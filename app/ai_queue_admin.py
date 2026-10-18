"""Administrative queue search and audited accounting exclusions.

Deletion is a durable tombstone: measurements/results remain evidence, never billed
or included in current usage. Closed invoice periods cannot be changed here.
"""
from __future__ import annotations
import time
import uuid
from . import auth, ai_billing, ai_arranger_runtime as queue


def tables(con):
    ai_billing._init(con)
    con.executescript('''CREATE TABLE IF NOT EXISTS ai_job_dispositions(
      queue_job_id TEXT PRIMARY KEY, disposition TEXT NOT NULL, changed_at INTEGER NOT NULL,
      actor_id INTEGER NOT NULL, reason TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS ai_job_disposition_audit(
      id INTEGER PRIMARY KEY, queue_job_id TEXT NOT NULL, disposition TEXT NOT NULL,
      changed_at INTEGER NOT NULL, actor_id INTEGER NOT NULL, reason TEXT NOT NULL);''')


def dispositions():
    with auth.db() as con:
        tables(con)
        return {r['queue_job_id']: r['disposition'] for r in con.execute('SELECT * FROM ai_job_dispositions')}


def query(search='', state='', visibility='visible', *, page=1, page_size=20, ids=None):
    if any(not isinstance(v,str) for v in (search,state,visibility)) or len(search)>200 or state not in ('','queued','blocked','running','completed','cancelled','failed','interrupted') or visibility not in ('visible','all','disabled','deleted'):
        raise ValueError('Filtri non validi')
    if type(page) is not int or page<1 or type(page_size) is not int or not 10<=page_size<=100:
        raise ValueError('Pagina non valida; da 10 a 100 righe per pagina')
    states=dispositions()
    with auth.db() as users_db:
        users = [tuple(r) for r in users_db.execute('SELECT id,username,display_name,email FROM users')]
        attributed = [tuple(r) for r in users_db.execute('SELECT queue_job_id,min(user_id) FROM ai_compute_jobs WHERE queue_job_id IS NOT NULL GROUP BY queue_job_id HAVING count(DISTINCT user_id)=1')]
    with queue._db() as con:
        queue._recover_dead_runners(con)
        con.execute('CREATE TEMP TABLE dispositions(job_id TEXT PRIMARY KEY, disposition TEXT)')
        con.executemany('INSERT INTO dispositions VALUES(?,?)', states.items())
        con.execute('CREATE TEMP TABLE actors(id INTEGER PRIMARY KEY, username TEXT, display_name TEXT, email TEXT)')
        con.executemany('INSERT INTO actors VALUES(?,?,?,?)', users)
        con.execute('CREATE TEMP TABLE attribution(job_id TEXT PRIMARY KEY,user_id INTEGER)')
        con.executemany('INSERT INTO attribution VALUES(?,?)', attributed)
        where=['1=1']; args=[]
        if visibility=='visible':where.append("coalesce(d.disposition,'')!='deleted'")
        elif visibility!='all':where.append('d.disposition=?');args.append(visibility)
        if state:where.append('j.state=?');args.append(state)
        if search:
            where.append("(j.job_id LIKE ? ESCAPE '\\' OR j.project_id LIKE ? ESCAPE '\\' OR j.operation LIKE ? ESCAPE '\\' OR j.state LIKE ? ESCAPE '\\' OR cast(coalesce(j.actor_user_id,t.user_id) AS TEXT) LIKE ? ESCAPE '\\' OR a.username LIKE ? ESCAPE '\\' OR a.display_name LIKE ? ESCAPE '\\' OR a.email LIKE ? ESCAPE '\\')")
            term='%'+search.replace('\\','\\\\').replace('%','\\%').replace('_','\\_')+'%';args.extend([term]*8)
        if ids is not None:
            if not ids:return {'jobs':[], 'total':0,'page':1,'page_size':page_size,'pages':1}
            where.append('j.job_id IN ('+','.join('?' for _ in ids)+')');args.extend(ids)
        sql=' FROM jobs j LEFT JOIN attribution t ON t.job_id=j.job_id LEFT JOIN actors a ON a.id=coalesce(j.actor_user_id,t.user_id) LEFT JOIN dispositions d ON j.job_id=d.job_id WHERE '+' AND '.join(where)
        total=con.execute('SELECT count(*)'+sql,args).fetchone()[0]
        pages=max(1,(total+page_size-1)//page_size);page=min(page,pages)
        rows=con.execute("SELECT j.*,coalesce(d.disposition,'enabled') disposition"+sql+' ORDER BY j.created_at DESC,j.job_id LIMIT ? OFFSET ?',(*args,page_size,(page-1)*page_size)).fetchall()
        jobs=[]
        for row in rows:
            value=queue._with_live_progress(queue._public(con,row));value['disposition']=row['disposition'];jobs.append(value)
        return {'jobs':jobs,'total':total,'page':page,'page_size':page_size,'pages':pages}


def manage(actor_id, body):
    action=body.get('action'); ids=body.get('ids'); reason=body.get('reason','')
    if action not in ('disable','delete','enable') or not isinstance(ids,list) or not 1<=len(ids)<=5000 or any(not isinstance(i,str) or not queue._SAFE_JOB_ID.fullmatch(i) for i in ids):
        raise ValueError('Seleziona da 1 a 5000 job e una azione valida')
    if not isinstance(reason,str) or not 3<=len(reason.strip())<=500:raise ValueError('Motivazione obbligatoria (3–500 caratteri)')
    ids=list(dict.fromkeys(ids))
    if type(body.get('preview',False)) is not bool:raise ValueError('preview deve essere booleano')
    filters=body.get('filters',{})
    if not isinstance(filters,dict) or set(filters)-{'search','state','visibility'}:raise ValueError('Filtri non validi')
    # Recheck every selected ID against the actual current search, across pages.
    selected=[]
    for offset in range(0,len(ids),100):
        result=query(**filters,ids=ids[offset:offset+100],page_size=100)
        selected.extend(result['jobs'])
    if {j['job_id'] for j in selected}!=set(ids):raise ValueError('La selezione non corrisponde alla ricerca corrente; aggiorna la lista')
    if any(j['state'] in ('queued','blocked','running') for j in selected):raise ValueError('Annulla e attendi la fine dei job attivi prima di escluderli')
    if any(j['disposition']=='deleted' for j in selected):raise ValueError('Le voci eliminate non possono essere ripristinate')
    now=int(time.time());disposition={'disable':'disabled','delete':'deleted','enable':'enabled'}[action]
    with auth.db() as con:
        tables(con);con.execute('BEGIN IMMEDIATE')
        for job in selected:
            jid=job['job_id']
            current=con.execute('SELECT disposition FROM ai_job_dispositions WHERE queue_job_id=?',(jid,)).fetchone()
            if current and current[0]=='deleted':raise ValueError('La voce è stata eliminata da un altro amministratore; aggiorna la lista')
            linked=uuid.uuid5(uuid.NAMESPACE_URL,'mta-ai-inference:'+jid).hex
            records=con.execute('SELECT * FROM ai_compute_jobs WHERE queue_job_id=? OR id=?',(jid,linked)).fetchall()
            for row in records:
                if row['status']=='running':raise ValueError('Accounting ancora in aggiornamento; riprova')
                if con.execute('SELECT 1 FROM ai_billing_periods WHERE user_id=? AND start_ts<=? AND end_ts>? LIMIT 1',(row['user_id'],row['started_at'],row['started_at'])).fetchone():
                    raise ValueError('Job incluso in un periodo fatturato: serve una rettifica contabile esterna; nessuna voce modificata')
            if body.get('preview'):continue
            con.execute('INSERT INTO ai_job_dispositions VALUES(?,?,?,?,?) ON CONFLICT(queue_job_id) DO UPDATE SET disposition=excluded.disposition,changed_at=excluded.changed_at,actor_id=excluded.actor_id,reason=excluded.reason',(jid,disposition,now,actor_id,reason.strip()))
            con.execute('INSERT INTO ai_job_disposition_audit(queue_job_id,disposition,changed_at,actor_id,reason) VALUES(?,?,?,?,?)',(jid,disposition,now,actor_id,reason.strip()))
            con.execute('UPDATE ai_compute_jobs SET accounting_excluded=? WHERE queue_job_id=? OR id=?',(int(action!='enable'),jid,linked))
    return {'ok':True,'count':len(selected),'preview':bool(body.get('preview')),'accounting_excluded':action!='enable'}
