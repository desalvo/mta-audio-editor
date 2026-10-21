"""Account approval, retirement, project recovery and private retention jobs."""
from __future__ import annotations
import hashlib
import hmac
import html
import json
import os
from pathlib import Path
import secrets
import threading
import time
import uuid
import zipfile
from . import auth

_LOCK=threading.RLock()
_STARTED=False
_STOP=threading.Event()


def init(con):
    con.executescript('''CREATE TABLE IF NOT EXISTS account_lifecycle(
      user_id INTEGER PRIMARY KEY, state TEXT NOT NULL DEFAULT 'pending',
      second_factor_required INTEGER NOT NULL DEFAULT 0, deleted_at INTEGER,
      project_deadline INTEGER, request_kind TEXT, requested_at INTEGER);
    CREATE TABLE IF NOT EXISTS account_retention_config(
      id INTEGER PRIMARY KEY CHECK(id=1), sandbox_days INTEGER NOT NULL DEFAULT 365,
      project_days INTEGER NOT NULL DEFAULT 60);
    INSERT OR IGNORE INTO account_retention_config(id) VALUES(1);
    CREATE TABLE IF NOT EXISTS account_identity_reservations(
      kind TEXT NOT NULL, digest TEXT NOT NULL, user_id INTEGER, PRIMARY KEY(kind,digest));
    CREATE TABLE IF NOT EXISTS account_archives(
      id TEXT PRIMARY KEY,user_id INTEGER, email TEXT NOT NULL, username TEXT NOT NULL,
      token TEXT NOT NULL UNIQUE, created_at INTEGER NOT NULL, expires_at INTEGER NOT NULL,
      state TEXT NOT NULL DEFAULT 'pending', project_ids TEXT NOT NULL DEFAULT '[]');
    CREATE TABLE IF NOT EXISTS account_sandboxes(
      id TEXT PRIMARY KEY, created_at INTEGER NOT NULL, expires_at INTEGER NOT NULL);
    CREATE TABLE IF NOT EXISTS account_action_confirmations(
      digest TEXT PRIMARY KEY,actor_id INTEGER NOT NULL,user_id INTEGER NOT NULL,
      stage INTEGER NOT NULL,expires INTEGER NOT NULL,privacy INTEGER NOT NULL);
    CREATE TABLE IF NOT EXISTS account_mail_outbox(
      id TEXT PRIMARY KEY,recipient TEXT NOT NULL,subject TEXT NOT NULL,body TEXT NOT NULL,
      state TEXT NOT NULL DEFAULT 'pending',lease INTEGER,attempts INTEGER NOT NULL DEFAULT 0);
    CREATE TABLE IF NOT EXISTS account_purge_jobs(user_id INTEGER PRIMARY KEY,job_ids TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS account_audit(
      id INTEGER PRIMARY KEY,user_id INTEGER,actor_id INTEGER,action TEXT NOT NULL,created_at INTEGER NOT NULL);
    ''')

    columns={r[1] for r in con.execute('PRAGMA table_info(account_lifecycle)')}
    if 'archive_lease' not in columns:con.execute('ALTER TABLE account_lifecycle ADD COLUMN archive_lease INTEGER NOT NULL DEFAULT 0')
    if 'mfa_method' not in columns:con.execute("ALTER TABLE account_lifecycle ADD COLUMN mfa_method TEXT NOT NULL DEFAULT 'totp'")
    columns={r[1] for r in con.execute('PRAGMA table_info(account_mail_outbox)')}
    if 'user_id' not in columns:con.execute('ALTER TABLE account_mail_outbox ADD COLUMN user_id INTEGER')


def settings(body=None):
    with auth.db() as con:
        init(con)
        if body is not None:
            if not isinstance(body,dict) or set(body)-{'sandbox_days','project_days'}:raise ValueError('Impostazioni non valide')
            for key,value in body.items():
                if type(value) is not int or not 1<=value<=3650:raise ValueError('Giorni ammessi: 1–3650')
            from .resource_accounts import init as init_resources,notice
            init_resources(con)
            previous=dict(con.execute('SELECT sandbox_days,project_days FROM account_retention_config').fetchone())
            for key,value in body.items():con.execute('UPDATE account_retention_config SET '+key+'=? WHERE id=1',(value,))  # noqa: S608 -- identifiers from fixed allowlists or quoted SQLite schema only
            changed=[key for key in body if body[key]!=previous[key]]
            if changed:
                revision=uuid.uuid4().hex
                for user in con.execute('SELECT id FROM users'):
                    notice(con,'retention:'+revision+':'+str(user[0]),user[0],{'kind':'legal','fields':changed})

        return dict(con.execute('SELECT sandbox_days,project_days FROM account_retention_config').fetchone())


def root():
    path=auth.data_root()/'.account-retention'
    if path.is_symlink():raise ValueError('Unsafe account retention root')
    path.mkdir(mode=0o700,parents=True,exist_ok=True);os.chmod(path,0o700)
    return path


def identity(kind,value):
    return hmac.new(auth._app_key(),(kind+':'+value.strip().casefold()).encode(),hashlib.sha256).hexdigest()


def reserve(con,uid,username,email):
    for kind,value in (('username',username),('email',email)):
        key=identity(kind,value)
        prior=con.execute('SELECT user_id FROM account_identity_reservations WHERE kind=? AND digest=?',(kind,key)).fetchone()
        if prior and prior[0]!=uid:raise ValueError(kind+' già utilizzato da un account; richiedi la riattivazione')
        con.execute('INSERT OR IGNORE INTO account_identity_reservations VALUES(?,?,?)',(kind,key,uid))


def availability(username,email):
    if len(username)>64 or len(email)>254:raise ValueError('Dati troppo lunghi')
    with auth.db() as con:
        init(con)
        result={}
        for kind,value in (('username',username),('email',email)):
            collision=con.execute('SELECT 1 FROM users WHERE '+kind+'=? COLLATE NOCASE',(value.strip(),)).fetchone()  # noqa: S608 -- identifiers from fixed allowlists or quoted SQLite schema only
            reserved=con.execute('SELECT 1 FROM account_identity_reservations WHERE kind=? AND digest=?',(kind,identity(kind,value))).fetchone()
            pending=con.execute('SELECT 1 FROM users WHERE pending_email=? COLLATE NOCASE',(value.strip(),)).fetchone() if kind=='email' else None
            result[kind+'_available']=bool(value.strip()) and not collision and not reserved and not pending
        return result


def info(uid):
    with auth.db() as con:
        init(con);row=con.execute('SELECT * FROM account_lifecycle WHERE user_id=?',(uid,)).fetchone()
    return dict(row) if row else {'state':'legacy','second_factor_required':0}


def is_deleted(uid):
    if uid and auth.get_user(uid) is None:
        with auth.db() as con:
            init(con)
            if con.execute("SELECT 1 FROM account_archives WHERE user_id=? AND state NOT IN ('revoked','expired')",(uid,)).fetchone():return True
    return bool(uid and info(uid)['state'] in ('deleting','deleted','expired','reactivation_pending','purged','erasing'))


def enqueue(con,key,recipient,subject,body,*,uid=None):
    if recipient:con.execute('INSERT OR IGNORE INTO account_mail_outbox(id,recipient,subject,body,user_id) VALUES(?,?,?,?,?)',(key,recipient,subject,body,uid))


def ready(uid):
    with auth.db() as con:
        init(con);user=con.execute('SELECT * FROM users WHERE id=?',(uid,)).fetchone()
        life=con.execute('SELECT * FROM account_lifecycle WHERE user_id=?',(uid,)).fetchone()
        if not user or user['active'] or not user['email_confirmed'] or (life and (life['second_factor_required'] and not (user['totp_enabled'] if life['mfa_method']=='totp' else life['mfa_method']=='email') or life['state'] not in ('pending','legacy'))):return False
        key='pending:'+str(uid)
        enqueue(con,key,user['email'],'Registrazione in attesa di approvazione','Email e requisiti di accesso verificati. Il tuo account è in attesa dell’approvazione di un amministratore. Riceverai una comunicazione quando sarà attivato.',uid=uid)
        for admin in con.execute("SELECT id,email FROM users WHERE role='admin' AND active=1 AND email_confirmed=1"):
            enqueue(con,key+':admin:'+str(admin['id']),admin['email'],'Richiesta di approvazione account',f"Richiesta pronta: {user['username']} ({user['email']}). Consulta Impostazioni → Utenti → Richieste pendenti.",uid=uid)
    return True


def register(uid,required=False,method='totp'):
    if method not in ('email','totp'):raise ValueError('Metodo secondo fattore non valido')
    with auth.db() as con:
        init(con);con.execute('BEGIN IMMEDIATE')
        user=con.execute('SELECT * FROM users WHERE id=?',(uid,)).fetchone()
        reserve(con,uid,user['username'],user['email'])
        con.execute('INSERT OR IGNORE INTO account_lifecycle(user_id,second_factor_required,mfa_method) VALUES(?,?,?)',(uid,int(required),method))
    if required:
        with auth.db() as con:con.execute("UPDATE account_lifecycle SET state='enrolling' WHERE user_id=?",(uid,))
    else:ready(uid)


def approval_guard(uid):
    life=info(uid);user=auth.get_user(uid)
    if life['state'] in ('deleting','deleted','expired','purged','erasing'):raise ValueError('Richiedere prima la riattivazione dell’account')
    if life['state']=='enrolling':raise ValueError('Completa prima la verifica del secondo fattore')
    if life['second_factor_required'] and not (user['totp_enabled'] if life['mfa_method']=='totp' else life['mfa_method']=='email'):raise ValueError('Il secondo fattore deve essere verificato prima dell’approvazione')


def approved(uid):
    with auth.db() as con:
        init(con);row=con.execute('SELECT * FROM users WHERE id=?',(uid,)).fetchone()
        con.execute("UPDATE account_lifecycle SET state='active',request_kind=NULL,requested_at=NULL WHERE user_id=?",(uid,))
        # Reactivation revokes old recovery URLs and cancels pending project deletion.
        archives=con.execute("SELECT id FROM account_archives WHERE user_id=? AND state!='expired'",(uid,)).fetchall()
        for archive in archives:con.execute("UPDATE account_archives SET state='revoked',token=? WHERE id=?",(secrets.token_urlsafe(32),archive['id']))
        con.execute('UPDATE account_lifecycle SET project_deadline=NULL,deleted_at=NULL WHERE user_id=?',(uid,))
        enqueue(con,'approved:'+str(uid)+':'+str(row['approved_at']),row['email'],'Account approvato · MTA Audio Editor','Il tuo account è stato approvato ed è attivo. Accedi al server con il metodo e il secondo fattore già configurati.',uid=uid)


def revoke(con,uid):
    for table in ('sessions','model_access_tokens','ai_access_tokens'):
        if not con.execute('SELECT 1 FROM sqlite_master WHERE type="table" AND name=?',(table,)).fetchone():continue
        if table=='sessions':con.execute('DELETE FROM sessions WHERE user_id=?',(uid,))
        else:con.execute('UPDATE '+table+' SET revoked_at=? WHERE user_id=?',(int(time.time()),uid))  # noqa: S608 -- identifiers from fixed allowlists or quoted SQLite schema only


def jobs(uid):
    from . import ai_arranger_runtime as queue
    with queue._db() as con:
        rows=[dict(r) for r in con.execute('SELECT * FROM jobs WHERE actor_user_id=? OR actor_user_id IS NULL',(uid,))]
    result=[]
    for row in rows:
        try:owner=row.get('actor_user_id') or json.loads(row.get('payload_json') or '{}').get('actor_user_id')
        except ValueError:continue
        if owner==uid:result.append(row)
    return result


def retire(uid,actor_id,*,privacy_request=False):
    user=auth.get_user(uid)
    if not user or user['role']=='admin':raise ValueError('Gli account amministratore non possono essere cancellati con questa funzione')
    config=settings();now=int(time.time())
    with auth.db() as con:
        init(con);con.execute('BEGIN IMMEDIATE')
        protected=con.execute('SELECT role FROM users WHERE id=?',(uid,)).fetchone()
        if not protected or protected[0]=='admin':raise ValueError('Gli amministratori non possono essere cancellati')
        old=con.execute('SELECT state FROM account_lifecycle WHERE user_id=?',(uid,)).fetchone()
        if old and old[0] in ('deleting','deleted','expired','reactivation_pending'):return {'state':old[0]}
        reserve(con,uid,user['username'],user['email'])
        con.execute('UPDATE users SET active=0,updated_at=? WHERE id=?',(now,uid));revoke(con,uid)
        con.execute("INSERT INTO account_lifecycle(user_id,state,deleted_at,project_deadline,request_kind,requested_at) VALUES(?,'deleting',?,?,?,?) ON CONFLICT(user_id) DO UPDATE SET state='deleting',deleted_at=excluded.deleted_at,project_deadline=excluded.project_deadline,request_kind=excluded.request_kind,requested_at=excluded.requested_at",(uid,now,now+config['project_days']*86400,'privacy' if privacy_request else 'deletion',now))
        con.execute('INSERT INTO account_audit(user_id,actor_id,action,created_at) VALUES(?,?,?,?)',(uid,actor_id,'retire',now))
        date=time.strftime('%Y-%m-%d %H:%M UTC',time.gmtime(now+config['project_days']*86400))
        enqueue(con,'retired:'+str(uid)+':'+str(now),user['email'],'Account disattivato: recupero progetti',f'L’account è disattivato e i token sono revocati. L’archivio è in preparazione: riceverai un secondo messaggio con il link riservato. Puoi richiedere una copia dei progetti entro {date}. Dopo questa scadenza verranno eliminati.',uid=uid)
        if privacy_request:
            for admin in con.execute("SELECT id,email FROM users WHERE role='admin' AND active=1 AND email_confirmed=1"):
                enqueue(con,'privacy-request:'+str(uid)+':'+str(now)+':'+str(admin['id']),admin['email'],'Richiesta cancellazione privacy',f"{user['username']} richiede la cancellazione privacy. Consulta gli archivi utenti cancellati nelle impostazioni e completa le due conferme amministrative.",uid=uid)
    from . import ai_arranger_runtime as queue
    for job in jobs(uid):
        if job['state'] in ('queued','blocked','running'):
            try:queue.cancel(job['job_id'])
            except ValueError:pass
    prepare_archive(uid)
    return {'state':info(uid)['state'],'project_deadline':info(uid).get('project_deadline')}


def prepare_archive(uid):
    if any(j['state'] in ('queued','blocked','running') for j in jobs(uid)):return False
    from . import storage
    with _LOCK:
        life=info(uid)
        if life['state']!='deleting':return False
        with auth.db() as con:
            con.execute('BEGIN IMMEDIATE')
            if con.execute("UPDATE account_lifecycle SET archive_lease=? WHERE user_id=? AND state='deleting' AND archive_lease<?",(int(time.time())+900,uid,int(time.time()))).rowcount!=1:return False
        user=auth.get_user(uid)
        projects=[p for p in storage.list_projects(is_admin=True) if p.owner_user_id==uid]
        aid=uuid.uuid4().hex;token=secrets.token_urlsafe(32);out=root()/(aid+'.zip');temp=out.with_suffix('.tmp')
        try:
            with zipfile.ZipFile(temp,'w',zipfile.ZIP_STORED) as archive:
                archive.writestr('README.txt','MTA Audio Editor: ogni file .maeproj contiene un progetto portabile.\n')
                for project in projects:
                    single=root()/(aid+'-'+project.id+'.maeproj')
                    try:storage.write_project_archive(project.id,single);archive.write(single,project.id+'.maeproj')
                    finally:single.unlink(missing_ok=True)
                    with auth.db() as con:con.execute('UPDATE account_lifecycle SET archive_lease=? WHERE user_id=?',(int(time.time())+900,uid))
            os.chmod(temp,0o600);os.replace(temp,out)
            with auth.db() as con:
                init(con);con.execute('INSERT INTO account_archives VALUES(?,?,?,?,?,?,?,?,?)',(aid,uid,user['email'],user['username'],token,int(time.time()),life['project_deadline'],'ready',json.dumps([p.id for p in projects])))
                con.execute("UPDATE account_lifecycle SET state='deleted' WHERE user_id=? AND state='deleting'",(uid,))
                link=auth._base_url()+'/account-projects/'+token
                date=time.strftime('%Y-%m-%d %H:%M UTC',time.gmtime(life['project_deadline']))
                enqueue(con,'deleted:'+aid,user['email'],'Account cancellato · recupero progetti',f'Il tuo account è disattivato. Billing e accounting restano conservati. Puoi richiedere una copia o scaricare i progetti entro {date}. Link riservato, da non condividere: {link}\nDopo tale data i progetti e questo archivio saranno cancellati. Puoi richiedere la riattivazione dalla pagina di login. La riattivazione non recupera progetti già eliminati.')
            return True
        finally:
            temp.unlink(missing_ok=True)
            with auth.db() as con:con.execute('UPDATE account_lifecycle SET archive_lease=0 WHERE user_id=?',(uid,))


def request_reactivation(identifier):
    user=auth.find_user(identifier)
    if not user or user['role']=='admin' or info(user['id'])['state'] not in ('deleted','expired','reactivation_pending'):return
    token=auth._create_email_token(user['id'],'reactivation')
    with auth.db() as con:
        init(con);enqueue(con,'reactivation-verify:'+auth._token_hash(token),user['email'],'Conferma richiesta di riattivazione',auth._base_url()+'/reactivate-account?token='+token,uid=user['id'])


def confirm_reactivation(token):
    row=auth._consume_email_token(token,'reactivation')
    if not row:return False
    uid=row['user_id']
    with auth.db() as con:
        init(con);user=con.execute('SELECT * FROM users WHERE id=?',(uid,)).fetchone()
        life=con.execute('SELECT state FROM account_lifecycle WHERE user_id=?',(uid,)).fetchone()
        if not life or life[0] not in ('deleted','expired','reactivation_pending'):return False
        now=int(time.time());con.execute("UPDATE account_lifecycle SET state='reactivation_pending',request_kind='reactivation',requested_at=? WHERE user_id=?",(now,uid))
        enqueue(con,'reactivation-pending:'+str(uid)+':'+str(now),user['email'],'Riattivazione in attesa','La richiesta è verificata ed è in attesa dell’approvazione amministratore. La scadenza dei progetti rimane valida finché non sei riattivato.',uid=uid)
        for admin in con.execute("SELECT id,email FROM users WHERE role='admin' AND active=1 AND email_confirmed=1"):
            enqueue(con,'reactivation-admin:'+str(uid)+':'+str(now)+':'+str(admin['id']),admin['email'],'Richiesta di riattivazione',f"{user['username']} richiede la riattivazione. Consulta le richieste pendenti nelle impostazioni.",uid=uid)
    return True


def listings():
    with auth.db() as con:
        init(con)
        pending=[dict(r) for r in con.execute("SELECT u.id,u.username,u.email,u.email_confirmed,u.totp_enabled,l.state,l.second_factor_required,l.mfa_method,l.request_kind FROM users u LEFT JOIN account_lifecycle l ON l.user_id=u.id WHERE u.active=0 AND (l.state IS NULL OR l.state IN ('pending','enrolling','reactivation_pending')) ORDER BY u.created_at")]
        archives=[dict(r) for r in con.execute('SELECT * FROM account_archives ORDER BY created_at DESC')]
        sandboxes=[dict(r) for r in con.execute('SELECT id,created_at,expires_at FROM account_sandboxes ORDER BY created_at DESC')]
    for archive in archives:
        account=auth.get_user(archive['user_id'])
        archive['account_exists']=bool(account)
        if account:
            archive['username']=account['username'];archive['email']=account['email']
        archive['request_kind']=info(archive['user_id']).get('request_kind')
        archive['url']=auth._base_url()+'/account-projects/'+archive.pop('token') if archive['state']=='ready' else None
    return {'pending':pending,'archives':archives,'sandboxes':sandboxes,'settings':settings()}


def has_accounting(con,uid):
    for table in ('ai_compute_jobs','ai_usage_events','ai_billing_periods','ai_persistent_storage_samples','resource_credits','resource_job_contracts','resource_periods','resource_storage_unlocks','resource_storage_debits','resource_quota_events'):
        if con.execute('SELECT 1 FROM sqlite_master WHERE type="table" AND name=?',(table,)).fetchone() and con.execute('SELECT 1 FROM '+table+' WHERE user_id=? LIMIT 1',(uid,)).fetchone():return True  # noqa: S608 -- identifiers from fixed allowlists or quoted SQLite schema only
    return False


def confirmation(actor,uid,body):
    from .account_erasure import erase
    return erase(uid,actor,confirmed=body.get('confirm'))


def _rows_for_user(con,uid,*,linked_jobs=()):
    """Discover user rows and FK descendants, including future ledger tables."""
    names=[r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")]
    selected={};meta={}
    for name in names:
        # All identifiers originate from SQLite, and are quoted, never request data.
        quoted='"'+name.replace('"','""')+'"'
        columns=[r[1] for r in con.execute('PRAGMA table_info('+quoted+')')];meta[name]=(quoted,columns)
        clauses=[f'"{k}"=?' for k in ('user_id','owner_user_id','actor_user_id') if k in columns]
        if name=='users':clauses=['id=?']
        if name in ('account_archives','account_identity_reservations','account_sandboxes','account_audit'):continue
        if clauses:selected[name]={r['rowid']:dict(r) for r in con.execute('SELECT rowid AS rowid,* FROM '+quoted+' WHERE '+' OR '.join(clauses),[uid]*len(clauses))}  # noqa: S608 -- identifiers from fixed allowlists or quoted SQLite schema only
    linked={r.get('id') for r in selected.get('ai_compute_jobs',{}).values()}|{j['job_id'] for j in jobs(uid)}|set(linked_jobs)
    for name,(quoted,columns) in meta.items():
        for col in ('job_id','queue_job_id'):
            if col in columns:
                for value in linked:
                    for row in con.execute('SELECT rowid AS rowid,* FROM '+quoted+' WHERE '+col+'=?',(value,)):  # noqa: S608 -- SQLite schema identifiers
                        selected.setdefault(name,{})[row['rowid']]=dict(row)
    changed=True
    while changed:
        changed=False
        for name,(quoted,columns) in meta.items():
            if name=='users':continue
            if name in ('account_archives','account_identity_reservations','account_sandboxes','account_audit'):continue
            for fk in con.execute('PRAGMA foreign_key_list('+quoted+')'):
                parent,childcol,parentcol=fk[2],fk[3],fk[4] or 'id'
                if parent=='users' and childcol not in ('user_id','owner_user_id','actor_user_id'):continue
                values={r.get(parentcol) for r in selected.get(parent,{}).values()}-{None}
                for value in values:
                    for row in con.execute('SELECT rowid AS rowid,* FROM '+quoted+' WHERE "'+childcol.replace('"','""')+'"=?',(value,)):  # noqa: S608 -- identifiers from fixed allowlists or quoted SQLite schema only
                        if row['rowid'] not in selected.setdefault(name,{}):selected[name][row['rowid']]=dict(row);changed=True
    return selected,meta


def purge(uid,actor,privacy):
    if any(j['state'] in ('queued','blocked','running') for j in jobs(uid)):raise ValueError('Job ancora attivi')
    config=settings();sid=uuid.uuid4().hex;now=int(time.time());file=root()/(sid+'.sandbox')
    try:
        with auth.db() as con:
            init(con);con.execute('BEGIN IMMEDIATE')
            user=con.execute('SELECT * FROM users WHERE id=?',(uid,)).fetchone()
            if not user or user['role']=='admin' or user['active']:raise ValueError('Account non eliminabile')
            state=con.execute('SELECT state FROM account_lifecycle WHERE user_id=?',(uid,)).fetchone()
            if not state or state[0] not in ('deleted','expired'):raise ValueError('Account riattivato o non pronto alla cancellazione totale')
            if has_accounting(con,uid) and not privacy:raise ValueError('Dati contabili presenti')
            selected,meta=_rows_for_user(con,uid)
            job_ids={j['job_id'] for j in jobs(uid)}|{r['id'] for r in selected.get('ai_compute_jobs',{}).values()}
            from . import ai_billing_outbox
            with ai_billing_outbox._db() as delivery:
                outbox=[dict(r) for r in delivery.execute('SELECT * FROM deliveries') if r['job_id'] in job_ids or r['billing_job_id'] in job_ids]
            if privacy:
                omit={'sessions','email_tokens','social_identities','model_access_tokens','ai_access_tokens','social_totp_challenges','account_email_mfa'}
                saved={k:list(v.values()) for k,v in selected.items() if k not in omit and not k.startswith('account_') and k!='users'}
                saved['users']=[{k:user[k] for k in ('id','username','email','display_name','created_at')}]
                blob={'schema':'mta/account-sandbox/v1','rows':saved,'billing_outbox':outbox,'queue':[{k:v for k,v in j.items() if k not in ('payload_json','idempotency_key')} for j in jobs(uid)]}
                payload=auth._seal(json.dumps(blob,default=str))
                fd=os.open(file,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
                with os.fdopen(fd,'w') as out:out.write(payload);out.flush();os.fsync(out.fileno())
                con.execute('INSERT INTO account_sandboxes VALUES(?,?,?)',(sid,now,now+config['sandbox_days']*86400))
            con.execute('PRAGMA defer_foreign_keys=ON')
            con.execute('UPDATE users SET approved_by=NULL WHERE approved_by=?',(uid,))
            # Archive download mail is separate and survives until the project grace deadline.
            for name,rows in selected.items():
                quoted=meta[name][0]
                for key in rows:con.execute('DELETE FROM '+quoted+' WHERE rowid=?',(key,))  # noqa: S608 -- identifiers from fixed allowlists or quoted SQLite schema only
            con.execute('UPDATE account_identity_reservations SET user_id=NULL WHERE user_id=?',(uid,))
            con.execute('UPDATE account_audit SET user_id=NULL WHERE user_id=?',(uid,))
            con.execute('INSERT OR REPLACE INTO account_purge_jobs VALUES(?,?)',(uid,json.dumps(sorted(job_ids))))
            con.execute('INSERT INTO account_audit(actor_id,action,created_at) VALUES(?,?,?)',(actor,'privacy-purge' if privacy else 'purge',now))
    except BaseException:
        file.unlink(missing_ok=True)
        raise
    _purge_queue(uid,job_ids)
    return {'done':True}


def _purge_queue(uid,job_ids):
    from . import ai_arranger_runtime as queue
    for jid in job_ids:queue._validate_job_id(jid)
    with queue._db() as con:
        con.execute('PRAGMA secure_delete=ON')
        # Terminal receipts are audit of identifiable job IDs; retire them with the job.
        ids=job_ids
        tables=[r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")]
        for jid in ids:
            for name in tables:
                quoted='"'+name.replace('"','""')+'"'
                cols={r[1] for r in con.execute('PRAGMA table_info('+quoted+')')}
                if name!='jobs' and 'job_id' in cols:con.execute('DELETE FROM '+quoted+' WHERE job_id=?',(jid,))  # noqa: S608 -- identifiers from fixed allowlists or quoted SQLite schema only
            from .studio_jobs import purge as purge_studio_result
            if __import__('re').fullmatch('[a-f0-9]{32}',jid):purge_studio_result(jid)
            con.execute('DELETE FROM jobs WHERE job_id=?',(jid,))
            for path in queue._ROOT.glob(jid+'.*'):
                if path.is_file() and not path.is_symlink():path.unlink()
    from . import ai_billing_outbox,ai_result_cache,ai_publish_outbox
    with ai_billing_outbox._db() as con:
        con.execute('PRAGMA secure_delete=ON')
        for jid in job_ids:con.execute('DELETE FROM deliveries WHERE job_id=? OR billing_job_id=?',(jid,jid))
    with ai_publish_outbox._open() as con:
        con.execute('PRAGMA secure_delete=ON')
        for jid in job_ids:
            con.execute('DELETE FROM publications WHERE job_id=?',(jid,))
            for suffix in ('.wav','.lock'):
                (queue._ROOT/'publication'/(jid+suffix)).unlink(missing_ok=True)
    cache=ai_result_cache._root()
    if cache:
        for metadata in cache.glob('*.json'):
            if metadata.is_symlink() or metadata.stat().st_size>1024*1024:continue
            try:details=json.loads(metadata.read_text())
            except (OSError,ValueError):continue
            if details.get('job_id') in job_ids:
                blob=metadata.with_suffix('.bin')
                with ai_result_cache._entry_lock(cache,blob):
                    blob.unlink(missing_ok=True);metadata.unlink(missing_ok=True)
    with auth.db() as con:con.execute('DELETE FROM account_purge_jobs WHERE user_id=?',(uid,))
    return {'done':True}


def cleanup(now=None):
    from .account_erasure import resume
    resume()
    from . import storage
    now=int(time.time() if now is None else now)
    with _LOCK:
        with auth.db() as con:
            init(con)
            con.execute('DELETE FROM account_action_confirmations WHERE expires<?',(now,))
            archives=[dict(r) for r in con.execute("SELECT * FROM account_archives WHERE expires_at<=? AND state!='expired'",(now,))]
            sandboxes=[dict(r) for r in con.execute('SELECT * FROM account_sandboxes WHERE expires_at<=?',(now,))]
        for archive in archives:
            for pid in ([] if archive['state']=='revoked' else json.loads(archive['project_ids'])):
                project=storage.load_project(pid) if storage.pdir(pid).exists() else None
                if project and project.owner_user_id==archive['user_id']:
                    storage.delete_project(pid)
                    if storage.pdir(pid).exists():raise OSError('Project retention deletion failed')
            (root()/(archive['id']+'.zip')).unlink(missing_ok=True)
            with auth.db() as con:
                con.execute("UPDATE account_archives SET state='expired',email='',username='',token=?,project_ids='[]' WHERE id=?",(secrets.token_urlsafe(32),archive['id']))
                con.execute("UPDATE account_lifecycle SET state='expired' WHERE user_id=? AND state='deleted'",(archive['user_id'],))
                con.execute('DELETE FROM account_mail_outbox WHERE id=?',('deleted:'+archive['id'],))
        for box in sandboxes:
            (root()/(box['id']+'.sandbox')).unlink(missing_ok=True)
            with auth.db() as con:con.execute('DELETE FROM account_sandboxes WHERE id=?',(box['id'],))
    return {'archives_expired':len(archives),'sandboxes_expired':len(sandboxes)}


def send_pending():
    cfg=auth.get_smtp_config()
    if not cfg.get('host') or not cfg.get('from_email'):return
    for _ in range(50):
        now=int(time.time())
        with auth.db() as con:
            init(con);con.execute('BEGIN IMMEDIATE')
            row=con.execute("SELECT * FROM account_mail_outbox WHERE state!='sent' AND (lease IS NULL OR lease<?) ORDER BY rowid LIMIT 1",(now-120,)).fetchone()
            if not row:return
            row=dict(row);con.execute("UPDATE account_mail_outbox SET state='sending',lease=? WHERE id=?",(now,row['id']))
        try:
            from .version import APP_RELEASE
            from .admin_navigation import action, outbox_action
            target=outbox_action(row['id'],row.get('user_id'))
            plain,link=action(row['body'],*target) if target else (row['body'],'')
            body='<html><body style="font:16px Arial;background:#edf2f8;padding:24px"><main style="background:white;max-width:640px;margin:auto;padding:28px"><img src="cid:mta-logo" width="64" height="64" alt="MTA"><h1>'+html.escape(row['subject'])+'</h1><p style="white-space:pre-wrap">'+html.escape(row['body'])+'</p>'+link+'<hr>MTA Audio Editor '+APP_RELEASE+'<br>'+html.escape(auth._base_url())+'</main></body></html>'
            auth.send_mail([row['recipient']],row['subject'],plain,body,inline_image=(Path(__file__).parent/'static/mail-logo.png').read_bytes(),message_id='<mta-account-'+hashlib.sha256(row['id'].encode()).hexdigest()+'@mta.local>')
            with auth.db() as con:con.execute("UPDATE account_mail_outbox SET state='sent',lease=NULL,body='' WHERE id=?",(row['id'],))
        except Exception:
            with auth.db() as con:con.execute("UPDATE account_mail_outbox SET state='pending',lease=?,attempts=attempts+1 WHERE id=?",(now+180,row['id']))
            return


def tick():
    auth.init_auth_db()
    with auth.db() as con:
        init(con);pending=[r[0] for r in con.execute("SELECT user_id FROM account_lifecycle WHERE state='deleting'")]
        purge_tasks=[dict(r) for r in con.execute('SELECT * FROM account_purge_jobs')]
    for task in purge_tasks:_purge_queue(task['user_id'],set(json.loads(task['job_ids'])))
    for uid in pending:prepare_archive(uid)
    cleanup();send_pending()


def start_service():
    global _STARTED
    if _STARTED:return
    _STARTED=True
    _STOP.clear()
    def loop():
        import logging
        while not _STOP.is_set():
            try:tick()
            except Exception:logging.getLogger(__name__).exception('Account retention cycle deferred')
            _STOP.wait(60)
    threading.Thread(target=loop,name='mta-account-retention',daemon=True).start()


def stop_service():
    global _STARTED
    _STOP.set();_STARTED=False
