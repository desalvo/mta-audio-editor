"""Period quotas, operator-managed subscriptions and auditable prepaid credits.

No payment processor is implied. Credits are EUR millionths. Periods use UTC;
calendar subscriptions retain the original day anchor, including leap years.
"""
import calendar
import datetime as dt
import html
import json
import math
import time
import uuid
from . import auth

RESOURCES=('cpu_seconds','gpu_seconds','storage_bytes')
PLANS={'day':(1,0,1),'week':(7,0,1.25),'month':(30,1,1.5),'quarter':(90,3,1.75),'year':(365,12,2)}


def init(c):
    from .ai_billing import _init
    _init(c)
    c.executescript('''
    CREATE TABLE IF NOT EXISTS resource_config(id INTEGER PRIMARY KEY,enabled INTEGER NOT NULL DEFAULT 0,self_service INTEGER NOT NULL DEFAULT 0);
    INSERT OR IGNORE INTO resource_config(id) VALUES(1);
    CREATE TABLE IF NOT EXISTS resource_plans(code TEXT PRIMARY KEY,cpu_seconds REAL NOT NULL,gpu_seconds REAL NOT NULL,storage_bytes INTEGER NOT NULL,price_micro INTEGER NOT NULL DEFAULT 0);
    CREATE TABLE IF NOT EXISTS resource_memberships(user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,plan TEXT,anchor INTEGER NOT NULL,cpu_seconds REAL,gpu_seconds REAL,storage_bytes INTEGER,promo TEXT NOT NULL DEFAULT '',overage INTEGER NOT NULL DEFAULT 0);
    CREATE TABLE IF NOT EXISTS resource_cancellations(user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,until_ts INTEGER NOT NULL);
    CREATE TABLE IF NOT EXISTS resource_periods(user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,start INTEGER NOT NULL,end INTEGER NOT NULL,limits TEXT NOT NULL,plan TEXT,PRIMARY KEY(user_id,start));
    CREATE TABLE IF NOT EXISTS resource_credits(id TEXT PRIMARY KEY,user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,delta_micro INTEGER NOT NULL,actor_id INTEGER,reason TEXT NOT NULL,created_at INTEGER NOT NULL);
    CREATE TABLE IF NOT EXISTS resource_job_contracts(job_id TEXT PRIMARY KEY REFERENCES ai_compute_jobs(id) ON DELETE CASCADE,user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,period_start INTEGER NOT NULL,subscription INTEGER NOT NULL,overage INTEGER NOT NULL DEFAULT 0,settled INTEGER NOT NULL DEFAULT 0,charge_micro INTEGER NOT NULL DEFAULT 0);
    CREATE TABLE IF NOT EXISTS resource_storage_samples(user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,day TEXT NOT NULL,bytes INTEGER NOT NULL,PRIMARY KEY(user_id,day));
    CREATE TABLE IF NOT EXISTS resource_storage_unlocks(id TEXT PRIMARY KEY,user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,period_start INTEGER NOT NULL,bytes INTEGER NOT NULL,cost_micro INTEGER NOT NULL,created_at INTEGER NOT NULL);
    CREATE TABLE IF NOT EXISTS resource_notices(id TEXT PRIMARY KEY,user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,payload TEXT NOT NULL,sent INTEGER NOT NULL DEFAULT 0,lease INTEGER NOT NULL DEFAULT 0,attempts INTEGER NOT NULL DEFAULT 0);
    ''')
    for key,(days,months,factor) in PLANS.items():
        c.execute('INSERT OR IGNORE INTO resource_plans(code,cpu_seconds,gpu_seconds,storage_bytes) VALUES(?,?,?,?)',(key,4*3600*days*factor,4*3600*days*factor,int(5*1024**3*factor)))
    c.execute('CREATE TABLE IF NOT EXISTS resource_job_budgets(job_id TEXT PRIMARY KEY REFERENCES ai_compute_jobs(id) ON DELETE CASCADE,budget_micro INTEGER NOT NULL,gross_micro INTEGER NOT NULL DEFAULT 0,waived_micro INTEGER NOT NULL DEFAULT 0,rates_json TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS resource_spending_pools(id TEXT PRIMARY KEY,user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,ceiling_micro INTEGER NOT NULL,spent_micro INTEGER NOT NULL DEFAULT 0)')
    if 'pool_id' not in {r[1] for r in c.execute('PRAGMA table_info(resource_job_budgets)')}:
        c.execute('ALTER TABLE resource_job_budgets ADD COLUMN pool_id TEXT')
    if 'rates_json' not in {r[1] for r in c.execute('PRAGMA table_info(resource_job_budgets)')}:
        c.execute('ALTER TABLE resource_job_budgets ADD COLUMN rates_json TEXT')
    if 'credit_value_micro' not in {r[1] for r in c.execute('PRAGMA table_info(resource_config)')}:
        c.execute('ALTER TABLE resource_config ADD COLUMN credit_value_micro INTEGER NOT NULL DEFAULT 100000')
    cols={row[1] for row in c.execute('PRAGMA table_info(resource_config)')}
    credits_migration='credits_enabled' not in cols
    if credits_migration:c.execute('ALTER TABLE resource_config ADD COLUMN credits_enabled INTEGER NOT NULL DEFAULT 0')
    if 'credit_denominations' not in cols:c.execute("ALTER TABLE resource_config ADD COLUMN credit_denominations TEXT NOT NULL DEFAULT '[500,1000,2000,5000]'")
    c.execute('CREATE TABLE IF NOT EXISTS resource_credit_service_events(id INTEGER PRIMARY KEY AUTOINCREMENT,effective_at INTEGER NOT NULL,enabled INTEGER NOT NULL)')
    if not c.execute('SELECT 1 FROM resource_credit_service_events').fetchone():c.execute('INSERT INTO resource_credit_service_events(effective_at,enabled) VALUES(?,?)',(int(time.time()),int(c.execute('SELECT credits_enabled FROM resource_config WHERE id=1').fetchone()[0])))
    from .resource_entitlements import init as init_entitlements
    init_entitlements(c)
    if credits_migration:
        c.execute('INSERT INTO resource_policy_events(user_id,effective_at,credit_billing) SELECT user_id,?,0 FROM resource_user_policy WHERE credit_billing=1',(int(time.time()),))
        c.execute('UPDATE resource_user_policy SET credit_billing=0')
    c.execute("CREATE TABLE IF NOT EXISTS resource_plan_charges(user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,period_start INTEGER NOT NULL,amount_micro INTEGER NOT NULL,status TEXT NOT NULL DEFAULT 'due',PRIMARY KEY(user_id,period_start))")
    from .resource_contracts import init as init_contracts
    init_contracts(c)
    # Jobs admitted before this upgrade receive a conservative remaining-wallet
    # ceiling. Already settled historical charges are never rewritten.
    for row in c.execute('SELECT r.job_id,r.user_id FROM resource_job_contracts r LEFT JOIN resource_job_budgets b ON b.job_id=r.job_id WHERE r.settled=0 AND b.job_id IS NULL').fetchall():
        reserve_budget(c,row['user_id'],row['job_id'])
    c.commit()


def number(v,*,integer=False):
    if type(v) not in (int,float) or not math.isfinite(v) or v<0 or v>1e15 or (integer and int(v)!=v):raise ValueError('Invalid resource amount')
    return int(v) if integer else float(v)


def config():
    with auth.db() as c:
        init(c)
        from .resource_access import tariff_view
        return {**dict(c.execute('SELECT * FROM resource_config WHERE id=1').fetchone()),'plans':[dict(r) for r in c.execute('SELECT * FROM resource_plans')],'tariffs':tariff_view(c)}


def _boundary(anchor,code,n):
    days,months,_=PLANS[code]
    if not months:return anchor+n*days*86400
    d=dt.datetime.fromtimestamp(anchor,dt.timezone.utc);m=d.year*12+d.month-1+n*months;y,m=divmod(m,12);m+=1
    return int(d.replace(year=y,month=m,day=min(d.day,calendar.monthrange(y,m)[1])).timestamp())


def _period(c,uid,at):
    from .resource_entitlements import apply_renewal
    apply_renewal(c,uid,at)
    member=c.execute('SELECT * FROM resource_memberships WHERE user_id=?',(uid,)).fetchone()
    if not member:return None
    cancelled=c.execute('SELECT until_ts FROM resource_cancellations WHERE user_id=?',(uid,)).fetchone()
    if cancelled and at>=cancelled[0]:return None
    enabled=c.execute('SELECT enabled FROM resource_config WHERE id=1').fetchone()[0]
    code=member['plan'] if member['plan'] and enabled else None
    if member['plan'] and not enabled:
        prior=c.execute('SELECT * FROM resource_periods WHERE user_id=? AND start<=? AND end>? AND plan IS NOT NULL ORDER BY start DESC LIMIT 1',(uid,at,at)).fetchone()
        return dict(prior) if prior else None
    kind=('week' if code=='trial' else code) or 'day';anchor=member['anchor']
    if at<anchor:return None
    days,months,_=PLANS[kind]
    n=max(0,int((at-anchor)//(days*86400)))
    while _boundary(anchor,kind,n)>at:n-=1
    while _boundary(anchor,kind,n+1)<=at:n+=1
    start,end=_boundary(anchor,kind,n),_boundary(anchor,kind,n+1)
    prior=c.execute('SELECT * FROM resource_periods WHERE user_id=? AND start=?',(uid,start)).fetchone()
    if prior:
        p=dict(prior)
        _fund(c,p,member)
        return p
    limits=dict(c.execute('SELECT * FROM resource_plans WHERE code=?',('week' if code=='trial' else code,)).fetchone()) if code else dict(member)
    price=limits.get('price_micro',0) if code and code!='trial' and not member['promo'] else 0
    from .resource_entitlements import policy
    if not policy(c,uid)['subscriptions_allowed']:price=0
    limits={**{k:limits.get(k) for k in RESOURCES},'_price_micro':price,'_funded':not price}
    c.execute('INSERT INTO resource_periods VALUES(?,?,?,?,?)',(uid,start,end,json.dumps(limits),code))
    p={'user_id':uid,'start':start,'end':end,'limits':json.dumps(limits),'plan':code}
    _fund(c,p,member)
    return p


def _used(c,uid,start,end,exclude_job=None):
    exists=c.execute("SELECT 1 FROM sqlite_master WHERE name='ai_compute_jobs'").fetchone()
    result={'cpu_seconds':0.,'gpu_seconds':0.}
    if exists:
        for r in c.execute("SELECT id,usage_json,resource_source FROM ai_compute_jobs WHERE user_id=? AND started_at>=? AND started_at<? AND accounting_excluded=0",(uid,start,end)):
            if r['id']==exclude_job:continue
            values=_counters(c,r)
            for key in result:result[key]+=values.get(key,0)
    return result


def _balance(c,uid):
    value=c.execute('SELECT coalesce(sum(delta_micro),0) FROM resource_credits WHERE user_id=?',(uid,)).fetchone()[0]
    if c.execute("SELECT 1 FROM sqlite_master WHERE name='ai_compute_jobs'").fetchone():
        value-=c.execute('SELECT coalesce(sum(r.charge_micro),0) FROM resource_job_contracts r JOIN ai_compute_jobs j ON j.id=r.job_id WHERE r.user_id=? AND j.accounting_excluded=0',(uid,)).fetchone()[0]
    if c.execute("SELECT 1 FROM sqlite_master WHERE name='resource_storage_debits'").fetchone():
        value-=(c.execute('SELECT cost_micro FROM resource_storage_debits WHERE user_id=?',(uid,)).fetchone() or [0])[0]
    return value


def _state(c,uid,used_storage,at):
    from .resource_entitlements import _settle_storage,ensure_periods
    _settle_storage(c,uid,at)
    ensure_periods(c,uid,at)
    p=_period(c,uid,at);user=c.execute('SELECT role,workspace_quota_bytes,workspace_quota_explicit FROM users WHERE id=?',(uid,)).fetchone()
    if not user:raise ValueError('Unknown user')
    member=c.execute('SELECT * FROM resource_memberships WHERE user_id=?',(uid,)).fetchone()
    from .resource_contracts import effective
    raw,included=effective(c,uid,p,at) if p else ({},{})
    limits={k:raw.get(k) for k in RESOURCES}
    if not p:limits['storage_bytes']=(int(user['workspace_quota_bytes'] or 0) or None) if user['role']!='admin' or user['workspace_quota_explicit'] else None
    if p:
        extra=c.execute('SELECT coalesce(sum(bytes),0) FROM resource_storage_unlocks WHERE user_id=? AND period_start=?',(uid,p['start'])).fetchone()[0]
        if limits['storage_bytes'] is not None:limits['storage_bytes']+=extra
    used=_used(c,uid,p['start'],p['end']) if p else _used(c,uid,max(0,at-30*86400),at+1)
    used['storage_bytes']=used_storage
    from .resource_entitlements import enrich_state
    result={'enabled':bool(c.execute('SELECT enabled FROM resource_config').fetchone()[0]),'period':p,'limits':limits,'used':used,'credits_micro':_balance(c,uid),'overage':bool(member and member['overage']),'promo':member['promo'] if member else '', 'subscription':p['plan'] if p else None,'included_compute':included,'funded':raw.get('_funded',True),'renewal_stops_at':(c.execute('SELECT until_ts FROM resource_cancellations WHERE user_id=?',(uid,)).fetchone() or [None])[0]}
    result=enrich_state(c,uid,result,at)
    from .resource_access import access_state
    result['access']=access_state(result,user['role'])
    result['credit_value_micro']=c.execute('SELECT credit_value_micro FROM resource_config WHERE id=1').fetchone()[0]
    result['credits']=result['credits_micro']/result['credit_value_micro']
    return result


def state(uid,used_storage=0,*,at=None):
    with auth.db() as c:
        init(c);c.execute('BEGIN IMMEDIATE');return _state(c,uid,used_storage,int(time.time() if at is None else at))


def configure(body):
    if set(body)-{'enabled','self_service','plans','credit_value_micro','credits_enabled','credit_denominations'}:raise ValueError('Invalid subscription setting')
    with auth.db() as c:
        init(c);c.execute('BEGIN IMMEDIATE')
        for key in ('enabled','self_service','credits_enabled'):
            if key in body:
                if type(body[key]) is not bool:raise ValueError('Boolean required')
                c.execute({'enabled':'UPDATE resource_config SET enabled=?','self_service':'UPDATE resource_config SET self_service=?','credits_enabled':'UPDATE resource_config SET credits_enabled=?'}[key],(int(body[key]),))
        if {'enabled','credits_enabled'}&set(body):
            cfg=c.execute('SELECT enabled,credits_enabled FROM resource_config WHERE id=1').fetchone()
            c.execute('INSERT INTO resource_credit_service_events(effective_at,enabled) VALUES(?,?)',(int(time.time()),int(bool(cfg[0] and cfg[1]))))
        if 'credit_denominations' in body:
            denominations=body['credit_denominations']
            if not isinstance(denominations,list) or not 1<=len(denominations)<=20 or any(type(v) is not int or not 100<=v<=100000 for v in denominations) or len(set(denominations))!=len(denominations):raise ValueError('Credit denominations must be unique EUR cent amounts between 100 and 100000')
            c.execute('UPDATE resource_config SET credit_denominations=? WHERE id=1',(json.dumps(sorted(denominations)),))
        if 'credit_value_micro' in body:
            value=number(body['credit_value_micro'],integer=True)
            if not value:raise ValueError('Credit value must be positive')
            c.execute('UPDATE resource_config SET credit_value_micro=? WHERE id=1',(value,))
        if body.get('enabled'):
            from .resource_access import ensure_tariffs
            ensure_tariffs(c)
        for p in body.get('plans',[]):
            if set(p)!={'code','cpu_seconds','gpu_seconds','storage_bytes','price_micro'} or p['code'] not in PLANS:raise ValueError('Invalid plan')
            c.execute('UPDATE resource_plans SET cpu_seconds=?,gpu_seconds=?,storage_bytes=?,price_micro=? WHERE code=?',(number(p['cpu_seconds']),number(p['gpu_seconds']),number(p['storage_bytes'],integer=True),number(p['price_micro'],integer=True),p['code']))
    return config()


def assign(uid,body,actor,*,self_service=False,expected_price=None,next_plan=None,next_price=None):
    if set(body)-{'plan','cpu_seconds','gpu_seconds','storage_bytes','promo','overage'}:raise ValueError('Invalid quota setting')
    plan=body.get('plan')
    if plan is not None and plan not in (*PLANS,'trial'):raise ValueError('Invalid plan')
    with auth.db() as c:
        init(c);c.execute('BEGIN IMMEDIATE')
        if not c.execute('SELECT 1 FROM users WHERE id=?',(uid,)).fetchone():raise ValueError('Unknown user')
        if self_service:
            cfg=dict(c.execute('SELECT * FROM resource_config').fetchone());price=c.execute('SELECT price_micro FROM resource_plans WHERE code=?',('week' if plan=='trial' else plan,)).fetchone()
            from .resource_entitlements import policy
            if not policy(c,uid)['subscriptions_allowed']:raise ValueError('Subscriptions are not enabled for this user')
            if plan=='trial':price=[0]
            if not cfg['enabled'] or not cfg['self_service'] or not price:raise ValueError('Self-service subscription is disabled')
            if number(expected_price,integer=True)!=price[0]:raise ValueError('Plan price changed; review current price')
            if c.execute('SELECT 1 FROM resource_periods WHERE user_id=? AND plan IS NOT NULL AND end>?',(uid,int(time.time()))).fetchone():raise ValueError('A subscription period is already active')
        # A new contract starts now. Existing contract evidence is immutable.
        stamp=int(time.time());prior=c.execute('SELECT 1 FROM resource_periods WHERE user_id=? AND start=?',(uid,stamp)).fetchone()
        if prior:raise ValueError('Wait one second before replacing this contract')
        c.execute('UPDATE resource_periods SET end=? WHERE user_id=? AND end>?',(stamp,uid,stamp))
        values=[None if body.get(k) is None else number(body[k],integer=k=='storage_bytes') for k in RESOURCES]
        if 'storage_bytes' not in body:values[2]=c.execute('SELECT workspace_quota_bytes FROM users WHERE id=?',(uid,)).fetchone()[0] or None
        c.execute('DELETE FROM resource_cancellations WHERE user_id=?',(uid,))
        promo=body.get('promo','')
        if not isinstance(promo,str) or len(promo)>300 or type(body.get('overage',False)) is not bool:raise ValueError('Invalid promotion or overage')
        c.execute('INSERT INTO resource_memberships VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(user_id) DO UPDATE SET plan=excluded.plan,anchor=excluded.anchor,cpu_seconds=excluded.cpu_seconds,gpu_seconds=excluded.gpu_seconds,storage_bytes=excluded.storage_bytes,promo=excluded.promo,overage=excluded.overage',(uid,plan,stamp,*values,promo,int(body.get('overage',False))))
        c.execute('DELETE FROM resource_next_plans WHERE user_id=?',(uid,))
        if plan=='trial':
            from .resource_entitlements import begin_trial
            begin_trial(c,uid,stamp)
            if next_plan is not None:
                chosen=dict(c.execute('SELECT * FROM resource_plans WHERE code=?',(next_plan,)).fetchone())
                if chosen['price_micro']!=number(next_price,integer=True):raise ValueError('Plan price changed; review current price')
                c.execute('UPDATE resource_next_plans SET plan=?,limits=? WHERE user_id=?',(next_plan,json.dumps(chosen),uid))
        _period(c,uid,stamp)
        c.execute('INSERT INTO resource_credits VALUES(?,?,?,?,?,?)',(uuid.uuid4().hex,uid,0,actor,'Contract assigned: '+str(plan)+' '+promo,stamp))
    return state(uid)


def grant(uid,amount,reason,actor,key):
    amount=number(amount,integer=True)
    if not amount or not isinstance(reason,str) or not 3<=len(reason)<=300 or not isinstance(key,str) or not 8<=len(key)<=80:raise ValueError('Amount, reason and unique request ID required')
    key='grant:'+key
    with auth.db() as c:
        init(c);c.execute('BEGIN IMMEDIATE')
        if not _state(c,uid,0,int(time.time()))['credits_enabled']:raise ValueError('Credits require an enabled credit service and an active subscription for this user')
        prior=c.execute('SELECT * FROM resource_credits WHERE id=?',(key,)).fetchone()
        if prior:
            if (prior['user_id'],prior['delta_micro'],prior['reason'])!=(uid,amount,reason):raise ValueError('Conflicting credit retry')
        else:c.execute('INSERT INTO resource_credits VALUES(?,?,?,?,?,?)',(key,uid,amount,actor,reason,int(time.time())))
    return state(uid)


def admit(c,uid,jid,stamp):
    """Called inside the ledger admission transaction, serializing limited users."""
    if not has_limits(uid,c):return
    from .resource_entitlements import policy,admit_credit
    mode=policy(c,uid)
    s=_state(c,uid,0,stamp);p=s['period']
    mode=s['policy']
    continuation=continuing_pool(c,uid,jid)
    if s['access']['blocked'] and not continuation:raise ValueError('SUBSCRIPTION_REQUIRED: An active subscription is required; open /account#subscriptions or contact the administrator')
    if not p:
        if mode['credit_billing']:
            admit_credit(c,uid,jid,stamp);reserve_budget(c,uid,jid);return
        from .resource_entitlements import admit_free
        admit_free(c,uid,jid,stamp);reserve_budget(c,uid,jid);return
    if not s['funded']:raise ValueError('Subscription is not active; contact the administrator')
    if c.execute('SELECT 1 FROM resource_job_contracts r JOIN ai_compute_jobs j ON j.id=r.job_id WHERE r.user_id=? AND j.status=\'running\' AND j.id!=? AND (j.queue_job_id IS NULL OR j.queue_job_id IS NOT (SELECT queue_job_id FROM ai_compute_jobs WHERE id=?))',(uid,jid,jid)).fetchone():raise ValueError('Another quota-controlled AI job is running')
    from .ai_billing import prices
    rates=prices(_connection=c)
    for key in ('cpu_seconds','gpu_seconds'):
        limit=s['limits'][key]
        if s['subscription'] and s['included_compute'].get(key) is not None:limit=min(limit,s['included_compute'][key]) if limit is not None else s['included_compute'][key]
        if limit is not None and s['used'][key]>=limit:
            if not (continuation and s['subscription'] and s['overage']) and (not s['subscription'] or not s['overage'] or not mode['credit_billing'] or s['credits_micro']<=0 or rates.get(key,0)<=0):raise ValueError('Resource quota exceeded: '+key)
    if not s['subscription'] and mode['credit_billing']:
        admit_credit(c,uid,jid,stamp);reserve_budget(c,uid,jid);return
    c.execute('INSERT INTO resource_job_modes VALUES(?,?)',(jid,'subscription' if s['subscription'] else 'free'))
    c.execute('INSERT INTO resource_job_contracts(job_id,user_id,period_start,subscription,overage) VALUES(?,?,?,?,?)',(jid,uid,p['start'],int(bool(p['plan'])),int(s['overage'] and mode['credit_billing'])))
    reserve_budget(c,uid,jid)
    # Starting with no credits does not buy unlimited free overages. A queue job
    # that initially had credits keeps its authorization across all worker steps.
    if not continuing_pool(c,uid,jid):
        c.execute('UPDATE resource_job_contracts SET overage=0 WHERE job_id=?',(jid,))


def settle(c,jid,values):
    if not c.execute("SELECT 1 FROM sqlite_master WHERE name='resource_job_contracts'").fetchone():return
    contract=c.execute('SELECT * FROM resource_job_contracts WHERE job_id=?',(jid,)).fetchone()
    if not contract or contract['settled']:return
    p=c.execute('SELECT * FROM resource_periods WHERE user_id=? AND start=?',(contract['user_id'],contract['period_start'])).fetchone();limits=json.loads(p['limits'])
    used=_used(c,contract['user_id'],p['start'],p['end']);cost=0
    from .ai_billing import prices
    job=c.execute('SELECT started_at FROM ai_compute_jobs WHERE id=?',(jid,)).fetchone();rates=prices(at=job['started_at'],_connection=c)
    quote=c.execute('SELECT rates_json FROM resource_job_budgets WHERE job_id=?',(jid,)).fetchone()
    if quote and quote[0]:rates=json.loads(quote[0])
    included=c.execute('SELECT included_json FROM resource_job_budgets WHERE job_id=?',(jid,)).fetchone()
    if included and included[0]:limits.update(json.loads(included[0]))
    mode=c.execute('SELECT mode FROM resource_job_modes WHERE job_id=?',(jid,)).fetchone() if c.execute("SELECT 1 FROM sqlite_master WHERE name='resource_job_modes'").fetchone() else None
    if mode and mode[0]=='credit':
        cost=sum(round(values.get(key,0)*rates.get(key,0)) for key in ('cpu_seconds','gpu_seconds'))
    elif contract['subscription'] and contract['overage']:
        for key in ('cpu_seconds','gpu_seconds'):
            if limits[key] is None:continue
            qty=values.get(key,0);over=max(0,used[key]-limits[key])-max(0,used[key]-qty-limits[key])
            cost+=round(over*rates.get(key,0))
    budget=c.execute('SELECT budget_micro,pool_id FROM resource_job_budgets WHERE job_id=?',(jid,)).fetchone()
    if budget is not None:
        gross=cost;cost=min(cost,budget[0],max(0,_balance(c,contract['user_id'])))
        cfg=c.execute('SELECT credits_enabled FROM resource_config WHERE id=1').fetchone()
        allowed=c.execute('SELECT subscriptions_allowed FROM resource_user_policy WHERE user_id=?',(contract['user_id'],)).fetchone()
        if not cfg[0] or (allowed and not allowed[0]):cost=0
        if budget['pool_id']:
            pool=c.execute('SELECT ceiling_micro,spent_micro FROM resource_spending_pools WHERE id=?',(budget['pool_id'],)).fetchone()
            cost=min(cost,max(0,pool['ceiling_micro']-pool['spent_micro']))
            c.execute('UPDATE resource_spending_pools SET spent_micro=spent_micro+? WHERE id=?',(cost,budget['pool_id']))
        c.execute('UPDATE resource_job_budgets SET gross_micro=?,waived_micro=? WHERE job_id=?',(gross,gross-cost,jid))
    c.execute('UPDATE resource_job_contracts SET settled=1,charge_micro=? WHERE job_id=?',(cost,jid))


def checkpoint(uid,jid,counters):
    from .ai_compute_diagnostics import store
    with auth.db() as c:
        previous={}
        if c.execute("SELECT 1 FROM sqlite_master WHERE name='ai_compute_job_diagnostics'").fetchone():
            row=c.execute('SELECT payload FROM ai_compute_job_diagnostics WHERE job_id=?',(jid,)).fetchone()
            if row:previous=json.loads(row[0])
    for key in ('cpu_seconds_estimated','gpu_seconds_estimated'):
        val=counters.get(key)
        if type(val) in (int,float) and math.isfinite(val) and 0<=val<1e18:previous[key]=max(previous.get(key,0),val)
    store(jid,previous)
    s=state(uid);p=s['period']
    with auth.db() as c:
        contract=c.execute('SELECT * FROM resource_job_contracts WHERE job_id=?',(jid,)).fetchone()
        if contract:
            prior=c.execute('SELECT * FROM resource_periods WHERE user_id=? AND start=?',(uid,contract['period_start'])).fetchone()
            p=dict(prior);s['subscription']=p['plan']
            s['used']=_used(c,uid,prior['start'],prior['end'],exclude_job=jid);s['limits']={k:json.loads(prior['limits']).get(k) for k in RESOURCES};s['overage']=bool(contract['overage'])
        mode=c.execute('SELECT mode FROM resource_job_modes WHERE job_id=?',(jid,)).fetchone()
        credit_mode=bool(mode and mode[0]=='credit')
    if not p and not credit_mode:return False
    for key in ('cpu_seconds','gpu_seconds'):
        limit=s['limits'][key];live=counters.get(key+'_estimated',0)
        if type(live) not in (int,float) or not math.isfinite(live) or live<0:continue
        if credit_mode:
            # An unfunded plan is not an included allowance: this admission pays
            # full usage from credits. Manual (non-plan) quotas still apply.
            if not p.get('plan') and limit is not None and s['used'][key]+live>=limit:return True
            continue
        if limit is not None and s['used'][key]+live>=limit:
            if not credit_mode and (not s['subscription'] or not s['overage']):return True
    if s['period'] and p and s['period']['start']==p['start']:sample(uid,0)
    # Credit exhaustion never cancels an admitted job. Manual/included quotas
    # above remain enforced unless credit overage was explicitly authorized.
    return False


def storage_check(uid,used,additional):
    s=state(uid,used);limit=s['limits']['storage_bytes']
    sample(uid,used)
    if not s['funded']:raise ValueError('Subscription renewal requires credits')
    if s['credits_micro']<0 and s.get('storage_extension',{}).get('paid_bytes',0):raise ValueError('Resource credits exhausted')
    if limit is not None and used+additional>limit:raise ValueError('Storage quota exceeded; manage subscription or unlock storage with credits')


def unlock_storage(uid,gb,key,max_cost=None):
    """Compatibility endpoint: extend paid quota without prepaying future hours."""
    from .resource_entitlements import extend_storage
    return extend_storage(uid,gb,key,max_cost)


def sample(uid,used,*,at=None,live=None):
    stamp=int(time.time() if at is None else at);day=dt.datetime.fromtimestamp(stamp,dt.timezone.utc).date().isoformat()
    with auth.db() as c:
        init(c);c.execute('INSERT INTO resource_storage_samples VALUES(?,?,?) ON CONFLICT(user_id,day) DO UPDATE SET bytes=max(bytes,excluded.bytes)',(uid,day,used))
        s=_state(c,uid,used,stamp);p=s['period'];start=p['start'] if p else 0
        if live:
            for metric in ('cpu_seconds','gpu_seconds'):
                val=live.get(metric+'_estimated',0)
                if type(val) in (int,float) and math.isfinite(val) and val>=0:s['used'][metric]+=val
        for key,limit in s['limits'].items():
            if not limit:continue
            for threshold in (80,90,95):
                if s['used'][key]>=limit*threshold/100:
                    notice(c,f'quota:{uid}:{start}:{key}:{threshold}',uid,{'kind':'quota','metric':key,'threshold':threshold,'used':s['used'][key],'limit':limit,'period_end':p['end'] if p else None,'subscriptions_enabled':s['enabled']})


def notice(c,key,uid,payload):
    c.execute('INSERT OR IGNORE INTO resource_notices(id,user_id,payload) VALUES(?,?,?)',(key,uid,json.dumps(payload)))


def history(uid,*,at=None):
    now=int(time.time() if at is None else at);today=dt.datetime.fromtimestamp(now,dt.timezone.utc).date();start=today-dt.timedelta(days=29)
    rows={str(start+dt.timedelta(days=n)):{'day':str(start+dt.timedelta(days=n)),'cpu_seconds':0.,'gpu_seconds':0.,'storage_bytes':None,'cpu_missing_jobs':0,'gpu_missing_jobs':0} for n in range(30)}
    with auth.db() as c:
        init(c)
        if c.execute("SELECT 1 FROM sqlite_master WHERE name='ai_compute_jobs'").fetchone():
            for r in c.execute("SELECT id,started_at,usage_json,resource_source FROM ai_compute_jobs WHERE user_id=? AND accounting_excluded=0 AND started_at>=? AND started_at<=?",(uid,int(dt.datetime.combine(start,dt.time(),dt.timezone.utc).timestamp()),now)):
                day=dt.datetime.fromtimestamp(r['started_at'],dt.timezone.utc).date().isoformat()
                if day in rows:
                    values=_counters(c,r)
                    for key in ('cpu_seconds','gpu_seconds'):
                        rows[day][key]+=values.get(key,0)
                        if key not in values:rows[day][key.split('_')[0]+'_missing_jobs']+=1
        for r in c.execute('SELECT day,bytes FROM resource_storage_samples WHERE user_id=? AND day>=?',(uid,str(start))):
            if r[0] in rows:rows[r[0]]['storage_bytes']=r[1]
    return list(rows.values())


def tick():
    from . import storage
    from .account_limits import project_storage
    from .i18n import user_language
    from .ai_notifications import smtp_configured,_server
    users=[u for u in auth.list_users() if u['active']];projects=storage.list_projects()
    for u in users:sample(u['id'],project_storage(u['id'],projects,storage.pdir)['used_bytes'])
    if not smtp_configured():return
    for _ in range(100):
        with auth.db() as c:
            init(c);c.execute('BEGIN IMMEDIATE');now=int(time.time())
            row=c.execute('SELECT n.*,u.email,u.email_confirmed,u.active FROM resource_notices n JOIN users u ON u.id=n.user_id WHERE n.sent=0 AND n.lease<? ORDER BY n.rowid LIMIT 1',(now-120,)).fetchone()
            if not row:break
            c.execute('UPDATE resource_notices SET lease=?,attempts=attempts+1 WHERE id=?',(now,row['id']))
        if not row['active'] or not row['email_confirmed']:continue
        payload=json.loads(row['payload']);it=user_language(row['user_id'])=='it';base=_server()
        if not base.startswith('https://'):
            from .legal import snapshot
            base=snapshot()[0]['public_url'] or base
        link=base+'/account#accountLimits'
        if payload['kind']=='legal':
            title='Aggiornamento privacy e termini di servizio' if it else 'Privacy and terms update'
            names={'operator_name':('Operator name','Nome del gestore'),'operator_address':('Address','Sede'),'operator_country':('Country','Paese'),'registration':('Company details','Dati societari'),'privacy_email':('Privacy contact','Contatto privacy'),'support_email':('Support contact','Contatto assistenza'),'dpo_contact':('DPO contact','Contatto DPO'),'representative_contact':('Representative','Rappresentante'),'public_url':('Server URL','URL del server'),'hosting':('Hosting','Hosting'),'processors':('Service providers','Fornitori'),'transfers':('Data transfers','Trasferimenti dati'),'retention':('Retention policy','Conservazione'),'project_days':('Project grace period','Periodo di recupero progetti'),'sandbox_days':('Accounting retention','Conservazione contabile'),'effective_date':('Effective date','Data di efficacia')}
            fields=[]
            for key in payload['fields']:
                base_key=key[:-3] if key.endswith(('_it','_en')) else key
                fields.append(names.get(base_key,(base_key,base_key))[1 if it else 0]+(' ('+key[-2:].upper()+')' if base_key!=key else ''))
            text=('Sono stati aggiornati i dati dei documenti di privacy e termini di servizio. Campi modificati: ' if it else 'Privacy and terms document data have changed. Changed fields: ')+', '.join(fields)
            links=[(base+'/privacy/'+('it' if it else 'en'),'Privacy'),(base+'/terms/'+('it' if it else 'en'),'Termini di servizio' if it else 'Terms of service')]
        else:
            title='Avviso utilizzo quota' if it else 'Resource quota warning'
            scale=1024**3 if payload['metric']=='storage_bytes' else 3600
            unit='GiB' if payload['metric']=='storage_bytes' else 'h'
            text=f"{payload['metric']}: {payload['threshold']}% · {payload.get('used',0)/scale:.3f} / {payload.get('limit',0)/scale:.3f} {unit}"
            if payload.get('period_end'):text+=' · '+dt.datetime.fromtimestamp(payload['period_end'],dt.timezone.utc).isoformat()
            links=[(link,'Limiti e Quote' if it else 'Limits and Quotas')]
            if payload.get('subscriptions_enabled'):links.append((base+'/account#subscriptions','Abbonamenti e crediti' if it else 'Subscriptions and credits'))

        from .version import APP_RELEASE
        body='<html><body style="font:16px Arial;background:#eef3f8;padding:24px"><article style="background:white;padding:24px;max-width:640px"><img src="cid:mta-logo" width="64" alt="MTA"><h1>'+html.escape(title)+'</h1><p>'+html.escape(text)+'</p>'+''.join('<p><a href="'+html.escape(url,quote=True)+'">'+html.escape(label)+'</a></p>' for url,label in links)+'<footer>MTA Audio Editor '+APP_RELEASE+' · '+html.escape(base)+'</footer></article></body></html>'
        try:
            from pathlib import Path
            auth.send_mail([row['email']],title,text+'\n'+'\n'.join(url for url,label in links),body,inline_image=(Path(__file__).parent/'static/mail-logo.png').read_bytes(),message_id='<mta-resource-'+uuid.uuid5(uuid.NAMESPACE_URL,row['id']).hex+'@mta.local>')
        except Exception as exc:
            import logging
            logging.getLogger(__name__).warning('Resource notice delivery deferred: %s',type(exc).__name__)
            continue
        with auth.db() as c:c.execute('UPDATE resource_notices SET sent=1 WHERE id=?',(row['id'],))


def has_limits(uid,c=None):
    def check(con):
        if not con.execute("SELECT 1 FROM sqlite_master WHERE name='resource_memberships'").fetchone():return False
        if con.execute("SELECT 1 FROM sqlite_master WHERE name='resource_user_policy'").fetchone() and con.execute('SELECT 1 FROM resource_user_policy WHERE user_id=? AND (credit_billing=1 OR access_required=1)',(uid,)).fetchone():return True
        return bool(con.execute('SELECT 1 FROM resource_memberships m WHERE m.user_id=?',(uid,)).fetchone())
    if c is not None:return check(c)
    with auth.db() as con:return check(con)


def covered_job(c,jid):
    if not c.execute("SELECT 1 FROM sqlite_master WHERE name='resource_job_contracts'").fetchone():return False
    if c.execute("SELECT 1 FROM sqlite_master WHERE name='resource_job_modes'").fetchone() and c.execute('SELECT 1 FROM resource_job_modes WHERE job_id=?',(jid,)).fetchone():return True
    return bool(c.execute('SELECT 1 FROM resource_job_contracts WHERE job_id=? AND subscription=1',(jid,)).fetchone())


def covered_storage(c,uid,stamp):
    if not c.execute("SELECT 1 FROM sqlite_master WHERE name='resource_periods'").fetchone():return 0
    p=c.execute("SELECT * FROM resource_periods WHERE user_id=? AND start<=? AND end>? AND plan IS NOT NULL AND json_extract(limits,'$._funded')=1 ORDER BY start DESC LIMIT 1",(uid,stamp,stamp)).fetchone()
    if not p:return 0
    base=json.loads(p['limits']).get('storage_bytes') or 0
    extra=c.execute('SELECT coalesce(sum(bytes),0) FROM resource_storage_unlocks WHERE user_id=? AND period_start=? AND created_at<=?',(uid,p['start'],stamp)).fetchone()[0]
    return base+extra


def storage_boundaries(c,uid,start,end):
    if not c.execute("SELECT 1 FROM sqlite_master WHERE name='resource_periods'").fetchone():return []
    values=[v for r in c.execute('SELECT start,end FROM resource_periods WHERE user_id=? AND end>? AND start<?',(uid,start,end)) for v in r if start<v<end]
    return values+[r[0] for r in c.execute('SELECT created_at FROM resource_storage_unlocks WHERE user_id=? AND created_at>? AND created_at<?',(uid,start,end))]


_LAST_TICK=0


def periodic_tick():
    global _LAST_TICK
    now=time.monotonic()
    if now-_LAST_TICK<60:return
    _LAST_TICK=now
    reconcile_cancelled_reservations()
    tick()


def options(uid,body):
    if set(body)!={'overage'} or type(body['overage']) is not bool:raise ValueError('Invalid overage option')
    with auth.db() as c:
        init(c)
        if not c.execute('UPDATE resource_memberships SET overage=? WHERE user_id=? AND plan IS NOT NULL',(int(body['overage']),uid)).rowcount:raise ValueError('Subscription required')
    return state(uid)


def transactions(uid):
    with auth.db() as c:
        init(c)
        return {'terminations':[dict(row) for row in c.execute('SELECT * FROM resource_contract_terminations WHERE user_id=? ORDER BY terminated_at DESC LIMIT 200',(uid,))],'subscription_fees':[dict(row) for row in c.execute('SELECT * FROM resource_plan_charges WHERE user_id=? ORDER BY period_start DESC LIMIT 200',(uid,))],'credits':[dict(r) for r in c.execute('SELECT * FROM resource_credits WHERE user_id=? ORDER BY created_at DESC LIMIT 200',(uid,))],
                'overages':[dict(r) for r in c.execute('SELECT r.job_id,r.period_start,r.charge_micro,b.gross_micro,b.waived_micro FROM resource_job_contracts r JOIN ai_compute_jobs j ON j.id=r.job_id LEFT JOIN resource_job_budgets b ON b.job_id=r.job_id WHERE r.user_id=? AND (r.charge_micro>0 OR b.waived_micro>0) AND j.accounting_excluded=0 ORDER BY r.period_start DESC LIMIT 200',(uid,))]}


def _fund(c,p,member):
    limits=json.loads(p['limits']);price=limits.get('_price_micro',0)
    if limits.get('_funded',True) or not price:return
    # Subscription fees are separate operator receivables, never credit spending.
    c.execute('INSERT OR IGNORE INTO resource_plan_charges(user_id,period_start,amount_micro) VALUES(?,?,?)',(p['user_id'],p['start'],price))
    limits['_funded']=True;limits['_funded_at']=int(time.time());p['limits']=json.dumps(limits)
    c.execute('UPDATE resource_periods SET limits=? WHERE user_id=? AND start=?',(p['limits'],p['user_id'],p['start']))


def subscribe(uid,code,expected_price,*,next_plan=None,next_price=None):
    if code not in (*PLANS,'trial'):raise ValueError('Invalid plan')
    # Validate the chosen renewal before creating a one-time trial, then apply it
    # in the same assignment transaction (no partially activated trial).
    if next_plan is not None and (code!='trial' or next_plan not in PLANS):raise ValueError('Invalid renewal plan')
    return assign(uid,{'plan':code},uid,self_service=True,expected_price=expected_price,next_plan=next_plan,next_price=next_price)


def cancel_renewal(uid):
    with auth.db() as c:
        init(c);p=_period(c,uid,int(time.time()))
        if not p or not p['plan']:raise ValueError('No active subscription')
        c.execute('INSERT INTO resource_cancellations VALUES(?,?) ON CONFLICT(user_id) DO UPDATE SET until_ts=excluded.until_ts',(uid,p['end']))
    return state(uid)


def _counters(c,row):
    values=json.loads(row['usage_json']) if row['resource_source']!='unmetered' else {}
    if c.execute("SELECT 1 FROM sqlite_master WHERE name='ai_compute_job_diagnostics'").fetchone():
        diag=c.execute('SELECT payload FROM ai_compute_job_diagnostics WHERE job_id=?',(row['id'],)).fetchone()
        if diag:
            try:payload=json.loads(diag[0])
            except (ValueError,TypeError):payload={}
            if isinstance(payload,dict):
                for key in ('cpu_seconds','gpu_seconds'):
                    val=payload.get(key+'_estimated')
                    if key not in values and type(val) in (int,float) and math.isfinite(val) and 0<=val<1e18 and (key!='gpu_seconds' or val>0):values[key]=val
    return values


def reconcile_cancelled_reservations(queue_job_id=None):
    """Release only proven pre-execution cancellations through canonical settlement."""
    if not auth.db_path().is_file():return
    with auth.db() as c:
        if not c.execute("SELECT 1 FROM sqlite_master WHERE name='ai_compute_jobs'").fetchone():return
        if queue_job_id is None:
            if not c.execute("SELECT 1 FROM sqlite_master WHERE name='resource_job_contracts'").fetchone():return
            rows=[dict(r) for r in c.execute("SELECT j.id,j.started_at,j.queue_job_id FROM ai_compute_jobs j JOIN resource_job_contracts r ON r.job_id=j.id WHERE j.status='running'")]
        else:
            rows=[dict(r) for r in c.execute("SELECT id,started_at,queue_job_id FROM ai_compute_jobs WHERE queue_job_id=? AND status='running'",(queue_job_id,))]
    from . import ai_arranger_runtime as queue,ai_billing
    for row in rows:
        if not row['queue_job_id']:continue
        try:
            with queue._db() as c:
                job=c.execute('SELECT state,started_at,completed_at FROM jobs WHERE job_id=?',(row['queue_job_id'],)).fetchone()
            if job and job['state']=='cancelled' and job['started_at'] is None:
                ai_billing.finish_job_idempotent(row['id'],'cancelled',source='unmetered',finished_at=max(row['started_at'],int(job['completed_at'])))
        except Exception as exc:
            import logging
            logging.getLogger(__name__).warning('Pre-execution cancellation accounting deferred: %s',type(exc).__name__)


def reserve_budget(c,uid,jid):
    """Freeze a shared ceiling for every ledger step of the same queued job."""
    from .ai_billing import prices
    job=c.execute('SELECT started_at,queue_job_id FROM ai_compute_jobs WHERE id=?',(jid,)).fetchone()
    pool_id=str(uid)+':'+('queue:'+job['queue_job_id'] if job['queue_job_id'] else 'job:'+jid)
    pool=c.execute('SELECT * FROM resource_spending_pools WHERE id=?',(pool_id,)).fetchone()
    if pool is None:
        reserved=c.execute("SELECT coalesce(sum(p.ceiling_micro-p.spent_micro),0) FROM resource_spending_pools p WHERE p.user_id=? AND EXISTS(SELECT 1 FROM resource_job_budgets b JOIN resource_job_contracts r ON r.job_id=b.job_id JOIN ai_compute_jobs j ON j.id=r.job_id WHERE b.pool_id=p.id AND r.settled=0 AND j.accounting_excluded=0)",(uid,)).fetchone()[0]
        ceiling=max(0,_balance(c,uid)-reserved)
        c.execute('INSERT INTO resource_spending_pools(id,user_id,ceiling_micro) VALUES(?,?,?)',(pool_id,uid,ceiling))
    else:ceiling=max(0,pool['ceiling_micro']-pool['spent_micro'])
    c.execute('INSERT INTO resource_job_budgets(job_id,budget_micro,rates_json,pool_id) VALUES(?,?,?,?)',(jid,ceiling,json.dumps(prices(at=job['started_at'],_connection=c)),pool_id))
    contract=c.execute('SELECT period_start FROM resource_job_contracts WHERE job_id=?',(jid,)).fetchone()
    if contract:
        p=c.execute('SELECT * FROM resource_periods WHERE user_id=? AND start=?',(uid,contract[0])).fetchone()
        if p:
            from .resource_contracts import effective
            _,included=effective(c,uid,p,job['started_at'])
            c.execute('UPDATE resource_job_budgets SET included_json=? WHERE job_id=?',(json.dumps(included),jid))


def prepare_upgrade(c):
    """Migrate deployed quota schemas before, never inside, ledger transactions."""
    if not c.execute("SELECT 1 FROM sqlite_master WHERE name='resource_memberships'").fetchone():return
    if not c.execute("SELECT 1 FROM sqlite_master WHERE name='resource_contract_amendments'").fetchone() or 'request_json' not in {r[1] for r in c.execute('PRAGMA table_info(resource_contract_amendments)')} or 'included_json' not in {r[1] for r in c.execute('PRAGMA table_info(resource_job_budgets)')} or not c.execute("SELECT 1 FROM sqlite_master WHERE name='resource_job_budgets'").fetchone() or not {'credit_value_micro','credits_enabled'}.issubset({r[1] for r in c.execute('PRAGMA table_info(resource_config)')}):
        init(c)


def continuing_pool(c,uid,jid):
    job=c.execute('SELECT queue_job_id FROM ai_compute_jobs WHERE id=?',(jid,)).fetchone()
    if not job:return False
    pool_id=str(uid)+':'+('queue:'+job['queue_job_id'] if job['queue_job_id'] else 'job:'+jid)
    return bool(c.execute('SELECT 1 FROM resource_spending_pools WHERE id=? AND user_id=? AND ceiling_micro>0',(pool_id,uid)).fetchone())
