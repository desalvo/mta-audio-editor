"""Explicit operator refunds with durable single dispatch and GET-only recovery.

No automatic POST retry, including after process death or expired provider
idempotency retention. Authenticated provider receipts and canonical ledger
reconciliation, not the browser or POST status, close the financial operation.
"""
from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import time
import uuid

import httpx

from . import auth, credit_purchases as stripe, paypal_payments as paypal
from .regime_operation_fence import FenceBlocked, admit, settle

_SCHEMA = '''
CREATE TABLE IF NOT EXISTS operator_refunds (
 id TEXT PRIMARY KEY,provider TEXT NOT NULL CHECK(provider IN ('stripe','paypal')),
 order_id TEXT NOT NULL,user_id INTEGER NOT NULL,actor_id INTEGER NOT NULL,
 request_id TEXT NOT NULL,amount_cents INTEGER NOT NULL CHECK(amount_cents>0),
 target TEXT NOT NULL,context_json TEXT NOT NULL,reason TEXT NOT NULL,
 state TEXT NOT NULL CHECK(state IN ('prepared','uncertain','pending','settled','failed','cancelled')),
 revision INTEGER NOT NULL DEFAULT 0,provider_reference TEXT,receipt_sha256 TEXT,
 created_at INTEGER NOT NULL,updated_at INTEGER NOT NULL,
 UNIQUE(actor_id,request_id),UNIQUE(provider,provider_reference));
CREATE UNIQUE INDEX IF NOT EXISTS operator_refunds_active_order
 ON operator_refunds(provider,order_id) WHERE state IN ('prepared','uncertain','pending');
CREATE TABLE IF NOT EXISTS operator_refund_audit (
 refund_id TEXT NOT NULL REFERENCES operator_refunds(id),revision INTEGER NOT NULL,
 actor_id INTEGER NOT NULL,state TEXT NOT NULL,created_at INTEGER NOT NULL,
 PRIMARY KEY(refund_id,revision));
CREATE TRIGGER IF NOT EXISTS operator_refund_identity_immutable
 BEFORE UPDATE ON operator_refunds WHEN NEW.id IS NOT OLD.id OR NEW.provider IS NOT OLD.provider
 OR NEW.order_id IS NOT OLD.order_id OR NEW.user_id IS NOT OLD.user_id OR NEW.actor_id IS NOT OLD.actor_id
 OR NEW.request_id IS NOT OLD.request_id OR NEW.amount_cents IS NOT OLD.amount_cents
 OR NEW.target IS NOT OLD.target OR NEW.context_json IS NOT OLD.context_json OR NEW.reason IS NOT OLD.reason
 OR NEW.created_at IS NOT OLD.created_at
 BEGIN SELECT RAISE(ABORT,'Refund financial identity is immutable'); END;
CREATE TRIGGER IF NOT EXISTS operator_refund_delete_guard BEFORE DELETE ON operator_refunds
 WHEN mta_operator_refund_erasure(OLD.id)!=1 BEGIN SELECT RAISE(ABORT,'Refund erasure requires authorization'); END;
CREATE TRIGGER IF NOT EXISTS operator_refund_audit_update_guard BEFORE UPDATE ON operator_refund_audit
 BEGIN SELECT RAISE(ABORT,'Refund audit is immutable'); END;
CREATE TRIGGER IF NOT EXISTS operator_refund_audit_delete_guard BEFORE DELETE ON operator_refund_audit
 WHEN mta_operator_refund_erasure(OLD.refund_id)!=1 BEGIN SELECT RAISE(ABORT,'Refund audit erasure requires authorization'); END;
'''
_PUBLIC = ('id','provider','order_id','user_id','amount_cents','target','state','revision',
           'provider_reference','created_at','updated_at')
_TERMINAL = ('settled','failed','cancelled')


def initialize(c):
    # Never implicitly commit the caller's transaction.
    statement=''
    for line in _SCHEMA.splitlines():
        statement+=line+'\n'
        if sqlite3.complete_statement(statement):
            c.execute(statement);statement=''
    if statement.strip():raise ValueError('Incomplete refund schema')


def _initialize():
    with auth.db() as c:
        stripe.init(c);paypal.init(c);initialize(c)


def _reference(value, provider):
    pattern=r're_[A-Za-z0-9]{1,100}' if provider=='stripe' else r'[A-Z0-9]{6,64}'
    if not isinstance(value,str) or re.fullmatch(pattern,value) is None:raise ValueError('Invalid refund reference')
    return value


def _actor(actor):
    if type(actor) is not int or actor<=0:raise ValueError('Invalid audit actor')
    with auth.db() as c:
        row=c.execute('SELECT role,active FROM users WHERE id=?',(actor,)).fetchone()
    if row is None or tuple(row)!=('admin',1):raise FenceBlocked('Active administrator required')


def _row(c,identifier,revision=None):
    if not isinstance(identifier,str) or re.fullmatch(r'[a-f0-9]{32}',identifier) is None:raise ValueError('Invalid refund operation')
    row=c.execute('SELECT * FROM operator_refunds WHERE id=?',(identifier,)).fetchone()
    if row is None:raise ValueError('Refund unavailable')
    if not audit(c)['verified']:raise FenceBlocked('Refund journal integrity requires operator review')
    if revision is not None and (type(revision) is not int or row['revision']!=revision):raise FenceBlocked('Refund changed; refresh before acting')
    return dict(row)


def _revision(value):
    if type(value) is not int or value<0:raise ValueError('Exact refund revision required')


def _public(row):
    return {key:row[key] for key in _PUBLIC}


def _change(c,row,actor,state,*,reference=None,digest=None):
    revision=row['revision']+1;now=int(time.time())
    c.execute('''UPDATE operator_refunds SET state=?,revision=?,updated_at=?,
      provider_reference=coalesce(?,provider_reference),receipt_sha256=coalesce(?,receipt_sha256) WHERE id=?''',
      (state,revision,now,reference,digest,row['id']))
    c.execute('INSERT INTO operator_refund_audit VALUES(?,?,?,?,?)',(row['id'],revision,actor,state,now))
    if state in _TERMINAL:settle(c,'operator-refund:'+row['id'])
    return _public(_row(c,row['id']))


def _configuration(c,provider):
    if provider=='stripe':
        key=auth._open(c.execute('SELECT secret_key FROM credit_payment_config WHERE id=1').fetchone()[0])
        if not key.startswith(('sk_test_','sk_live_')):raise FenceBlocked('Stripe merchant unavailable')
        return key
    cfg=paypal._keys(c)
    if not cfg['enabled'] or cfg['environment'] not in paypal.BASES or not cfg['client_id'] or not cfg['client_secret']:
        raise FenceBlocked('PayPal merchant unavailable')
    return cfg


def _fingerprint(config):
    return hashlib.sha256(json.dumps(config,sort_keys=True).encode()).hexdigest()


def _context(c,provider,order_id,target=None):
    from .payment_reconciliation import report
    health=report(c)
    if not health['verified'] or health['pending'] or health.get('active_disputes'):
        raise FenceBlocked('Reconcile unresolved payment evidence and disputes first')
    position=c.execute('SELECT * FROM payment_reconciliation_positions WHERE provider=? AND order_id=?',(provider,order_id)).fetchone()
    if position is None or not position['funded'] or position['held_minor'] or position['currency']!='EUR':
        raise FenceBlocked('Funded undisputed EUR payment required')
    if provider=='stripe':
        order=c.execute('SELECT * FROM credit_purchase_orders WHERE id=?',(order_id,)).fetchone()
        if order is None or not isinstance(order['payment_intent'],str) or re.fullmatch(r'pi_[A-Za-z0-9_]{1,100}',order['payment_intent']) is None:
            raise FenceBlocked('Reconciled Stripe intent required')
        target=order['payment_intent'];gross=order['amount_cents'];refunded=order['refunded_cents']
        if refunded!=position['refunded_minor']:raise FenceBlocked('Stripe refund ledger mismatch')
        identity={'session_id':order['session_id'],'intent':target}
    else:
        order=c.execute('SELECT * FROM paypal_orders WHERE id=?',(order_id,)).fetchone()
        capture=c.execute('SELECT * FROM paypal_captures WHERE id=? AND order_id=?',(target,order_id)).fetchone()
        if order is None or capture is None:raise FenceBlocked('Select a reconciled capture belonging to this order')
        gross=capture['amount_cents'];refunded=c.execute('SELECT coalesce(sum(amount_cents),0) FROM paypal_refunds WHERE capture_id=?',(target,)).fetchone()[0]
        if (position['refunded_minor']!=c.execute('SELECT coalesce(sum(amount_cents),0) FROM paypal_refunds WHERE order_id=?',(order_id,)).fetchone()[0]
            or order['amount_cents']!=c.execute('SELECT coalesce(sum(amount_cents),0) FROM paypal_captures WHERE order_id=?',(order_id,)).fetchone()[0]):raise FenceBlocked('PayPal capture/refund ledger mismatch')
        identity={key:order[key] for key in ('provider_order','kind','period_start','environment','client_fingerprint')}
    if (order['status']!='paid' or order['user_id']!=position['user_id'] or order['amount_cents']!=position['amount_minor']
        or not 0<=refunded<=gross):raise FenceBlocked('Payment identity or balance changed')
    config=_configuration(c,provider)
    if provider=='paypal' and (order['environment']!=config['environment'] or order['client_fingerprint']!=hashlib.sha256(config['client_id'].encode()).hexdigest()):
        raise FenceBlocked('PayPal merchant changed')
    return {'provider':provider,'order_id':order_id,'user_id':order['user_id'],'target':target,
            'gross_cents':gross,'refunded_cents':refunded,'order_refunded_cents':position['refunded_minor'],
            'order_amount_cents':order['amount_cents'],'merchant':_fingerprint(config),'identity':identity}


def _reconcile(provider,order_id):
    from .payment_reconcile_service import reconcile_checkout
    result=reconcile_checkout(provider,order_id)
    if result.get('ledger_reconciled') is not True:raise FenceBlocked('Payment is not reconciled')


def _require_original_payment(c,row):
    """Reject local identity drift before any reconciliation can mutate money."""
    context=json.loads(row['context_json'])
    if row['provider']=='stripe':
        order=c.execute('SELECT user_id,amount_cents,session_id,payment_intent FROM credit_purchase_orders WHERE id=?',(row['order_id'],)).fetchone()
        expected=(context['user_id'],context['order_amount_cents'],context['identity']['session_id'],row['target'])
    else:
        order=c.execute('SELECT user_id,amount_cents,provider_order,kind,period_start,environment,client_fingerprint FROM paypal_orders WHERE id=?',(row['order_id'],)).fetchone()
        expected=(context['user_id'],context['order_amount_cents'],*(context['identity'][key] for key in ('provider_order','kind','period_start','environment','client_fingerprint')))
        capture=c.execute('SELECT amount_cents FROM paypal_captures WHERE id=? AND order_id=?',(row['target'],row['order_id'])).fetchone()
        if capture is None or capture[0]!=context['gross_cents']:raise FenceBlocked('Original refund capture changed')
    if order is None or tuple(order)!=expected:raise FenceBlocked('Original refund payment identity changed')
    if _fingerprint(_configuration(c,row['provider']))!=context['merchant']:raise FenceBlocked('Original refund merchant required')


def prepare(actor,body):
    _actor(actor)
    required={'provider','order_id','target','amount_cents','reason','request_id'}
    if not isinstance(body,dict) or set(body)!=required:raise ValueError('Exact refund preparation fields required')
    if body['provider'] not in ('stripe','paypal'):raise ValueError('Unsupported refund provider')
    if not isinstance(body['order_id'],str) or re.fullmatch(r'[A-Za-z0-9_-]{1,120}',body['order_id']) is None:raise ValueError('Invalid local order')
    if not isinstance(body['target'],str) or len(body['target'])>120:raise ValueError('Invalid refund target')
    if type(body['amount_cents']) is not int or not 0<body['amount_cents']<=1_000_000_000:raise ValueError('Positive integer cents required')
    if not isinstance(body['request_id'],str) or re.fullmatch(r'[A-Za-z0-9_-]{8,80}',body['request_id']) is None:raise ValueError('Invalid refund request ID')
    if not isinstance(body['reason'],str) or len(body['reason'])>500 or not 4<=len(body['reason'].strip()) or any(ord(ch)<32 for ch in body['reason']):raise ValueError('Document the operator refund reason')
    _initialize()
    with auth.db() as c:
        old=c.execute('SELECT * FROM operator_refunds WHERE actor_id=? AND request_id=?',(actor,body['request_id'])).fetchone()
        if old:
            if any(old[k]!=body[k] for k in ('provider','order_id','target','amount_cents','reason')):raise FenceBlocked('Conflicting refund retry')
            return _public(old)
    _reconcile(body['provider'],body['order_id'])
    with auth.db() as c:
        c.execute('BEGIN IMMEDIATE');context=_context(c,body['provider'],body['order_id'],body['target'])
        if body['target']!=context['target']:raise FenceBlocked('Refund target changed')
        if body['amount_cents']>context['gross_cents']-context['refunded_cents']:raise FenceBlocked('Refund exceeds remaining captured amount')
        old=c.execute('SELECT * FROM operator_refunds WHERE actor_id=? AND request_id=?',(actor,body['request_id'])).fetchone()
        if old:
            if any(old[k]!=body[k] for k in ('provider','order_id','target','amount_cents','reason')):raise FenceBlocked('Conflicting refund retry')
            return _public(old)
        if c.execute("SELECT 1 FROM operator_refunds WHERE provider=? AND order_id=? AND state NOT IN ('settled','failed','cancelled')",(body['provider'],body['order_id'])).fetchone():raise FenceBlocked('An unresolved refund already reserves this order')
        identifier=uuid.uuid4().hex;now=int(time.time())
        admit(c,'operator-refund:'+identifier,'checkout')
        c.execute('''INSERT INTO operator_refunds(id,provider,order_id,user_id,actor_id,request_id,amount_cents,
          target,context_json,reason,state,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,'prepared',?,?)''',
          (identifier,body['provider'],body['order_id'],context['user_id'],actor,body['request_id'],body['amount_cents'],body['target'],json.dumps(context,sort_keys=True),body['reason'],now,now))
        c.execute('INSERT INTO operator_refund_audit VALUES(?,0,?,?,?)',(identifier,actor,'prepared',now))
        return _public(_row(c,identifier))


def _receipt(row,document):
    if not isinstance(document,dict):raise ValueError('Invalid provider refund receipt')
    ref=_reference(document.get('id'),row['provider']);token='mta-refund-'+row['id']
    context=json.loads(row['context_json'])
    if row['provider_reference'] and row['provider_reference']!=ref:raise FenceBlocked('Refund reference cannot change')
    if row['provider']=='stripe':
        if (document.get('object')!='refund' or document.get('payment_intent')!=row['target']
            or document.get('currency')!='eur' or type(document.get('amount')) is not int
            or document['amount']!=row['amount_cents'] or not isinstance(document.get('metadata'),dict)
            or document['metadata'].get('mta_refund')!=token):raise FenceBlocked('Stripe refund identity mismatch')
        state={'succeeded':'settled','failed':'failed','canceled':'failed','pending':'pending','requires_action':'pending'}.get(document.get('status'))
    else:
        if (paypal._refund_capture(document,context['identity']['environment'])!=row['target']
            or paypal._cents(document.get('amount',{}))!=row['amount_cents'] or document.get('custom_id')!=token):raise FenceBlocked('PayPal refund identity mismatch')
        state={'COMPLETED':'settled','FAILED':'failed','CANCELLED':'failed','PENDING':'pending'}.get(document.get('status'))
    if state is None:raise FenceBlocked('Unknown provider refund outcome')
    digest=hashlib.sha256(json.dumps(document,sort_keys=True,allow_nan=False).encode()).hexdigest()
    return ref,state,digest


def _dispatch(row,config):
    token='mta-refund-'+row['id']
    if row['provider']=='paypal':
        return paypal._api(config,'POST','/v2/payments/captures/'+row['target']+'/refund',
          {'amount':{'value':f"{row['amount_cents']//100}.{row['amount_cents']%100:02d}",'currency_code':'EUR'},'custom_id':token},request_id=row['id'])
    with httpx.Client(timeout=30,follow_redirects=False) as client:
        result=client.post('https://api.stripe.com/v1/refunds',headers={'Authorization':'Bearer '+config,'Idempotency-Key':token},
          data={'payment_intent':row['target'],'amount':str(row['amount_cents']),'metadata[mta_refund]':token})
        if result.status_code not in (200,201):raise ValueError('Refund dispatch outcome requires review')
        return result.json()


def execute(actor,identifier,revision):
    _actor(actor);_revision(revision);_initialize()
    with auth.db() as c:
        initial=_row(c,identifier,revision)
        _require_original_payment(c,initial)
    if initial['state']!='prepared':raise FenceBlocked('Refund already dispatched or closed; verify its existing outcome')
    _reconcile(initial['provider'],initial['order_id'])
    with auth.db() as c:
        c.execute('BEGIN IMMEDIATE');row=_row(c,identifier,revision)
        if row['state']!='prepared':raise FenceBlocked('Refund already dispatched')
        admin=c.execute('SELECT role,active FROM users WHERE id=?',(actor,)).fetchone()
        if admin is None or tuple(admin)!=('admin',1):raise FenceBlocked('Administrator authorization changed')
        if _context(c,row['provider'],row['order_id'],row['target'])!=json.loads(row['context_json']):raise FenceBlocked('Refund quote changed; cancel and prepare again')
        config=_configuration(c,row['provider'])
        # Commit uncertainty before any potentially irreversible I/O. Never
        # clear this on exceptions, network errors, HTTP errors or process death.
        _change(c,row,actor,'uncertain');row=_row(c,identifier)
    try:
        document=_dispatch(row,config)
        if not isinstance(document,dict):raise ValueError('Invalid provider dispatch response')
        ref=_reference(document.get('id'),row['provider'])
        digest=hashlib.sha256(json.dumps(document,sort_keys=True,allow_nan=False).encode()).hexdigest()
    except (ValueError,FenceBlocked,httpx.HTTPError,TypeError,KeyError):
        with auth.db() as c:return _public(_row(c,identifier))
    with auth.db() as c:
        c.execute('BEGIN IMMEDIATE');row=_row(c,identifier)
        if row['provider_reference'] and row['provider_reference']!=ref:raise FenceBlocked('Conflicting provider refund')
        if row['state'] in _TERMINAL:return _public(row)
        _change(c,row,actor,'pending',reference=ref,digest=digest);row=_row(c,identifier)
    return verify(actor,identifier,row['revision'])


def verify(actor,identifier,revision,reference=None):
    """GET-only recovery; caller references are hints requiring exact receipt binding."""
    _actor(actor);_revision(revision);_initialize()
    with auth.db() as c:
        row=_row(c,identifier,revision)
        if row['state'] in _TERMINAL:return _public(row)
        if row['state']=='prepared':raise FenceBlocked('No refund dispatch to verify')
        config=_configuration(c,row['provider'])
    context=json.loads(row['context_json'])
    if _fingerprint(config)!=context['merchant']:raise FenceBlocked('Original refund merchant configuration required')
    ref=_reference(reference or row['provider_reference'],row['provider'])
    if row['provider']=='stripe':
        from .regime_provider_probe import _get
        with httpx.Client(timeout=15,follow_redirects=False) as client:
            document=_get(client,'https://api.stripe.com/v1/refunds/'+ref,{'Authorization':'Bearer '+config})
    else:document=paypal._api(config,'GET','/v2/payments/refunds/'+ref)
    actual,state,digest=_receipt(row,document)
    if actual!=ref:raise FenceBlocked('Provider refund reference mismatch')
    # Preserve an authenticated reference before attempting a potentially
    # unavailable canonical ledger readback. Pending receipts never settle.
    with auth.db() as c:
        c.execute('BEGIN IMMEDIATE');current=_row(c,identifier,revision)
        if _fingerprint(_configuration(c,row['provider']))!=context['merchant']:raise FenceBlocked('Refund merchant changed during lookup')
        _change(c,current,actor,'pending',reference=ref,digest=digest)
        row=_row(c,identifier)
    if state=='pending':return _public(row)
    with auth.db() as c:_require_original_payment(c,row)
    try:_reconcile(row['provider'],row['order_id'])
    except (ValueError,FenceBlocked,httpx.HTTPError):return _public(row)
    with auth.db() as c:
        c.execute('BEGIN IMMEDIATE');current=_row(c,identifier,row['revision'])
        updated=_context(c,row['provider'],row['order_id'],row['target'])
        immutable=('provider','order_id','user_id','target','gross_cents','order_amount_cents','merchant','identity')
        if any(updated[k]!=context[k] for k in immutable):raise FenceBlocked('Original refund payment identity changed')
        if state=='settled':
            if updated['refunded_cents']<context['refunded_cents']+row['amount_cents']:raise FenceBlocked('Refund not yet reflected in canonical ledger')
            if row['provider']=='paypal':
                entry=c.execute('SELECT order_id,capture_id,amount_cents FROM paypal_refunds WHERE id=?',(ref,)).fetchone()
                if entry is None or tuple(entry)!=(row['order_id'],row['target'],row['amount_cents']):raise FenceBlocked('Canonical refund entry missing')
        return _change(c,current,actor,state,reference=ref,digest=digest)


def cancel(actor,identifier,revision):
    _actor(actor);_revision(revision);_initialize()
    with auth.db() as c:
        c.execute('BEGIN IMMEDIATE');row=_row(c,identifier,revision)
        if row['state']!='prepared':raise FenceBlocked('Dispatched refunds cannot be cancelled locally')
        return _change(c,row,actor,'cancelled')


def overview(*,owner=None,limit=50,offset=0):
    if type(limit) is not int or not 1<=limit<=200 or type(offset) is not int or offset<0:raise ValueError('Invalid refund pagination')
    if owner is not None and (type(owner) is not int or owner<=0):raise ValueError('Invalid owner')
    _initialize()
    with auth.db() as c:
        rows=c.execute('SELECT * FROM operator_refunds WHERE (? IS NULL OR user_id=?) ORDER BY created_at DESC,id DESC LIMIT ? OFFSET ?',(owner,owner,limit,offset)).fetchall()
        total=c.execute('SELECT count(*) FROM operator_refunds WHERE (? IS NULL OR user_id=?)',(owner,owner)).fetchone()[0]
        items=[_public(x) for x in rows]
        if owner is not None:
            for item in items:
                for key in ('user_id','target','provider_reference','revision'):item.pop(key)
            return {'items':items,'total':total,'limit':limit,'offset':offset}
        for item,row in zip(items,rows):
            item['reason']=row['reason'];item['actor_id']=row['actor_id']
            item['audit']=[dict(x) for x in c.execute('SELECT revision,actor_id,state,created_at FROM operator_refund_audit WHERE refund_id=? ORDER BY revision',(row['id'],))]
        targets=[]
        tables={x[0] for x in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if 'payment_reconciliation_positions' in tables:
            for p in c.execute("SELECT * FROM payment_reconciliation_positions WHERE funded=1 AND held_minor=0 AND amount_minor>refunded_minor ORDER BY provider,order_id LIMIT 200"):
                if p['provider']=='stripe':
                    order=c.execute('SELECT payment_intent FROM credit_purchase_orders WHERE id=?',(p['order_id'],)).fetchone()
                    if order and order[0]:targets.append({'provider':'stripe','order_id':p['order_id'],'target':order[0],'remaining_cents':p['amount_minor']-p['refunded_minor']})
                elif p['provider']=='paypal':
                    for capture in c.execute('''SELECT id,amount_cents-(SELECT coalesce(sum(amount_cents),0) FROM paypal_refunds WHERE capture_id=p.id) AS remaining FROM paypal_captures p WHERE order_id=?''',(p['order_id'],)):
                        if capture[1]>0:targets.append({'provider':'paypal','order_id':p['order_id'],'target':capture[0],'remaining_cents':capture[1]})
        return {'items':items,'total':total,'limit':limit,'offset':offset,'targets':targets,'audit':audit(c),'transition_enabled':False}


def audit(c):
    try:return _audit(c)
    except (sqlite3.DatabaseError,ValueError,TypeError,KeyError):
        return {'verified':False,'pending':None,'issues':['unverifiable_journal']}


def _audit(c):
    tables={x[0] for x in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if not {'operator_refunds','operator_refund_audit'}&tables:return {'verified':True,'pending':0,'settled':0,'issues':[]}
    if not {'operator_refunds','operator_refund_audit','regime_fence_operations'}<=tables:return {'verified':False,'pending':None,'issues':['schema_unavailable']}
    issues=[];pending=0;closed=0
    for row in c.execute('SELECT * FROM operator_refunds'):
        context=json.loads(row['context_json'])
        terminal=row['state'] in _TERMINAL;pending+=not terminal;closed+=row['state']=='settled'
        fence=c.execute('SELECT status,kind FROM regime_fence_operations WHERE operation_id=?',('operator-refund:'+row['id'],)).fetchone()
        events=c.execute('SELECT revision,state FROM operator_refund_audit WHERE refund_id=? ORDER BY revision',(row['id'],)).fetchall()
        if (fence is None or tuple(fence)!=('closed' if terminal else 'open','checkout') or not events
            or [x[0] for x in events]!=list(range(row['revision']+1)) or events[-1][1]!=row['state']
            or any(context[k]!=row[k] for k in ('provider','order_id','user_id','target'))
            or not 0<row['amount_cents']<=context['gross_cents']-context['refunded_cents']
            or (row['state'] in ('settled','failed') and (not row['provider_reference'] or not row['receipt_sha256']))):issues.append('refund_journal_mismatch')
    return {'verified':not issues,'pending':pending,'settled':closed,'issues':sorted(set(issues))}


def require_erasure_ready(c,uid):
    if not c.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='operator_refunds'").fetchone():return []
    rows=c.execute('SELECT id,state FROM operator_refunds WHERE user_id=?',(uid,)).fetchall()
    if rows and (any(row['state'] not in _TERMINAL for row in rows) or not audit(c)['verified']):raise FenceBlocked('Resolve and verify operator refunds before account erasure')
    return [row['id'] for row in rows]


def authorize_account_erasure(c,uid,actor):
    if not c.in_transaction:raise FenceBlocked('Refund erasure requires an owned transaction')
    allowed=set(require_erasure_ready(c,uid))
    if not allowed:return
    row=c.execute('SELECT role,active FROM users WHERE id=?',(actor,)).fetchone()
    owner=c.execute('SELECT role,active FROM users WHERE id=?',(uid,)).fetchone()
    life=c.execute('SELECT state FROM account_lifecycle WHERE user_id=?',(uid,)).fetchone()
    if (row is None or tuple(row)!=('admin',1) or owner is None or owner[0]=='admin' or owner[1]
        or life is None or life[0] not in ('deleted','expired','erasing')):raise FenceBlocked('Approved retired-account erasure required for refunds')
    c.create_function('mta_operator_refund_erasure',1,lambda identifier:int(identifier in allowed))
