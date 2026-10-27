"""Persistent lifecycle email outbox and configurable user resource digests.

Mail is at-least-once with stable Message-ID; SMTP cannot guarantee exactly-once
across a crash after remote acceptance. Failures never stop inference or billing.
"""
from __future__ import annotations
from .service_admission import admitted
import datetime as dt
import hashlib
import html
import json
import logging
import os
import time
import threading
import uuid
from pathlib import Path
from urllib.parse import urlsplit
from . import auth, i18n

LOG=logging.getLogger(__name__)
CADENCES={'day':86400,'week':604800,'month':2592000,'off':0}


def _init(con):
    con.executescript('''
    CREATE TABLE IF NOT EXISTS ai_mail_config(id INTEGER PRIMARY KEY, cadence TEXT NOT NULL, since REAL NOT NULL, active INTEGER NOT NULL DEFAULT 0);
    CREATE TABLE IF NOT EXISTS ai_mail_preferences(user_id INTEGER PRIMARY KEY, cadence TEXT,
      language TEXT NOT NULL DEFAULT 'it', cursor REAL NOT NULL);
    CREATE TABLE IF NOT EXISTS ai_mail_events(id TEXT PRIMARY KEY,user_id INTEGER NOT NULL,
      payload TEXT NOT NULL,state TEXT NOT NULL DEFAULT 'pending',attempts INTEGER NOT NULL DEFAULT 0,
      due REAL NOT NULL,lease REAL,created_at REAL NOT NULL,last_error TEXT);
    ''')
    if 'active' not in {r[1] for r in con.execute('PRAGMA table_info(ai_mail_config)')}:con.execute('ALTER TABLE ai_mail_config ADD COLUMN active INTEGER NOT NULL DEFAULT 0')
    con.execute("INSERT OR IGNORE INTO ai_mail_config(id,cadence,since) VALUES(1,'week',?)",(time.time(),))
    con.commit()


def smtp_configured():
    cfg=auth.get_smtp_config()
    return bool(cfg.get('host') and cfg.get('from_email'))


def preferences(user_id):
    with auth.db() as con:
        _init(con)
        config=con.execute('SELECT * FROM ai_mail_config WHERE id=1').fetchone()
        row=con.execute('SELECT * FROM ai_mail_preferences WHERE user_id=?',(user_id,)).fetchone()
    return {'cadence':row['cadence'] if row else None,'effective_cadence':(row['cadence'] if row and row['cadence'] else config['cadence']),
      'default_cadence':config['cadence'],'language':i18n.user_language(user_id),'smtp_configured':smtp_configured(),
      'job_notifications':'always-when-smtp-configured'}


def set_preferences(user_id,body):
    if set(body)-{'cadence','language'}:raise ValueError('Unsupported preference')
    cadence=body.get('cadence');language=body.get('language',preferences(user_id)['language'])
    if cadence is not None and cadence not in CADENCES:raise ValueError('Invalid cadence')
    if language not in ('en','it'):raise ValueError('Invalid language')
    with auth.db() as con:
        _init(con)
        if not con.execute('SELECT 1 FROM users WHERE id=?',(user_id,)).fetchone():raise ValueError('Unknown user')
        con.execute('''INSERT INTO ai_mail_preferences(user_id,cadence,language,cursor) VALUES(?,?,?,?)
          ON CONFLICT(user_id) DO UPDATE SET cadence=excluded.cadence,language=excluded.language''',
          (user_id,cadence,language,time.time()))
    return preferences(user_id)


def set_default(cadence):
    if cadence not in CADENCES:raise ValueError('Invalid cadence')
    with auth.db() as con:
        _init(con);con.execute('UPDATE ai_mail_config SET cadence=? WHERE id=1',(cadence,))
    return {'cadence':cadence}


def _queue_event(con,key,user,payload):
    con.execute('INSERT OR IGNORE INTO ai_mail_events(id,user_id,payload,due,created_at) VALUES(?,?,?,?,?)',
      (key,user,json.dumps(payload,sort_keys=True,allow_nan=False),time.time(),time.time()))


def collect():
    if not smtp_configured():
        with auth.db() as con:
            _init(con);con.execute('UPDATE ai_mail_config SET active=0 WHERE id=1')
        return {'queued':0,'smtp_configured':False}
    from . import ai_arranger_runtime as queue, ai_billing
    from .ai_usage_reporting import snapshot
    now=time.time()
    with auth.db() as con:
        _init(con);ai_billing._init(con)
        cfg=con.execute('SELECT since,active FROM ai_mail_config WHERE id=1').fetchone()
        if not cfg['active']:
            con.execute('UPDATE ai_mail_config SET since=?,active=1 WHERE id=1',(now,))
        since=cfg['since'] if cfg['active'] else now
        users={r['id']:dict(r) for r in con.execute('SELECT id,email FROM users WHERE active=1 AND email_confirmed=1 AND email<>\'\'')}
        seen={r[0] for r in con.execute('SELECT id FROM ai_mail_events')}
        ledgers=[dict(r) for r in con.execute('SELECT * FROM ai_compute_jobs WHERE accounting_excluded=0 AND (started_at>=? OR finished_at>=?)',(since,since))]
    with queue._db() as con:
        queued=[dict(r) for r in con.execute('SELECT * FROM jobs WHERE created_at>=? OR completed_at>=?',(since,since))]
    queue_ids={r['job_id'] for r in queued}
    queue_ledgers={uuid.uuid5(uuid.NAMESPACE_URL,'mta-ai-inference:'+r['job_id']).hex for r in queued}
    queue_ledgers.update(r['id'] for r in ledgers if r.get('queue_job_id') in queue_ids)
    events=[];detail_cache={}
    def details_for(owner):
        if owner not in detail_cache:
            from .ai_usage_reporting import records
            detail_cache[owner]={r['id']:r for r in records(owner,0,now+1)}
        return detail_cache[owner]
    from .ai_queue_admin import dispositions
    excluded=dispositions()
    for row in queued:
        if excluded.get(row["job_id"]) in ("disabled","deleted"):continue
        event_key='queue:'+row['job_id']
        if (event_key+':terminal:'+row['state'] in seen) or (row['state'] not in ('completed','failed','cancelled','interrupted') and event_key+':started' in seen):continue
        owner=row.get('actor_user_id')
        if owner is None:
            try:owner=json.loads(row.get('payload_json') or '{}').get('actor_user_id')
            except ValueError:continue
        if owner not in users:continue
        value=queue._with_live_progress(row)
        usage={k:value[k] for k in ('cpu_seconds','gpu_seconds') if value.get(k) is not None}
        estimated={k:value[k] for k in ('cpu_seconds_estimated','gpu_seconds_estimated') if value.get(k) is not None}
        payload={'job_id':row['job_id'],'operation':row['operation'],'status':row['state'],
          'started_at':row['started_at'],'finished_at':row['completed_at'],'usage':usage,'diagnostic':estimated,'token_id':None,
          'amount_micro':0,'credits_debited_micro':0,'cost_pending':False,'origin':'queue'}
        # Billing only comes from the ledger, never from progress sidecars.
        linked=uuid.uuid5(uuid.NAMESPACE_URL,'mta-ai-inference:'+row['job_id']).hex
        linked_rows=[r for r in ledgers if r['id']==linked or r.get('queue_job_id')==row['job_id']]
        if linked_rows:
            payload.update(usage={},amount_micro=0,cost_pending=False)
            for ledger in linked_rows:
                details=details_for(owner).get(ledger['id'])
                for key,quantity in json.loads(ledger['usage_json']).items():
                    payload['usage'][key]=payload['usage'].get(key,0)+quantity
                if details:
                    payload['amount_micro']+=details['amount_micro']
                    payload['credits_debited_micro']+=details.get('credits_debited_micro',0)
                payload['cost_pending']|=ledger['status']=='running'
            for metric in payload['usage']:
                if any(r['resource_source']=='diagnostic-estimate' and metric in json.loads(r['usage_json']) for r in linked_rows):
                    payload['diagnostic'].pop(metric+'_estimated',None)
            tokens={r['token_id'] for r in linked_rows}
            payload['token_id']=next(iter(tokens)) if len(tokens)==1 else None
        events.append((owner,payload))
    for row in ledgers:
        event_key='ledger:'+row['id']
        if event_key+':terminal:'+row['status'] in seen or (row['status']=='running' and event_key+':started' in seen):continue
        if row['id'] in queue_ledgers or row['user_id'] not in users:continue
        details=details_for(row['user_id']).get(row['id'])
        events.append((row['user_id'],{'job_id':row['id'],'operation':row['kind'],'status':row['status'],
          'started_at':row['started_at'],'finished_at':row['finished_at'],'usage':json.loads(row['usage_json']),
          'diagnostic':details['estimated'] if details else {},'token_id':row['token_id'],'amount_micro':details['amount_micro'] if details else 0,
          'credits_debited_micro':details.get('credits_debited_micro',0) if details else 0,'cost_pending':row['status']=='running','origin':'ledger'}))
    with auth.db() as con:
        _init(con)
        before=con.total_changes
        for owner,value in events:
            key=value['origin']+':'+value['job_id']
            if value['started_at'] is not None:
                start={**value,'event':'started','status':'running','finished_at':None,'usage':{},'diagnostic':{},'amount_micro':0,'credits_debited_micro':0,'cost_pending':True}
                _queue_event(con,key+':started',owner,start)
            if value['status'] in ('completed','done','failed','cancelled','interrupted'):
                _queue_event(con,key+':terminal:'+value['status'],owner,{**value,'event':'terminal'})
        queued_count=con.total_changes-before
    # Each user's cursor and digest intent commit together. Failed mail retries
    # the same immutable interval, rather than consuming or repeating its usage.
    for owner in users:
        with auth.db() as con:
            _init(con)
            con.execute('INSERT OR IGNORE INTO ai_mail_preferences(user_id,cursor) VALUES(?,?)',(owner,now))
            row=con.execute('SELECT * FROM ai_mail_preferences WHERE user_id=?',(owner,)).fetchone()
            default=con.execute('SELECT cadence FROM ai_mail_config WHERE id=1').fetchone()[0]
        span=CADENCES[row['cadence'] or default]
        if not span or now-row['cursor']<span:continue
        start=row['cursor'];summary=snapshot(owner,start,now,completed_window=True)
        with auth.db() as con:
            _init(con);con.execute('BEGIN IMMEDIATE')
            current=con.execute('SELECT cursor FROM ai_mail_preferences WHERE user_id=?',(owner,)).fetchone()[0]
            if current!=start:continue
            _queue_event(con,f'summary:{owner}:{start}:{now}',owner,{'event':'summary','report':summary})
            con.execute('UPDATE ai_mail_preferences SET cursor=? WHERE user_id=?',(now,owner))
    return {'queued':queued_count,'smtp_configured':True}


def _server():
    value=os.getenv('MTA_PUBLIC_URL','').rstrip('/')
    parsed=urlsplit(value)
    if parsed.scheme not in ('http','https') or not parsed.hostname or parsed.username or parsed.password:return 'MTA server'
    return value


def render(payload,language):
    from .version import APP_RELEASE
    tr=lambda en,it:it if language=='it' else en
    esc=lambda x:html.escape(str(x),quote=True)
    status={'running':tr('Started','Avviato'),'done':tr('Completed','Completato'),'completed':tr('Completed','Completato'),
      'failed':tr('Failed','Fallito'),'cancelled':tr('Cancelled','Annullato'),'interrupted':tr('Interrupted','Interrotto')}
    fields=[]
    def metric(label,values):
        return ', '.join(f'{key}: {value:.3f}' for key,value in values.items()) or tr('Unavailable / not yet measured','Non disponibile / non ancora misurato')
    def table(rows):return '<table role="presentation" width="100%" style="border-collapse:collapse">'+''.join('<tr><td style="padding:10px;border-bottom:1px solid #dce5ef;color:#54667e">'+esc(k)+'</td><td style="padding:10px;border-bottom:1px solid #dce5ef">'+esc(v)+'</td></tr>' for k,v in rows)+'</table>'
    if payload['event']=='summary':
        report=payload['report'];title=tr('Your AI resource summary','Riepilogo delle tue risorse AI')
        utc=lambda stamp:dt.datetime.fromtimestamp(stamp,dt.timezone.utc).strftime('%Y-%m-%d %H:%M UTC')
        fields=[(tr('Period','Periodo'),utc(report['start_ts'])+' → '+utc(report['end_ts'])),('Job',report['jobs']),
          (tr('Accounted resources','Risorse contabilizzate'),metric('',report['usage'])),
          (tr('Unsettled counters','Contatori non contabilizzati'),metric('',report['diagnostic'])),
          (tr('Estimated amount (not an invoice)','Importo stimato (non è una fattura)'),f"€ {report['amount_micro']/1e6:.6f}")]
        extra='<h3>'+tr('By application token','Dettaglio per token applicazione')+'</h3>'+table([(str(row['token_id'])+' · '+row['label'],f"{row['jobs']} job · € {row['amount_micro']/1e6:.6f} · "+metric('',row['usage'])) for row in report['by_token']])
    else:
        title=tr('AI job','Job AI')+' · '+status.get(payload['status'],payload['status'])
        utc=lambda stamp:dt.datetime.fromtimestamp(stamp,dt.timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC') if stamp is not None else '—'
        fields=[(tr('Start','Inizio'),utc(payload.get('started_at'))),(tr('End','Fine'),utc(payload.get('finished_at'))),('Job',payload['job_id']),(tr('Operation','Operazione'),payload['operation']),
          (tr('Status','Stato'),status.get(payload['status'],payload['status'])),('Token',payload.get('token_id') or tr('Web / no token','Web / senza token')),
          (tr('Accounted resources','Risorse contabilizzate'),metric('',payload['usage'])),
          (tr('Unsettled counters','Contatori non contabilizzati'),metric('',payload['diagnostic'])),
          (tr('Estimated amount (not an invoice)','Importo stimato (non è una fattura)'),f"€ {payload['amount_micro']/1e6:.6f}"+(' · '+tr('pending','provvisorio') if payload.get('cost_pending') else ''))]
        extra=''
    credits=payload['report'].get('credits_debited_micro',0) if payload['event']=='summary' else payload.get('credits_debited_micro',0)
    fields.append((tr('CPU/GPU credits used','Crediti CPU/GPU utilizzati'),f'€ {credits/1e6:.6f}'))
    plain=title+'\n'+APP_RELEASE+' · '+_server()+'\n'+'\n'.join(str(k)+': '+str(v) for k,v in fields)
    body=f'''<!doctype html><html><body style="margin:0;background:#edf2f8;font:15px Arial,sans-serif;color:#172a42"><table role="presentation" width="100%"><tr><td align="center" style="padding:28px 12px"><table role="presentation" width="620" style="width:100%;max-width:620px;background:white;border-radius:14px"><tr><td style="background:#153753;color:white;padding:24px;border-radius:14px 14px 0 0"><img src="cid:mta-logo" width="64" height="64" alt="MTA"><h1 style="font-size:24px;margin:12px 0">{esc(title)}</h1><p>MTA Audio Editor · {esc(APP_RELEASE)}</p></td></tr><tr><td style="padding:24px">{table(fields)}{extra}<p style="font-size:13px;color:#54667e">{esc(tr('Server','Server'))}: {esc(_server())}</p><p style="font-size:12px;color:#54667e">{esc(tr('Per-job consumption accepted by the server is accounted for quotas and billing. Unsettled counters do not authorize charges. This email is not an invoice.','I consumi per job accettati dal server sono contabilizzati per quote e billing. I contatori non contabilizzati non autorizzano addebiti. Questa email non è una fattura.'))}</p></td></tr></table></td></tr></table></body></html>'''
    return title+' · MTA',plain,body


def deliver(limit=25):
    if not smtp_configured():return {'sent':0,'failed':0,'smtp_configured':False}
    sent=failed=0
    for _ in range(limit):
        now=time.time()
        with auth.db() as con:
            _init(con);con.execute('BEGIN IMMEDIATE')
            row=con.execute("SELECT e.* FROM ai_mail_events e WHERE e.state!='sent' AND e.due<=? AND (e.lease IS NULL OR e.lease<?) AND (e.id NOT LIKE '%:terminal:%' OR NOT EXISTS(SELECT 1 FROM ai_mail_events prior WHERE prior.id=substr(e.id,1,instr(e.id,':terminal:')-1)||':started' AND prior.state!='sent')) ORDER BY e.created_at,e.id LIMIT 1",(now,now-120)).fetchone()
            if not row:break
            con.execute("UPDATE ai_mail_events SET state='sending',lease=? WHERE id=?",(now,row['id']))
            user=con.execute('SELECT email,active,email_confirmed FROM users WHERE id=?',(row['user_id'],)).fetchone()
        try:
            if not user or not user['active'] or not user['email_confirmed']:
                raise RuntimeError('Recipient not eligible')
            from .i18n import user_language
            language=user_language(row['user_id'])
            subject,plain,body=render(json.loads(row['payload']),language)
            auth.send_mail([user['email']],subject,plain,body,
              inline_image=(Path(__file__).parent/'static'/'mail-logo.png').read_bytes(),
              message_id='<mta-ai-'+hashlib.sha256(row['id'].encode()).hexdigest()+'@mta.local>')
            with auth.db() as con:con.execute("UPDATE ai_mail_events SET state='sent',lease=NULL,last_error=NULL WHERE id=?",(row['id'],))
            sent+=1
        except Exception as exc:
            failed+=1
            with auth.db() as con:con.execute("UPDATE ai_mail_events SET state='pending',lease=NULL,attempts=attempts+1,due=?,last_error=? WHERE id=?",(now+min(86400,30*2**min(row['attempts'],11)),type(exc).__name__,row['id']))
            LOG.warning('AI email delivery deferred (%s)',type(exc).__name__)
    return {'sent':sent,'failed':failed,'smtp_configured':True}


@admitted('notifications')
def tick():
    # Expired approval replies must not keep a recoverable credential forever.
    with auth.db() as con:
        if con.execute("SELECT 1 FROM sqlite_master WHERE name='ai_device_requests'").fetchone():
            con.execute('DELETE FROM ai_device_requests WHERE expires_at<?',(int(time.time()),))
    from .resource_accounts import periodic_tick
    periodic_tick()
    collect();return deliver()


_SERVICE_LOCK=threading.Lock()
_THREAD=None
_STOP=None


def start_service():
    global _THREAD,_STOP
    with _SERVICE_LOCK:
        if _THREAD is not None and _THREAD.is_alive():return
        stop=threading.Event();_STOP=stop
        def work():
            while not stop.is_set():
                try:tick()
                except Exception:LOG.exception('AI notification scheduler deferred')
                stop.wait(5)
        _THREAD=threading.Thread(target=work,daemon=True,name='mta-ai-email');_THREAD.start()


def stop_service():
    with _SERVICE_LOCK:
        stop,thread=_STOP,_THREAD
        if stop is not None:stop.set()
    if thread is not None:thread.join(2)
