"""Prospective contract amendments and immediate, time-prorated terminations."""
import json
import time
import uuid
from . import auth


def init(c):
    c.executescript('''
    CREATE TABLE IF NOT EXISTS resource_contract_amendments(
      id TEXT PRIMARY KEY,user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
      period_start INTEGER NOT NULL,effective_at INTEGER NOT NULL,limits_json TEXT NOT NULL,
      included_json TEXT NOT NULL,actor_id INTEGER NOT NULL,reason TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS resource_contract_terminations(
      id TEXT PRIMARY KEY,user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
      period_start INTEGER NOT NULL,terminated_at INTEGER NOT NULL,original_end INTEGER NOT NULL,
      original_fee_micro INTEGER NOT NULL,final_fee_micro INTEGER NOT NULL,
      refund_due_micro INTEGER NOT NULL,actor_id INTEGER NOT NULL,reason TEXT NOT NULL);
    ''')
    if 'request_json' not in {r[1] for r in c.execute('PRAGMA table_info(resource_contract_amendments)')}:
        c.execute('ALTER TABLE resource_contract_amendments ADD COLUMN request_json TEXT')
    if 'included_json' not in {r[1] for r in c.execute('PRAGMA table_info(resource_job_budgets)')}:
        c.execute('ALTER TABLE resource_job_budgets ADD COLUMN included_json TEXT')


def effective(c, uid, period, at):
    raw=json.loads(period['limits'])
    included={k:raw.get(k) for k in ('cpu_seconds','gpu_seconds')}
    event=c.execute('SELECT limits_json,included_json FROM resource_contract_amendments WHERE user_id=? AND period_start=? AND effective_at<=? ORDER BY effective_at DESC,rowid DESC LIMIT 1', (uid,period['start'],at)).fetchone()
    if event:
        raw.update(json.loads(event['limits_json']));included=json.loads(event['included_json'])
    return raw,included


def amend(uid,body,actor):
    from . import resource_accounts as r
    if set(body)!={'limits','free_increases','reason','request_id'} or set(body['limits'])!=set(r.RESOURCES):raise ValueError('CPU, GPU and storage limits are required')
    limits={k:r.number(v,integer=k=='storage_bytes') for k,v in body['limits'].items()}
    free=body['free_increases']
    if not isinstance(free,dict) or set(free)-set(r.RESOURCES) or any(type(v) is not bool for v in free.values()):raise ValueError('Specify free or paid increases')
    reason=body['reason'];key=body['request_id']
    if not isinstance(reason,str) or not 3<=len(reason)<=300 or not isinstance(key,str) or not 8<=len(key)<=80:raise ValueError('Reason and request ID required')
    with auth.db() as c:
        r.init(c);c.execute('BEGIN IMMEDIATE');now=int(time.time());s=r._state(c,uid,0,now);p=s['period']
        if not p or not s['subscription']:raise ValueError('No active subscription')
        prior=c.execute('SELECT * FROM resource_contract_amendments WHERE id=?',(key,)).fetchone()
        if prior:
            if prior['user_id']!=uid or prior['reason']!=reason or json.loads(prior['limits_json'])!=limits or (prior['request_json'] and json.loads(prior['request_json'])!=free):raise ValueError('Conflicting amendment retry')
        else:
            _,included=effective(c,uid,p,now)
            old=s['limits']
            for k in r.RESOURCES:
                increase=limits[k]-(old[k] or 0)
                if increase>0:
                    if k not in free:raise ValueError('Choose free or paid for every quota increase')
                    if not free[k] and not s['credits_enabled']:raise ValueError('Enable subscription credits for paid quota increases')
                if k in included:
                    # Paid extensions remain overages; a larger admission limit
                    # must never turn billable compute into included compute.
                    included[k]=min(limits[k],(included[k] or 0)+max(0,increase if free.get(k) else 0))
            if any(limits[k]>(old[k] or 0) and free.get(k) is False for k in ('cpu_seconds','gpu_seconds')):
                c.execute('UPDATE resource_memberships SET overage=1 WHERE user_id=?',(uid,))
            c.execute('INSERT INTO resource_contract_amendments(id,user_id,period_start,effective_at,limits_json,included_json,actor_id,reason,request_json) VALUES(?,?,?,?,?,?,?,?,?)',(key,uid,p['start'],now,json.dumps(limits),json.dumps(included),actor,reason,json.dumps(free)))
            # Preserve historical storage allowance for correct time slicing.
            base=json.loads(p['limits']).get('storage_bytes') or 0
            extra=max(0,limits['storage_bytes']-base-s['storage_extension'].get('prepaid_bytes',0))
            free_growth=max(0,limits['storage_bytes']-(old['storage_bytes'] or 0)) if free.get('storage_bytes') else 0
            free_bytes=min(extra,s['storage_extension']['free_bytes']+free_growth)
            c.execute('INSERT INTO resource_quota_events VALUES(?,?,?,?,?,?,?)',('amend:'+key,uid,now,limits['storage_bytes'],free_bytes,actor,reason))
            c.execute('INSERT INTO resource_credits VALUES(?,?,?,?,?,?)',(uuid.uuid4().hex,uid,0,actor,'Contract amendment: '+reason,now))
    return r.state(uid)


def terminate(uid,body,actor):
    from . import resource_accounts as r,ai_billing
    from .resource_entitlements import _settle_storage
    if set(body)!={'reason','request_id'} or not isinstance(body['reason'],str) or not 3<=len(body['reason'])<=300 or not isinstance(body['request_id'],str) or not 8<=len(body['request_id'])<=80:raise ValueError('Reason and request ID required')
    with auth.db() as c:
        r.init(c);c.execute('BEGIN IMMEDIATE');now=int(time.time())
        old=c.execute('SELECT * FROM resource_contract_terminations WHERE id=?',(body['request_id'],)).fetchone()
        if old:
            if old['user_id']!=uid or old['reason']!=body['reason']:raise ValueError('Conflicting termination retry')
            return dict(old)
        p=r._period(c,uid,now)
        if not p or not p['plan']:raise ValueError('No active subscription')
        _settle_storage(c,uid,now)
        raw=json.loads(p['limits']);fee=int(raw.get('_price_micro',0));duration=max(1,p['end']-p['start'])
        enabled=bool(c.execute('SELECT enabled FROM resource_config WHERE id=1').fetchone()[0]) and ai_billing.user_billing_enabled(uid,_connection=c)
        final=round(fee*min(duration,max(0,now-p['start']))/duration) if enabled else 0
        charge=c.execute('SELECT * FROM resource_plan_charges WHERE user_id=? AND period_start=?',(uid,p['start'])).fetchone()
        refund=max(0,charge['amount_micro']-final) if charge and charge['status']=='paid' else 0
        if charge:c.execute('UPDATE resource_plan_charges SET amount_micro=? WHERE user_id=? AND period_start=?',(final,uid,p['start']))
        c.execute('INSERT INTO resource_contract_terminations VALUES(?,?,?,?,?,?,?,?,?,?)',(body['request_id'],uid,p['start'],now,p['end'],fee,final,refund,actor,body['reason']))
        c.execute('UPDATE resource_periods SET end=? WHERE user_id=? AND start=?',(now,uid,p['start']))
        c.execute("UPDATE resource_memberships SET plan=NULL,anchor=?,cpu_seconds=NULL,gpu_seconds=NULL,storage_bytes=NULL,promo='',overage=0 WHERE user_id=?",(now,uid))
        c.execute('DELETE FROM resource_next_plans WHERE user_id=?',(uid,));c.execute('DELETE FROM resource_cancellations WHERE user_id=?',(uid,))
        c.execute('INSERT INTO resource_credits VALUES(?,?,?,?,?,?)',(uuid.uuid4().hex,uid,0,actor,'Contract terminated: '+body['reason'],now))
        return dict(c.execute('SELECT * FROM resource_contract_terminations WHERE id=?',(body['request_id'],)).fetchone())
