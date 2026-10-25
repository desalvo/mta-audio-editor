"""Paid-access policy and prospective defaults; existing tariff history is retained."""
import time
from . import auth

DEFAULT_TARIFFS={'cpu_seconds':1,'gpu_seconds':10,'disk_gb_hours':20}


def ensure_tariffs(c):
    stamp=int(time.time())
    for key,value in DEFAULT_TARIFFS.items():
        if c.execute('SELECT 1 FROM ai_resource_price_history WHERE resource=?',(key,)).fetchone():continue
        c.execute('INSERT INTO ai_resource_price_history(resource,valid_from,micro_per_unit) VALUES(?,?,?)',(key,stamp,value))
        c.execute("INSERT OR IGNORE INTO ai_resource_prices VALUES(?,?,'EUR',?)",(key,value,stamp))


def tariff_view(c):
    from .ai_billing import prices
    current=prices(_connection=c)
    return {key:{'micro_per_unit':current.get(key,default),'configured':key in current} for key,default in DEFAULT_TARIFFS.items()}


def access_state(s,role):
    required=bool(s['policy'].get('access_required')) and bool(s['policy']['subscriptions_allowed']) and role!='admin'
    allowed=bool(s['subscription'] and s['funded'])
    return {'required':required,'blocked':required and not allowed,'url':'/account#subscriptions'}


def status(uid):
    from .resource_accounts import state
    return state(uid)['access']


def quick_required(uid):
    """No schema mutation or heavy storage scans on the request path."""
    with auth.db() as c:
        if not c.execute("SELECT 1 FROM sqlite_master WHERE name='resource_user_policy'").fetchone():return False
        if 'access_required' not in {r[1] for r in c.execute('PRAGMA table_info(resource_user_policy)')}:return False
        return bool(c.execute('SELECT 1 FROM resource_user_policy p JOIN users u ON u.id=p.user_id WHERE p.user_id=? AND p.access_required=1 AND u.role!=?',(uid,'admin')).fetchone())


def grant_credits(uid,credits,expected_value,reason,actor,key):
    """Convert nominal credits once; money already on the ledger never changes."""
    from .service_regime import require_commercial
    require_commercial("credit grant")
    from . import resource_accounts as r
    amount=r.number(credits)
    with auth.db() as c:
        r.init(c);c.execute('BEGIN IMMEDIATE')
        if not r._state(c,uid,0,int(time.time()))['credits_enabled']:raise ValueError('Credits require an enabled credit service and an active subscription for this user')
        value=c.execute('SELECT credit_value_micro FROM resource_config WHERE id=1').fetchone()[0]
        if expected_value!=value:raise ValueError('Credit value changed; review current value')
        micro=round(amount*value)
        if micro<1 or abs(amount*value-micro)>.00001:raise ValueError('Credit precision exceeds one micro-EUR')
        # Inline idempotent insertion keeps value validation and grant atomic.
        if not isinstance(reason,str) or not 3<=len(reason)<=300 or not isinstance(key,str) or not 8<=len(key)<=80:raise ValueError('Reason and unique request ID required')
        prior=c.execute('SELECT * FROM resource_credits WHERE id=?',('grant:'+key,)).fetchone()
        if prior:
            if (prior['user_id'],prior['delta_micro'],prior['reason'])!=(uid,micro,reason):raise ValueError('Conflicting credit retry')
        else:c.execute('INSERT INTO resource_credits VALUES(?,?,?,?,?,?)',('grant:'+key,uid,micro,actor,reason,int(time.time())))
    return r.state(uid)


class CreditAdmissionError(ValueError):
    """A deterministic refusal, never a job awaiting admission reconciliation."""

    @property
    def code(self):
        return "subscription_required" if str(self).startswith("SUBSCRIPTION_REQUIRED:") else "credits_exhausted"


def preflight(uid):
    from .model_license_policy import FREE_ADMISSION
    if FREE_ADMISSION.get():return
    from . import resource_accounts as r
    if type(uid) is not int or uid<=0 or not auth.db_path().is_file():return
    with auth.db() as c:
        if not r.has_limits(uid,c):return
    s=r.state(uid)
    paid=bool(s['subscription'] and s['funded'])
    if s['access']['blocked']:
        raise CreditAdmissionError('SUBSCRIPTION_REQUIRED: An active subscription is required. Choose a subscription or contact the server administrator.')
    if paid and s['credits_micro']<=0 and any(s.get('included_compute',s['limits']).get(k) is not None and s['used'][k]>=s.get('included_compute',s['limits'])[k] for k in ('cpu_seconds','gpu_seconds')):
        raise CreditAdmissionError('CREDIT_REQUIRED: Included compute quota is exhausted and no credits are available. Top up credits, wait for renewal, or contact the server administrator.')
