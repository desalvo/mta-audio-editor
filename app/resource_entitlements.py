"""Per-user subscription access, one-time trials and time-priced quota extensions.

Capacity charges follow assigned quota, not occupied files. All timestamps are
UTC seconds. Old prepaid capacity retains its original period coverage.
"""
import json
import math
import time
import uuid
from . import auth

GIB=1024**3


def init(c):
    c.executescript('''
    CREATE TABLE IF NOT EXISTS resource_user_policy(user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,subscriptions_allowed INTEGER NOT NULL DEFAULT 1,credit_billing INTEGER NOT NULL DEFAULT 0);
    CREATE TABLE IF NOT EXISTS resource_policy_events(id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,effective_at INTEGER NOT NULL,credit_billing INTEGER NOT NULL);
    CREATE TABLE IF NOT EXISTS resource_trial_uses(user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,start INTEGER NOT NULL,end INTEGER NOT NULL);
    CREATE TABLE IF NOT EXISTS resource_next_plans(user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,plan TEXT NOT NULL,effective_at INTEGER NOT NULL,limits TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS resource_quota_events(id TEXT PRIMARY KEY,user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,effective_at INTEGER NOT NULL,quota_bytes INTEGER NOT NULL,free_extra_bytes INTEGER NOT NULL,actor_id INTEGER NOT NULL,reason TEXT NOT NULL);
    CREATE INDEX IF NOT EXISTS resource_quota_user_time ON resource_quota_events(user_id,effective_at);
    CREATE TABLE IF NOT EXISTS resource_storage_debits(user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,through_ts INTEGER NOT NULL,cost_micro INTEGER NOT NULL DEFAULT 0);
    CREATE TABLE IF NOT EXISTS resource_job_modes(job_id TEXT PRIMARY KEY REFERENCES ai_compute_jobs(id) ON DELETE CASCADE,mode TEXT NOT NULL);
    ''')
    cols={r[1] for r in c.execute('PRAGMA table_info(resource_user_policy)')}
    if 'access_required' not in cols:
        c.execute('ALTER TABLE resource_user_policy ADD COLUMN access_required INTEGER NOT NULL DEFAULT 0')


def policy(c,uid):
    row=c.execute('SELECT * FROM resource_user_policy WHERE user_id=?',(uid,)).fetchone()
    return dict(row) if row else {'user_id':uid,'subscriptions_allowed':True,'credit_billing':False,'access_required':False}


def set_policy(uid,body,actor):
    from . import resource_accounts as r
    if not body or set(body)-{'subscriptions_allowed','credit_billing','access_required'} or any(type(v) is not bool for v in body.values()):raise ValueError('Invalid user billing policy')
    with auth.db() as c:
        r.init(c);c.execute('BEGIN IMMEDIATE')
        if not c.execute('SELECT 1 FROM users WHERE id=?',(uid,)).fetchone():raise ValueError('Unknown user')
        current=policy(c,uid);current.update(body)
        role=c.execute('SELECT role FROM users WHERE id=?',(uid,)).fetchone()[0]
        if role=='admin' and (current['access_required'] or current['credit_billing']):raise ValueError('Administrators cannot require paid access')
        current['credit_billing']=False
        if 'credit_billing' in body:body['credit_billing']=False
        if not current['subscriptions_allowed']:current['access_required']=False
        if current['access_required'] or current['credit_billing']:
            from .resource_access import ensure_tariffs
            ensure_tariffs(c)
        if current['credit_billing']!=policy(c,uid)['credit_billing']:body['credit_billing']=bool(current['credit_billing'])
        if 'credit_billing' in body:
            c.execute('INSERT INTO resource_policy_events(user_id,effective_at,credit_billing) VALUES(?,?,?)',(uid,int(time.time()),int(body['credit_billing'])))
        if not current['subscriptions_allowed']:
            stamp=int(time.time())
            c.execute('UPDATE resource_periods SET end=? WHERE user_id=? AND end>?',(stamp,uid,stamp))
            c.execute("UPDATE resource_memberships SET plan=NULL,anchor=?,promo='' WHERE user_id=?",(stamp,uid))
            c.execute('DELETE FROM resource_next_plans WHERE user_id=?',(uid,))
            c.execute('DELETE FROM resource_cancellations WHERE user_id=?',(uid,))
            c.execute('UPDATE resource_job_contracts SET overage=0 WHERE user_id=? AND settled=0',(uid,))
        c.execute('INSERT INTO resource_user_policy(user_id,subscriptions_allowed,credit_billing,access_required) VALUES(?,?,?,?) ON CONFLICT(user_id) DO UPDATE SET subscriptions_allowed=excluded.subscriptions_allowed,credit_billing=excluded.credit_billing,access_required=excluded.access_required',(uid,int(current['subscriptions_allowed']),int(current['credit_billing']),int(current['access_required'])))
        c.execute('INSERT INTO resource_credits VALUES(?,?,?,?,?,?)',(uuid.uuid4().hex,uid,0,actor,'Billing policy: '+json.dumps(body),int(time.time())))
    return r.state(uid)


def begin_trial(c,uid,stamp):
    if c.execute('SELECT 1 FROM resource_trial_uses WHERE user_id=?',(uid,)).fetchone():raise ValueError('Free trial already used')
    end=stamp+7*86400
    c.execute('INSERT INTO resource_trial_uses VALUES(?,?,?)',(uid,stamp,end))
    plan=dict(c.execute("SELECT * FROM resource_plans WHERE code='week'").fetchone())
    c.execute('INSERT OR REPLACE INTO resource_next_plans VALUES(?,?,?,?)',(uid,'week',end,json.dumps(plan)))


def apply_renewal(c,uid,stamp):
    from . import resource_accounts as r
    cancelled=c.execute('SELECT until_ts FROM resource_cancellations WHERE user_id=? AND until_ts<=?',(uid,stamp)).fetchone()
    if cancelled:
        c.execute("UPDATE resource_memberships SET plan=NULL,anchor=?,promo='' WHERE user_id=?",(cancelled[0],uid))
        c.execute('DELETE FROM resource_next_plans WHERE user_id=?',(uid,))
        c.execute('DELETE FROM resource_cancellations WHERE user_id=?',(uid,))
        return
    row=c.execute('SELECT * FROM resource_next_plans WHERE user_id=? AND effective_at<=?',(uid,stamp)).fetchone()
    cfg=c.execute('SELECT enabled FROM resource_config WHERE id=1').fetchone()
    if not row or not cfg or not cfg[0]:return
    cancel=c.execute('SELECT until_ts FROM resource_cancellations WHERE user_id=?',(uid,)).fetchone()
    if cancel and cancel[0]<=row['effective_at']:return
    member=c.execute('SELECT * FROM resource_memberships WHERE user_id=?',(uid,)).fetchone()
    if not member:return
    limits=json.loads(row['limits']);price=limits.pop('price_micro',0)
    limits={k:limits[k] for k in r.RESOURCES}|{'_price_micro':price,'_funded':not price}
    c.execute('UPDATE resource_memberships SET plan=?,anchor=?,promo=? WHERE user_id=?',(row['plan'],row['effective_at'],'',uid))
    c.execute('INSERT OR IGNORE INTO resource_periods VALUES(?,?,?,?,?)',(uid,row['effective_at'],r._boundary(row['effective_at'],row['plan'],1),json.dumps(limits),row['plan']))
    c.execute('DELETE FROM resource_next_plans WHERE user_id=?',(uid,))


def next_plan(uid,code,expected_price):
    from . import resource_accounts as r
    if code not in r.PLANS:raise ValueError('Invalid renewal plan')
    with auth.db() as c:
        r.init(c);c.execute('BEGIN IMMEDIATE');cfg=dict(c.execute('SELECT * FROM resource_config').fetchone())
        if not cfg['enabled'] or not cfg['self_service'] or not policy(c,uid)['subscriptions_allowed']:raise ValueError('Subscriptions are not enabled for this user')
        p=r._period(c,uid,int(time.time()))
        if not p or not p['plan']:raise ValueError('No active subscription')
        plan=dict(c.execute('SELECT * FROM resource_plans WHERE code=?',(code,)).fetchone())
        if plan['price_micro']!=r.number(expected_price,integer=True):raise ValueError('Plan price changed; review current price')
        c.execute('INSERT OR REPLACE INTO resource_next_plans VALUES(?,?,?,?)',(uid,code,p['end'],json.dumps(plan)))
        c.execute('DELETE FROM resource_cancellations WHERE user_id=?',(uid,))
    return r.state(uid)


def _quota_at(c,uid,stamp):
    return c.execute('SELECT * FROM resource_quota_events WHERE user_id=? AND effective_at<=? ORDER BY effective_at DESC,rowid DESC LIMIT 1',(uid,stamp)).fetchone()


def _extension(c,uid,p,stamp):
    if not p or not p['plan']:return {'included_bytes':None,'quota_bytes':None,'paid_bytes':0,'free_bytes':0}
    base=json.loads(p['limits']).get('storage_bytes') or 0
    ev=_quota_at(c,uid,stamp)
    # Existing prepaid purchases remain covered until their original expiry.
    prepaid=c.execute('SELECT coalesce(sum(bytes),0) FROM resource_storage_unlocks WHERE user_id=? AND period_start=? AND created_at<=?',(uid,p['start'],stamp)).fetchone()[0]
    target=max(base+prepaid,ev['quota_bytes']) if ev else base+prepaid
    extra=max(0,target-base-prepaid);free=min(extra,ev['free_extra_bytes']) if ev else 0
    return {'included_bytes':base,'quota_bytes':target,'paid_bytes':extra-free,'free_bytes':free,'prepaid_bytes':prepaid}


def storage_segments(c,uid,start,end):
    """Exact quota/tariff/contract intervals, usable for arbitrary report windows."""
    end=min(end,int(time.time()))
    if start>=end or not c.execute("SELECT 1 FROM sqlite_master WHERE name='resource_quota_events'").fetchone():return []
    periods=[dict(x) for x in c.execute("SELECT * FROM resource_periods WHERE user_id=? AND plan IS NOT NULL AND end>? AND start<? AND json_extract(limits,'$._funded')=1 ORDER BY start",(uid,start,end))]
    tariffs=[dict(x) for x in c.execute("SELECT * FROM ai_resource_price_history WHERE resource='disk_gb_hours' ORDER BY valid_from")]
    services=[dict(row) for row in c.execute('SELECT * FROM resource_credit_service_events ORDER BY effective_at,id')]
    cuts={start,end}
    cuts.update(row['effective_at'] for row in services if start<row['effective_at']<end)
    for p in periods:
        p['start']=max(p['start'],json.loads(p['limits']).get('_funded_at',p['start']))
        cuts.update((max(start,p['start']),min(end,p['end'])))
    cuts.update(x[0] for x in c.execute('SELECT effective_at FROM resource_quota_events WHERE user_id=? AND effective_at>? AND effective_at<?',(uid,start,end)))
    cuts.update(x[0] for x in c.execute('SELECT created_at FROM resource_storage_unlocks WHERE user_id=? AND created_at>? AND created_at<?',(uid,start,end)))
    for row in tariffs:
        for k in ('valid_from','valid_until'):
            if row[k] is not None and start<row[k]<end:cuts.add(row[k])
    midnight=(start//86400+1)*86400
    while midnight<end:cuts.add(midnight);midnight+=86400
    cuts=sorted(cuts);out=[]
    for a,b in zip(cuts,cuts[1:]):
        p=next((p for p in periods if p['start']<=a<p['end']),None)
        if not p:continue
        ext=_extension(c,uid,p,a)
        if not ext['paid_bytes'] and not ext['free_bytes']:continue
        rate=next((x['micro_per_unit'] for x in reversed(tariffs) if x['valid_from']<=a and (x['valid_until'] is None or a<x['valid_until'])),0)
        active=next((bool(row['enabled']) for row in reversed(services) if row['effective_at']<=a),True)
        if not active:rate=0
        gh=ext['paid_bytes']/GIB*(b-a)/3600
        out.append({'start_ts':a,'end_ts':b,'duration_seconds':b-a,'plan':p['plan'],**ext,'gb_hours':gh,'rate_micro_per_gb_hour':rate,'cost_micro':gh*rate})
    return out


def _settle_storage(c,uid,stamp):
    prior=c.execute('SELECT through_ts FROM resource_storage_debits WHERE user_id=?',(uid,)).fetchone()
    stamp=max(stamp,prior[0] if prior else 0)
    first=c.execute('SELECT min(effective_at) FROM resource_quota_events WHERE user_id=?',(uid,)).fetchone()[0]
    first_policy=c.execute('SELECT min(effective_at) FROM resource_policy_events WHERE user_id=?',(uid,)).fetchone()[0]
    if first is None and first_policy is None:return
    starts=[v for v in (first,first_policy) if v is not None]
    cost=round(sum(x['cost_micro'] for x in storage_segments(c,uid,min(starts),stamp))+sum(x['cost_micro'] for x in credit_storage_segments(c,uid,min(starts),stamp)))
    c.execute('INSERT INTO resource_storage_debits VALUES(?,?,?) ON CONFLICT(user_id) DO UPDATE SET through_ts=excluded.through_ts,cost_micro=excluded.cost_micro',(uid,stamp,cost))


def enrich_state(c,uid,s,stamp):
    from . import resource_accounts as r
    _settle_storage(c,uid,stamp)
    ext=_extension(c,uid,s['period'],stamp)
    if s['subscription']:s['limits']['storage_bytes']=ext['quota_bytes']
    s['storage_extension']=ext;s['credits_micro']=r._balance(c,uid)
    s['policy']=policy(c,uid)
    cfg=dict(c.execute('SELECT * FROM resource_config WHERE id=1').fetchone())
    s['credits_enabled']=bool(cfg['enabled'] and cfg['credits_enabled'] and s['policy']['subscriptions_allowed'] and s['subscription'] and s['funded'])
    s['policy']['credit_billing']=s['credits_enabled']
    s['credit_denominations']=json.loads(cfg['credit_denominations'])
    if not s['policy']['subscriptions_allowed']:s['policy']['access_required']=False
    trial=c.execute('SELECT * FROM resource_trial_uses WHERE user_id=?',(uid,)).fetchone()
    s['trial_available']=not bool(trial)
    nxt=c.execute('SELECT * FROM resource_next_plans WHERE user_id=?',(uid,)).fetchone()
    s['next_plan']=dict(nxt) if nxt else None
    if s['next_plan']:s['next_plan']['limits']=json.loads(nxt['limits'])
    return s


def set_storage(uid,quota_bytes,*,actor,free=False,reason='Storage quota changed',owner=False,key=None,max_rate=None):
    from . import resource_accounts as r
    amount=r.number(quota_bytes,integer=True)
    if type(free) is not bool or not isinstance(reason,str) or not 3<=len(reason)<=300:raise ValueError('Invalid storage allocation')
    if owner and free:raise ValueError('Only administrators can grant free storage')
    request_id=('capacity:'+key) if key else uuid.uuid4().hex
    with auth.db() as c:
        r.init(c);c.execute('BEGIN IMMEDIATE');stamp=int(time.time());s=r._state(c,uid,0,stamp)
        if not s['subscription'] or not s['funded']:raise ValueError('An active funded subscription is required')
        if not s['credits_enabled'] and not free and amount>s['limits']['storage_bytes']:raise ValueError('Enable subscription credits or grant the storage extension free of charge')
        ext=s['storage_extension'];floor=ext['included_bytes']+ext['prepaid_bytes']
        if owner:floor+=ext['free_bytes']
        if amount<floor:raise ValueError('Storage quota cannot be below included and free capacity')
        rate=__import__('app.ai_billing',fromlist=['prices']).prices(_connection=c).get('disk_gb_hours',0)
        if max_rate is not None and rate>r.number(max_rate,integer=True):raise ValueError('Storage quote changed; review current tariff')
        if owner and amount>ext['quota_bytes'] and (s['credits_micro']<=0 or rate<=0):raise ValueError('Credits and an ordinary storage tariff are required')
        prior=c.execute('SELECT * FROM resource_quota_events WHERE id=?',(request_id,)).fetchone()
        if prior:
            if prior['user_id']!=uid or prior['quota_bytes']!=amount:raise ValueError('Conflicting storage retry')
        else:
            free_amount=max(0,amount-ext['included_bytes']-ext['prepaid_bytes']) if free else (ext['free_bytes'] if owner else 0)
            c.execute('INSERT INTO resource_quota_events VALUES(?,?,?,?,?,?,?)',(request_id,uid,stamp,amount,free_amount,actor,reason))
    return r.state(uid)


def extend_storage(uid,gb,key,max_cost=None):
    from . import resource_accounts as r
    gb=r.number(gb)
    if not 0<gb<=100000 or not isinstance(key,str) or not 8<=len(key)<=80:raise ValueError('Invalid storage request')
    # Compatibility: max_cost now bounds the hourly tariff, never an upfront fee.
    with auth.db() as c:
        r.init(c)
        prior=c.execute('SELECT * FROM resource_quota_events WHERE id=?',('capacity:'+key,)).fetchone()
        if prior:
            if prior['user_id']!=uid or prior['reason']!='Extend storage: '+str(gb):raise ValueError('Conflicting storage retry')
            return r._state(c,uid,0,int(time.time()))
    s=r.state(uid)
    if not s['subscription']:raise ValueError('An active funded subscription is required')
    return set_storage(uid,s['limits']['storage_bytes']+int(gb*GIB),actor=uid,owner=True,key=key,max_rate=max_cost,reason='Extend storage: '+str(gb))


def admit_credit(c,uid,jid,stamp):
    from . import resource_accounts as r
    if r._balance(c,uid)<=0 and not r.continuing_pool(c,uid,jid):raise ValueError('Resource credits exhausted')
    if c.execute("SELECT 1 FROM resource_job_contracts r JOIN ai_compute_jobs j ON j.id=r.job_id WHERE r.user_id=? AND j.status='running' AND j.id!=? AND (j.queue_job_id IS NULL OR j.queue_job_id IS NOT (SELECT queue_job_id FROM ai_compute_jobs WHERE id=?))",(uid,jid,jid)).fetchone():raise ValueError('Another quota-controlled AI job is running')
    p=r._period(c,uid,stamp)
    if not p:
        start=stamp//86400*86400
        limits=json.dumps(dict.fromkeys(r.RESOURCES)|{'_funded':True})
        c.execute('INSERT OR IGNORE INTO resource_periods VALUES(?,?,?,?,NULL)',(uid,start,start+86400,limits))
    else:start=p['start']
    c.execute('INSERT INTO resource_job_modes VALUES(?,?)',(jid,'credit'))
    c.execute('INSERT INTO resource_job_contracts(job_id,user_id,period_start,subscription,overage) VALUES(?,?,?,0,1)',(jid,uid,start))


def storage_report(uid,start,end):
    from . import resource_accounts as r
    if type(start) not in (int,float) or type(end) not in (int,float) or not math.isfinite(start) or not math.isfinite(end) or not 0<=start<end<=time.time()+1:raise ValueError('Invalid storage reporting interval')
    with auth.db() as c:
        r.init(c);c.execute('BEGIN IMMEDIATE');r._state(c,uid,0,int(time.time()))
        segments=storage_segments(c,uid,int(start),int(end))
    return {'start_ts':int(start),'end_ts':int(end),'basis':'assigned-quota-over-included','segments':segments,'gb_hours':sum(s['gb_hours'] for s in segments),'duration_seconds':sum(s['duration_seconds'] for s in segments if s['paid_bytes']),'cost_micro':round(sum(s['cost_micro'] for s in segments)),'currency':'EUR'}



def ensure_periods(c,uid,stamp):
    """Materialize elapsed quota contracts before integrating assigned capacity."""
    from . import resource_accounts as r
    if not c.execute('SELECT 1 FROM resource_quota_events WHERE user_id=?',(uid,)).fetchone():return
    row=c.execute('SELECT max(end) FROM resource_periods WHERE user_id=?',(uid,)).fetchone()
    edge=row[0] if row else None
    for _ in range(36600):
        if edge is None or edge>stamp:break
        _settle_storage(c,uid,edge)
        p=r._period(c,uid,edge)
        if not p or p['end']<=edge:break
        edge=p['end']



def credit_storage_segments(c,uid,start,end):
    """Ordinary occupied-storage credit billing only during explicit admin opt-in."""
    end=min(end,int(time.time()))
    events=[dict(x) for x in c.execute('SELECT * FROM resource_policy_events WHERE user_id=? ORDER BY effective_at,id',(uid,))]
    if not events or start>=end:return []
    samples=[dict(x) for x in c.execute('SELECT sampled_at,bytes_used FROM ai_persistent_storage_samples WHERE user_id=? AND sampled_at<=? ORDER BY sampled_at',(uid,end))]
    tariffs=[dict(x) for x in c.execute("SELECT * FROM ai_resource_price_history WHERE resource='disk_gb_hours' ORDER BY valid_from")]
    periods=[dict(x) for x in c.execute('SELECT start,end FROM resource_periods WHERE user_id=? AND plan IS NOT NULL AND end>? AND start<?',(uid,start,end))]
    out=[]
    for left,right in zip(samples,samples[1:]):
        if right['sampled_at']-left['sampled_at']>26*3600:continue
        a,b=max(start,left['sampled_at']),min(end,right['sampled_at'])
        if a>=b:continue
        cuts={a,b}
        for x in events:
            if a<x['effective_at']<b:cuts.add(x['effective_at'])
        for x in tariffs:
            for key in ('valid_from','valid_until'):
                if x[key] is not None and a<x[key]<b:cuts.add(x[key])
        for x in periods:
            for key in ('start','end'):
                if a<x[key]<b:cuts.add(x[key])
        cuts=sorted(cuts)
        for x,y in zip(cuts,cuts[1:]):
            mode=next((e['credit_billing'] for e in reversed(events) if e['effective_at']<=x),0)
            if not mode or any(p['start']<=x<p['end'] for p in periods):continue
            rate=next((t['micro_per_unit'] for t in reversed(tariffs) if t['valid_from']<=x and (t['valid_until'] is None or x<t['valid_until'])),0)
            out.append({'start_ts':x,'end_ts':y,'gb_hours':left['bytes_used']/GIB*(y-x)/3600,'cost_micro':left['bytes_used']/GIB*(y-x)/3600*rate})
    return out



def admit_free(c,uid,jid,stamp):
    from . import resource_accounts as r
    start=stamp//86400*86400
    c.execute('INSERT OR IGNORE INTO resource_periods VALUES(?,?,?,?,NULL)',(uid,start,start+86400,json.dumps(dict.fromkeys(r.RESOURCES)|{'_funded':True})))
    c.execute('INSERT INTO resource_job_modes VALUES(?,?)',(jid,'free'))
    c.execute('INSERT INTO resource_job_contracts(job_id,user_id,period_start,subscription,overage) VALUES(?,?,?,0,0)',(jid,uid,start))
