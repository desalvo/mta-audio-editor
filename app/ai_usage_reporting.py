"""User totals and token breakdown; verified and diagnostic resources stay distinct."""
from __future__ import annotations
import json
import math
import time
import uuid
from . import auth, ai_billing


def records(user_id, start, end, *, completed_window=False):
    if type(user_id) is not int or user_id<=0 or any(isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) for v in (start,end)) or not 0<=start<end:
        raise ValueError('Invalid user or reporting interval')
    with auth.db() as con:
        ai_billing._init(con)
        sql=('SELECT * FROM ai_compute_jobs WHERE user_id=? AND finished_at>=? AND finished_at<? ORDER BY started_at,id' if completed_window else 'SELECT * FROM ai_compute_jobs WHERE user_id=? AND started_at>=? AND started_at<? ORDER BY started_at,id')
        ledger=[dict(r) for r in con.execute(sql,(user_id,start,end))]
        from .ai_compute_diagnostics import read as read_diagnostics
        diagnostics=read_diagnostics(con,user_id)
        rates=ai_billing._rates_for_jobs(con,ledger)
        enabled=ai_billing.user_billing_enabled(user_id,_connection=con)
        for row in ledger:
            row['usage']=json.loads(row['usage_json'])
            row['estimated']=diagnostics.get(row['id'],{})
            row['cost_micro']=sum(round(qty*rates[row['id']].get(key,0)) for key,qty in row['usage'].items()
              if row['status']=='done' and row['resource_source']!='unmetered' and row['billable']==1
              and key not in ai_billing.NON_BILLABLE_IO and key!='disk_gb_hours')
            row['amount_micro']=row['cost_micro'] if enabled else 0
            row['origin']='ledger'
        # Do not count a queue Arranger and its ledger settlement twice.
        all_ledger={r[0] for r in con.execute('SELECT id FROM ai_compute_jobs WHERE user_id=?',(user_id,))}
    from . import ai_arranger_runtime as queue
    with queue._db() as con:
        sql='SELECT * FROM jobs WHERE completed_at>=? AND completed_at<?' if completed_window else 'SELECT * FROM jobs WHERE created_at>=? AND created_at<?'
        rows=[dict(r) for r in con.execute(sql,(start,end))]
    for row in rows:
        actor_id=row.get('actor_user_id')
        if actor_id is None:
            try:actor_id=json.loads(row.get('payload_json') or '{}').get('actor_user_id')
            except ValueError:continue
        if actor_id!=user_id:continue
        linked=uuid.uuid5(uuid.NAMESPACE_URL,'mta-ai-inference:'+row['job_id']).hex
        if linked in all_ledger:
            target=next((r for r in ledger if r['id']==linked),None)
            if target is not None:
                value=queue._with_live_progress(row)
                target['estimated'].update({key:value[key] for key in ('cpu_seconds_estimated','gpu_seconds_estimated') if value.get(key) is not None})
            continue
        value=queue._with_live_progress(row)
        verified={key:value[key] for key in ('cpu_seconds','gpu_seconds') if value.get(key) is not None}
        estimated={key:value[key] for key in ('cpu_seconds_estimated','gpu_seconds_estimated') if value.get(key) is not None}
        ledger.append({'id':row['job_id'],'user_id':user_id,'token_id':None,'kind':row['operation'],
          'status':row['state'],'started_at':row['started_at'] or row['created_at'],'finished_at':row['completed_at'],
          'wall_ms':max(0,int(((row['completed_at'] or time.time())-(row['started_at'] or time.time()))*1000)),
          'usage':verified,'estimated':estimated,'resource_source':'queue-diagnostic','cost_micro':0,'amount_micro':0,'origin':'queue'})
    return ledger


def aggregate(items):
    total={'jobs':0,'usage':{},'diagnostic':{},'cost_micro':0,'amount_micro':0,'unmetered_jobs':0}
    for row in items:
        total['jobs']+=1
        total['cost_micro']+=row['cost_micro'];total['amount_micro']+=row['amount_micro']
        if not row['usage']:total['unmetered_jobs']+=1
        for source,target in [('usage','usage'),('estimated','diagnostic')]:
            for key,value in row[source].items():total[target][key]=total[target].get(key,0)+value
    return total


def snapshot(user_id,start,end,*,token_id=None,completed_window=False):
    items=records(user_id,start,end,completed_window=completed_window)
    if token_id is not None:items=[r for r in items if r['token_id']==token_id]
    from .ai_access import list_tokens
    tokens={r['id']:r for r in list_tokens(user_id)}
    ids={r['token_id'] for r in items}
    groups=[{'token_id':tid,'label':tokens.get(tid,{}).get('label','Web / senza token' if tid is None else 'Token storico'),
      **aggregate([r for r in items if r['token_id']==tid])} for tid in sorted(ids,key=lambda x:-1 if x is None else x)]
    return {'user_id':user_id,'start_ts':start,'end_ts':end,'currency':'EUR','by_token':groups,**aggregate(items),
      'billing_enabled':ai_billing.user_billing_enabled(user_id),'amount_is_estimate':True,'interval_basis':'completion' if completed_window else 'start',
      'note':'Importi stimati a tariffe storicizzate, non fatture. Storage condiviso per utente escluso dal dettaglio token. Diagnostica GPU non fatturabile.'}
