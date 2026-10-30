"""PayPal Orders v2: server quotes, authenticated capture and idempotent fulfillment.

One-off EUR payments settle subscription receivables or top up overage credits.
No browser return URL, approval event or unverified webhook grants entitlement.
"""
import hashlib
import json
import re
import time
import uuid
from urllib.parse import urlsplit

import httpx
from . import auth, resource_accounts as r

BASES={'sandbox':'https://api-m.sandbox.paypal.com','live':'https://api-m.paypal.com'}


def init(c):
    c.executescript('''
    CREATE TABLE IF NOT EXISTS paypal_config(id INTEGER PRIMARY KEY CHECK(id=1),enabled INTEGER NOT NULL DEFAULT 0,environment TEXT NOT NULL DEFAULT 'sandbox',client_id TEXT NOT NULL DEFAULT '',client_secret TEXT NOT NULL DEFAULT '',webhook_id TEXT NOT NULL DEFAULT '');
    INSERT OR IGNORE INTO paypal_config(id) VALUES(1);
    CREATE TABLE IF NOT EXISTS paypal_orders(id TEXT PRIMARY KEY,user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,request_id TEXT NOT NULL,kind TEXT NOT NULL,period_start INTEGER,amount_cents INTEGER NOT NULL,environment TEXT NOT NULL,client_fingerprint TEXT NOT NULL,provider_order TEXT UNIQUE,checkout_url TEXT,status TEXT NOT NULL DEFAULT 'pending',created_at INTEGER NOT NULL,paid_at INTEGER,refund_due_micro INTEGER NOT NULL DEFAULT 0,UNIQUE(user_id,request_id));
    CREATE TABLE IF NOT EXISTS paypal_captures(id TEXT PRIMARY KEY,order_id TEXT NOT NULL REFERENCES paypal_orders(id) ON DELETE CASCADE,amount_cents INTEGER NOT NULL);
    CREATE TABLE IF NOT EXISTS paypal_refunds(id TEXT PRIMARY KEY,order_id TEXT NOT NULL REFERENCES paypal_orders(id) ON DELETE CASCADE,capture_id TEXT NOT NULL REFERENCES paypal_captures(id) ON DELETE CASCADE,amount_cents INTEGER NOT NULL);
    CREATE TABLE IF NOT EXISTS paypal_events(id TEXT PRIMARY KEY,received_at INTEGER NOT NULL);
    ''')
    from .subscription_receivables import initialize
    initialize(c)


def _keys(c):
    row=dict(c.execute('SELECT * FROM paypal_config WHERE id=1').fetchone())
    for k in ('client_id','client_secret','webhook_id'):row[k]=auth._open(row[k]) if row[k] else ''
    return row


def settings(body=None):
    with auth.db() as c:
        init(c)
        if body is not None:
            if not isinstance(body,dict) or set(body)-{'enabled','environment','client_id','client_secret','webhook_id'}:raise ValueError('Invalid PayPal configuration')
            if 'enabled' in body:
                if type(body['enabled']) is not bool:raise ValueError('Boolean required')
                c.execute('UPDATE paypal_config SET enabled=? WHERE id=1',(int(body['enabled']),))
            if 'environment' in body:
                if body['environment'] not in BASES:raise ValueError('Invalid PayPal environment')
                c.execute('UPDATE paypal_config SET environment=? WHERE id=1',(body['environment'],))
            for key in ('client_id','client_secret','webhook_id'):
                if key in body:
                    value=body[key]
                    if not isinstance(value,str) or len(value)>512 or any(ch.isspace() for ch in value):raise ValueError('Invalid PayPal credential')
                    if value:
                        sql={'client_id':'UPDATE paypal_config SET client_id=? WHERE id=1','client_secret':'UPDATE paypal_config SET client_secret=? WHERE id=1','webhook_id':'UPDATE paypal_config SET webhook_id=? WHERE id=1'}[key]
                        c.execute(sql,(auth._seal(value),))
        row=c.execute('SELECT * FROM paypal_config WHERE id=1').fetchone()
        return {'provider':'paypal','enabled':bool(row['enabled']),'environment':row['environment'],'client_id_set':bool(row['client_id']),'client_secret_set':bool(row['client_secret']),'webhook_id_set':bool(row['webhook_id']),'configured':bool(row['enabled'] and row['client_id'] and row['client_secret'] and row['webhook_id'])}


def _api(config,method,path,payload=None,request_id=None):
    if not config['enabled'] or config['environment'] not in BASES or not config['client_id'] or not config['client_secret']:raise ValueError('PayPal is not configured; contact the administrator')
    base=BASES[config['environment']]
    try:
        with httpx.Client(timeout=30,follow_redirects=False) as client:
            token=client.post(base+'/v1/oauth2/token',auth=(config['client_id'],config['client_secret']),data={'grant_type':'client_credentials'})
            if token.status_code!=200:raise ValueError('PayPal authentication unavailable; contact the administrator')
            bearer=token.json().get('access_token')
            if not isinstance(bearer,str) or not bearer:raise ValueError('Invalid PayPal authentication response')
            headers={'Authorization':'Bearer '+bearer,'Content-Type':'application/json'}
            if request_id:headers['PayPal-Request-Id']=request_id
            result=client.request(method,base+path,json=payload,headers=headers)
    except (httpx.HTTPError,KeyError) as exc:raise ValueError('PayPal unavailable; retry or contact the administrator') from exc
    if result.status_code not in (200,201):raise ValueError('PayPal request failed; retry or contact the administrator')
    return result.json()


def _quote(c,uid,kind,amount=None,period_start=None,refund_id=None,expected_micro=None):
    if kind=='subscription_reversal':
        from .subscription_receivables import quote
        source=quote(c,uid,refund_id,expected_micro)
        return (source['due_micro']+9999)//10000,source['period_start']
    s=r._state(c,uid,0,int(time.time()))
    if kind=='credits':
        if not s['credits_enabled']:raise ValueError('Credits require an enabled credit service and an active subscription')
        cfg=c.execute('SELECT credit_denominations FROM resource_config WHERE id=1').fetchone()
        if type(amount) is not int or amount not in json.loads(cfg[0]):raise ValueError('Credit denomination changed; refresh the page')
        return amount,None
    if kind!='subscription' or type(period_start) is not int:raise ValueError('Invalid subscription payment')
    if not s['policy']['subscriptions_allowed'] or not s['enabled']:raise ValueError('Subscription payments are disabled')
    fee=c.execute("SELECT amount_micro FROM resource_plan_charges WHERE user_id=? AND period_start=? AND status='due'",(uid,period_start)).fetchone()
    if not fee or fee[0]<=0:raise ValueError('No unpaid subscription fee')
    # Payment processors settle cents. Keep quoted sub-cent remainder explicit.
    cents=(fee[0]+9999)//10000
    return cents,period_start


def checkout(uid,body):
    from .service_regime import require_commercial
    require_commercial("checkout")
    if set(body)-{'kind','amount_cents','period_start','request_id','refund_id','expected_due_micro'} or not {'kind','request_id'}<=set(body):raise ValueError('Invalid PayPal purchase')
    if body['kind']=='subscription_reversal':
        if set(body)!={'kind','refund_id','expected_due_micro','request_id'} or type(body['expected_due_micro']) is not int or body['expected_due_micro']<=0:
            raise ValueError('Exact subscription reversal quote required')
    elif {'refund_id','expected_due_micro'}&set(body):raise ValueError('Unexpected repayment target')
    key=body['request_id']
    if not isinstance(key,str) or not 8<=len(key)<=80:raise ValueError('Invalid purchase request ID')
    from .legal import snapshot
    base=snapshot()[0]['public_url'].rstrip('/');url=urlsplit(base)
    if url.scheme!='https' or not url.hostname or url.username or url.password:raise ValueError('Configure the public HTTPS URL first')
    with auth.db() as c:
        from .owner_payments import initialize, guard_pending
        r.init(c);initialize(c);c.execute('BEGIN IMMEDIATE');cfg=_keys(c)
        if not cfg['enabled'] or not cfg['webhook_id']:raise ValueError('PayPal is not configured')
        old=c.execute('SELECT * FROM paypal_orders WHERE user_id=? AND request_id=?',(uid,key)).fetchone()
        if old:
            if old['kind']!=body['kind'] or (body['kind']=='credits' and old['amount_cents']!=body.get('amount_cents')) or (body['kind']=='subscription' and old['period_start']!=body.get('period_start')):raise ValueError('Conflicting purchase retry')
            if body['kind']=='subscription_reversal':
                target=c.execute('SELECT refund_id,quoted_micro FROM subscription_repayment_targets WHERE order_id=?',(old['id'],)).fetchone()
                if target is None or tuple(target)!=(body['refund_id'],body['expected_due_micro']):raise ValueError('Conflicting repayment retry')
            if old['status']=='paid':return {'status':'paid','order_id':old['id']}
            if old['status'] in ('cancelled','canceled','failed','refunded'):return {'status':old['status'],'order_id':old['id']}
        cents,period=_quote(c,uid,body['kind'],body.get('amount_cents'),body.get('period_start'),body.get('refund_id'),body.get('expected_due_micro'))
        fingerprint=hashlib.sha256(cfg['client_id'].encode()).hexdigest()
        if old:
            if (old['kind'],old['amount_cents'],old['period_start'],old['environment'],old['client_fingerprint'])!=(body['kind'],cents,period,cfg['environment'],fingerprint):raise ValueError('Conflicting purchase retry')
            if old['checkout_url']:
                from .owner_payments import safe_url
                target=safe_url(old['checkout_url'],'paypal',old['environment'])
                if old['status']!='pending' or not target:raise ValueError('Checkout needs administrator review')
                return {'checkout_url':target,'order_id':old['id']}
            order=old['id']
            from .regime_checkout_fence import enroll
            enroll(c, 'paypal', order)
        else:
            guard_pending(c,uid,body['kind'],period)
            if body['kind']=='subscription_reversal':
                from .subscription_receivables import quote
                source=quote(c,uid,body['refund_id'],body['expected_due_micro'])
                if source['pending_order_id']:raise ValueError('A subscription repayment checkout is already pending; resume it or contact the administrator')
            order=uuid.uuid4().hex
            c.execute('INSERT INTO paypal_orders(id,user_id,request_id,kind,period_start,amount_cents,environment,client_fingerprint,created_at) VALUES(?,?,?,?,?,?,?,?,?)',(order,uid,key,body['kind'],period,cents,cfg['environment'],fingerprint,int(time.time())))
            if body['kind']=='subscription_reversal':
                c.execute('INSERT INTO subscription_repayment_targets VALUES(?,?,?)',(order,body['refund_id'],body['expected_due_micro']))
            from .regime_checkout_fence import enroll
            enroll(c, 'paypal', order)
        from .regime_payment_outbox import enqueue
        enqueue(c, provider='paypal', order_id=order, request_key='mta-create-'+order)
    from .regime_payment_outbox import mark_attempt_uncertain
    with auth.db() as c:
        c.execute('BEGIN IMMEDIATE')
        mark_attempt_uncertain(c, 'checkout:paypal:'+order)
    payload={'intent':'CAPTURE','purchase_units':[{'reference_id':order,'custom_id':order,'invoice_id':'mta-'+order,'description':'MTA Audio Editor '+body['kind'],'amount':{'currency_code':'EUR','value':f'{cents//100}.{cents%100:02d}'}}], 'payment_source':{'paypal':{'experience_context':{'user_action':'PAY_NOW','shipping_preference':'NO_SHIPPING','return_url':base+('/account?paypal_order=' if body['kind']=='subscription_reversal' else '/account/credits?paypal_order=')+order,'cancel_url':base+'/account/credits?payment=cancelled'}}}}
    result=_api(cfg,'POST','/v2/checkout/orders',payload,'mta-create-'+order)
    pid=result.get('id','')
    links=[x.get('href','') for x in result.get('links',[]) if x.get('rel') in ('payer-action','approve')]
    if not re.fullmatch(r'[A-Z0-9]{6,64}',pid) or len(links)!=1:raise ValueError('Invalid PayPal checkout response')
    from .owner_payments import safe_url
    if not safe_url(links[0],'paypal',cfg['environment']):raise ValueError('Invalid PayPal approval URL')
    with auth.db() as c:
        c.execute('BEGIN IMMEDIATE')
        from .regime_payment_outbox import confirm
        confirm(c, 'checkout:paypal:'+order, provider_reference=pid)
        c.execute('UPDATE paypal_orders SET provider_order=?,checkout_url=? WHERE id=? AND status=?',(pid,links[0],order,'pending'))
    return {'checkout_url':links[0],'order_id':order}


def _cents(amount):
    if (not isinstance(amount,dict) or not isinstance(amount.get('value'),str)
        or not re.fullmatch(r'[0-9]{1,29}(?:\.[0-9]{1,2})?',amount['value'])
        or amount.get('currency_code')!='EUR'):raise ValueError('Invalid PayPal amount')
    whole,_,fraction=amount['value'].partition('.')
    return int(whole)*100+int(fraction.ljust(2,'0'))


def fulfill(local_id,result, *, webhook_event_id=None, webhook_digest=None, _reconciliation=None, _disputes=(), _merchant_context=None, _settlement_context=None):
    from .regime_operation_fence import FenceBlocked
    with auth.db() as c:
        r.init(c);init(c);c.execute('BEGIN IMMEDIATE')
        order=c.execute('SELECT * FROM paypal_orders WHERE id=?',(local_id,)).fetchone()
        if _disputes and _reconciliation is None:raise ValueError('Authenticated history context required')
        if not order:raise ValueError('Unknown PayPal order')
        if _settlement_context is not None:
            if _reconciliation is None:raise ValueError('Original report reconciliation required')
            _settlement_context.verify(c,order,_reconciliation[1],result)
        merchant_event=None
        if _merchant_context is not None:
            if _reconciliation is None:raise ValueError('Authenticated merchant history required')
            from .paypal_merchant_reconcile import before_commit
            merchant_event=before_commit(c,_merchant_context,order,_reconciliation[1],result,_reconciliation[2])
        if _reconciliation is not None:
            initial,cfg,history=_reconciliation
            immutable=('user_id','kind','period_start','amount_cents','environment','client_fingerprint','provider_order')
            if any(order[k]!=initial[k] for k in immutable) or _keys(c)!=cfg:
                raise FenceBlocked('PayPal order or configuration changed during reconciliation')
            historical={item['refund_id']:(item['capture_id'],item['amount_minor']) for item in history}
            for rid,cid,amount in c.execute('SELECT id,capture_id,amount_cents FROM paypal_refunds WHERE order_id=?',(local_id,)):
                if historical.get(rid)!=(cid,amount):raise FenceBlocked('PayPal snapshot omits a locally recorded refund')
        if result.get('id')!=order['provider_order'] or result.get('status')!='COMPLETED':raise ValueError('PayPal payment is not completed')
        units=result.get('purchase_units',[])
        if len(units)!=1 or units[0].get('custom_id')!=local_id or units[0].get('reference_id')!=local_id or _cents(units[0]['amount'])!=order['amount_cents']:raise ValueError('PayPal payment identity or amount mismatch')
        captures=units[0].get('payments',{}).get('captures',[])
        allowed=('COMPLETED','PARTIALLY_REFUNDED','REFUNDED') if _reconciliation is not None else ('COMPLETED',)
        if not captures or len({x.get('id') for x in captures})!=len(captures) or any(x.get('status') not in allowed for x in captures) or sum(_cents(x['amount']) for x in captures)!=order['amount_cents']:raise ValueError('PayPal captures do not match payment')
        if _reconciliation is None and units[0].get('payments',{}).get('refunds'):
            raise ValueError('PayPal refund history requires authenticated reconciliation')
        from .payment_reconciliation import record_event, bind_object, mark_applied
        from .regime_checkout_fence import verify_enrolled_payment
        verify_enrolled_payment(c,'paypal',local_id)
        financial_id=webhook_event_id or 'capture:'+order['provider_order']
        normalized={'type':'capture','provider_order':order['provider_order'],
                    'amount_minor':order['amount_cents'],'kind':order['kind'],
                    'captures':sorted((x['id'],_cents(x['amount'])) for x in captures)}
        digest=webhook_digest or hashlib.sha256(json.dumps(normalized,sort_keys=True).encode()).hexdigest()
        duplicate=record_event(c,'paypal',financial_id,digest,normalized)
        if _reconciliation is None:
            for row in c.execute("SELECT normalized_json FROM payment_reconciliation_events WHERE provider='paypal' AND order_id=? AND state='pending'",(local_id,)):
                if json.loads(row[0]).get('type')=='paypal_history_gap':
                    raise FenceBlocked('Complete PayPal history reconciliation before ordinary fulfillment')
        if _reconciliation is not None:
            # Frozen authenticated history enters the same transaction as funding.
            # Even an already-applied capture must replay newly discovered refunds.
            for data in history:
                encoded=json.dumps(data,sort_keys=True).encode()
                record_event(c,'paypal','reconcile:refund:'+data['refund_id'],hashlib.sha256(encoded).hexdigest(),data)
        if _reconciliation is not None:
            if _settlement_context is not None:_settlement_context.claim(c,_disputes)
            for data in _disputes:
                encoded=json.dumps(data,sort_keys=True).encode();key=hashlib.sha256(encoded).hexdigest()
                record_event(c,'paypal','reconcile:risk:'+key,key,data)
            # Existing locally known disputes cannot disappear from a complete
            # collection; an omitted terminal result is still not a release.
            if c.execute("SELECT 1 FROM sqlite_master WHERE name='paypal_financial_holds'").fetchone():
                discovered={x['hold_id'] for x in _disputes}
                for row in c.execute("SELECT hold_id FROM paypal_financial_holds WHERE order_id=? AND kind='dispute'",(local_id,)):
                    if row[0] not in discovered:raise FenceBlocked('PayPal history omits a recorded dispute')
            from .payment_reconciliation import mark_applied
            for row in c.execute("SELECT normalized_json FROM payment_reconciliation_events WHERE provider='paypal' AND order_id=? AND state='pending'",(local_id,)):
                gap=json.loads(row[0])
                if gap.get('type')=='paypal_history_gap' and not set(gap.get('required_dispute_ids',[]))<={x['hold_id'].split(':')[1] for x in _disputes}:
                    raise FenceBlocked('PayPal history omits a previously observed dispute')
            from .paypal_dispute_history import close_gaps
            close_gaps(c,local_id)
        bind_object(c,'paypal',order['provider_order'],local_id)
        for item in captures:bind_object(c,'paypal',item['id'],local_id)
        from .checkout_terminal_outcomes import block_paid_after_terminal
        if block_paid_after_terminal(c,'paypal',local_id,financial_id):
            return {'status':'pending','order_id':local_id,'pending':True,'conflict':True}
        if order['status']=='paid':
            stored=sorted(tuple(x) for x in c.execute('SELECT id,amount_cents FROM paypal_captures WHERE order_id=?',(local_id,)))
            if stored!=[tuple(x) for x in normalized['captures']]:raise ValueError('Paid capture identity changed')
            _record_position(c,order,financial_id)
            mark_applied(c,'paypal',financial_id,local_id)
            _replay_pending_refunds(c,local_id)
            if merchant_event:mark_applied(c,'paypal',merchant_event,local_id)
            if webhook_event_id is not None:
                c.execute('INSERT OR IGNORE INTO paypal_events VALUES(?,?)',(webhook_event_id,int(time.time())))
            return {'status':'paid','order_id':local_id,'duplicate':duplicate}
        for capture in captures:
            if not re.fullmatch(r'[A-Z0-9]{6,64}',str(capture.get('id',''))):raise ValueError('Invalid capture ID')
            c.execute('INSERT INTO paypal_captures VALUES(?,?,?)',(capture['id'],local_id,_cents(capture['amount'])))
        refund=0
        if order['kind']=='credits':
            c.execute('INSERT INTO resource_credits VALUES(?,?,?,?,?,?)',('paypal:'+local_id,order['user_id'],order['amount_cents']*10000,None,'PayPal credit purchase: '+local_id,int(time.time())))
        elif order['kind']=='subscription_reversal':
            from .subscription_receivables import allocate
            refund=allocate(c,order)
        else:
            fee=c.execute('SELECT * FROM resource_plan_charges WHERE user_id=? AND period_start=?',(order['user_id'],order['period_start'])).fetchone()
            if not fee:raise ValueError('Subscription receivable missing')
            refund=max(0,order['amount_cents']*10000-(fee['amount_micro'] if fee['status']=='due' else 0))
            c.execute("UPDATE resource_plan_charges SET status='paid' WHERE user_id=? AND period_start=?",(order['user_id'],order['period_start']))
            from .subscription_receivables import freeze_original_payment
            freeze_original_payment(c,order,refund)
        c.execute("UPDATE paypal_orders SET status='paid',paid_at=?,refund_due_micro=? WHERE id=?",(int(time.time()),refund,local_id))
        from .regime_checkout_fence import settle_if_enrolled
        settle_if_enrolled(c, 'paypal', local_id)
        _record_position(c,order,financial_id)
        mark_applied(c,'paypal',financial_id,local_id)
        _replay_pending_refunds(c,local_id)
        if merchant_event:mark_applied(c,'paypal',merchant_event,local_id)
        if webhook_event_id is not None:
            c.execute('INSERT INTO paypal_events VALUES(?,?)',(webhook_event_id,int(time.time())))
    return {'status':'paid','order_id':local_id,'refund_due_micro':refund}


def capture(uid,local_id):
    with auth.db() as c:
        r.init(c);init(c);order=c.execute('SELECT * FROM paypal_orders WHERE id=? AND user_id=?',(local_id,uid)).fetchone();cfg=_keys(c)
        if not order:raise ValueError('Unknown PayPal order')
        if order['status']=='paid':return {'status':'paid','order_id':local_id}
        if order['status'] in ('cancelled','canceled','failed','refunded'):raise ValueError('Checkout is closed; create a new explicit purchase if needed')
        if order['environment']!=cfg['environment'] or order['client_fingerprint']!=hashlib.sha256(cfg['client_id'].encode()).hexdigest():raise ValueError('Payment configuration changed; contact the administrator')
        pid=order['provider_order']
        if not pid:raise ValueError('Checkout is not ready')
        # Revalidate the quote before collecting money after a quota/contract change.
        target=c.execute('SELECT refund_id,quoted_micro FROM subscription_repayment_targets WHERE order_id=?',(local_id,)).fetchone() if order['kind']=='subscription_reversal' else None
        if order['kind']=='subscription_reversal' and target is None:raise ValueError('Subscription repayment target missing')
        cents,_=_quote(c,uid,order['kind'],order['amount_cents'],order['period_start'],target[0] if target else None,target[1] if target else None)
        if cents!=order['amount_cents']:raise ValueError('Payment amount changed; refresh the page')
    current=_api(cfg,'GET','/v2/checkout/orders/'+pid)
    if current.get('status')=='APPROVED':
        from .service_regime import require_commercial
        require_commercial('capture')
        # Recheck the exact original owner, merchant, quote and admission after
        # network readback, before collecting any new money. Already completed
        # receipts still use the historical reconciliation path below.
        with auth.db() as c:
            c.execute('BEGIN IMMEDIATE')
            fresh=c.execute('SELECT * FROM paypal_orders WHERE id=?',(local_id,)).fetchone()
            immutable=('user_id','kind','period_start','amount_cents','environment','client_fingerprint','provider_order')
            if fresh is None or fresh['status']!='pending' or any(fresh[k]!=order[k] for k in immutable) or _keys(c)!=cfg:
                from .regime_operation_fence import FenceBlocked
                raise FenceBlocked('Payment changed during approval verification')
            active=c.execute('SELECT active FROM users WHERE id=?',(uid,)).fetchone()
            if active is None or not active[0]:raise ValueError('Active payment owner required')
            has_events=c.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='payment_reconciliation_events'").fetchone()
            if has_events and c.execute("SELECT 1 FROM payment_reconciliation_events WHERE provider='paypal' AND order_id=? AND state='pending' LIMIT 1",(local_id,)).fetchone():
                raise ValueError('Resolve pending payment evidence before capture')
            cents,period=_quote(c,uid,order['kind'],order['amount_cents'],order['period_start'],target[0] if target else None,target[1] if target else None)
            if cents!=order['amount_cents'] or period!=order['period_start']:raise ValueError('Payment quote changed during approval verification')
            from .regime_outcome_receipt import require_open_commercial_checkout
            require_open_commercial_checkout(c,'checkout:paypal:'+local_id)
            dispatch=c.execute('SELECT state,provider_reference FROM regime_payment_outbox WHERE operation_id=?',('checkout:paypal:'+local_id,)).fetchone()
            if dispatch is None or tuple(dispatch)!=('confirmed',pid):raise ValueError('Verified original checkout dispatch required')
        _api(cfg,'POST','/v2/checkout/orders/'+pid+'/capture',{},'mta-capture-'+local_id)
        current=_api(cfg,'GET','/v2/checkout/orders/'+pid)
    return fulfill(local_id,current)


def webhook(raw,headers):
    if len(raw)>1024*1024:raise ValueError('Webhook too large')
    payload=json.loads(raw)
    if not isinstance(payload,dict) or not isinstance(payload.get('id'),str) or len(payload['id'])>200:raise ValueError('Invalid webhook')
    with auth.db() as c:init(c);cfg=_keys(c)
    verification={'webhook_id':cfg['webhook_id'],'webhook_event':payload}
    for key,header in [('auth_algo','paypal-auth-algo'),('cert_url','paypal-cert-url'),('transmission_id','paypal-transmission-id'),('transmission_sig','paypal-transmission-sig'),('transmission_time','paypal-transmission-time')]:
        value=headers.get(header,'')
        if not value or len(value)>4096:raise ValueError('Missing PayPal signature')
        verification[key]=value
    if not cfg['webhook_id'] or _api(cfg,'POST','/v1/notifications/verify-webhook-signature',verification).get('verification_status')!='SUCCESS':raise ValueError('Invalid PayPal signature')
    if payload.get('event_type') in ('PAYMENT.CAPTURE.REVERSED','CUSTOMER.DISPUTE.CREATED','CUSTOMER.DISPUTE.UPDATED','CUSTOMER.DISPUTE.RESOLVED'):
        return financial_risk_event(payload,cfg,hashlib.sha256(raw).hexdigest())
    if payload.get('event_type')=='PAYMENT.CAPTURE.REFUNDED':return refund_event(payload,cfg,webhook_digest=hashlib.sha256(raw).hexdigest())
    if payload.get('event_type')!='PAYMENT.CAPTURE.COMPLETED':return {'received':True}
    pid=payload.get('resource',{}).get('supplementary_data',{}).get('related_ids',{}).get('order_id','')
    if not re.fullmatch(r'[A-Z0-9]{6,64}',str(pid)):raise ValueError('Invalid PayPal order ID')
    with auth.db() as c:
        order=c.execute('SELECT * FROM paypal_orders WHERE provider_order=?',(pid,)).fetchone()
    if not order:raise ValueError('Unknown PayPal order')
    if order['environment']!=cfg['environment'] or order['client_fingerprint']!=hashlib.sha256(cfg['client_id'].encode()).hexdigest():raise ValueError('Payment configuration changed')
    # Commit the verified webhook identity and economic fulfillment together.
    # Retrying after a crash cannot leave money credited but the event unrecorded.
    fulfill(order['id'],_api(cfg,'GET','/v2/checkout/orders/'+pid),webhook_event_id=payload['id'],webhook_digest=hashlib.sha256(raw).hexdigest())
    return {'received':True}


def _refund_capture(resource,environment):
    captures=[]
    allowed=urlsplit(BASES[environment]).hostname
    for link in resource.get('links',[]):
        url=urlsplit(link.get('href',''))
        match=re.fullmatch(r'/v2/payments/captures/([A-Z0-9]{6,64})',url.path)
        if link.get('rel')=='up' and url.scheme=='https' and url.hostname==allowed and not url.username and not url.password and not url.query and not url.fragment and match:
            captures.append(match[1])
    if len(captures)!=1:raise ValueError('Refund capture reference missing or ambiguous')
    return captures[0]


def _record_position(c,order,event_id):
    from .payment_reconciliation import initialize
    initialize(c)
    refunded=c.execute('SELECT coalesce(sum(amount_cents),0) FROM paypal_refunds WHERE order_id=?',(order['id'],)).fetchone()[0]
    held=_held_minor(c,order['id'])
    net=max(0,order['amount_cents']-refunded-held)*10000
    if not 0<=refunded<=order['amount_cents']:raise ValueError('Invalid PayPal refund balance')
    c.execute('''INSERT INTO payment_reconciliation_positions
      (provider,order_id,user_id,amount_minor,currency,refunded_minor,held_minor,net_micro,funded)
      VALUES('paypal',?,?,?,'EUR',?,?,?,1)
      ON CONFLICT(provider,order_id) DO UPDATE SET refunded_minor=excluded.refunded_minor,held_minor=excluded.held_minor,net_micro=excluded.net_micro''',
      (order['id'],order['user_id'],order['amount_cents'],refunded,held,net))
    if order['kind']=='credits':
        # Record the exact already-staged movement, never add a second credit.
        cid='paypal:'+order['id']
        previous=c.execute('SELECT 1 FROM payment_reconciliation_movements WHERE credit_id=?',(cid,)).fetchone()
        if not previous:
            credit=c.execute('SELECT user_id,delta_micro FROM resource_credits WHERE id=?',(cid,)).fetchone()
            if credit is None or tuple(credit)!=(order['user_id'],order['amount_cents']*10000):raise ValueError('PayPal purchase ledger mismatch')
            c.execute("INSERT INTO payment_reconciliation_movements VALUES('paypal',?,?,?,?)",(event_id,cid,order['id'],credit[1]))
    elif order['kind']=='subscription_reversal':
        from .subscription_receivables import sync
        sync(c)


def _apply_refund(c,normalized,event_id):
    from .payment_reconciliation import mark_applied
    capture_id=normalized['capture_id'];rid=normalized['refund_id'];amount=normalized['amount_minor']
    capture=c.execute('SELECT * FROM paypal_captures WHERE id=?',(capture_id,)).fetchone()
    if capture is None:return False
    order=c.execute('SELECT * FROM paypal_orders WHERE id=?',(capture['order_id'],)).fetchone()
    from .regime_checkout_fence import verify_enrolled_payment
    verify_enrolled_payment(c,'paypal',order['id'])
    if (order['environment'],order['client_fingerprint'])!=(normalized['environment'],normalized['merchant_fingerprint']):raise ValueError('Refund merchant mismatch')
    previous=c.execute('SELECT order_id,capture_id,amount_cents FROM paypal_refunds WHERE id=?',(rid,)).fetchone()
    if previous:
        if tuple(previous)!=(order['id'],capture_id,amount):raise ValueError('Conflicting refund identity')
    else:
        prior=c.execute('SELECT coalesce(sum(amount_cents),0) FROM paypal_refunds WHERE capture_id=?',(capture_id,)).fetchone()[0]
        if amount<=0 or prior+amount>capture['amount_cents']:raise ValueError('Invalid refund amount')
        c.execute('INSERT INTO paypal_refunds VALUES(?,?,?,?)',(rid,order['id'],capture_id,amount))
        if order['kind']=='credits':
            old_net=c.execute("SELECT net_micro FROM payment_reconciliation_positions WHERE provider='paypal' AND order_id=?",(order['id'],)).fetchone()
            if old_net is None:raise ValueError('PayPal financial position missing')
            _record_position(c,order,'capture:'+order['provider_order'])
            new_net=c.execute("SELECT net_micro FROM payment_reconciliation_positions WHERE provider='paypal' AND order_id=?",(order['id'],)).fetchone()[0]
            delta=new_net-old_net[0]
            if delta:
                cid='paypal-refund:'+rid
                c.execute('INSERT INTO resource_credits VALUES(?,?,?,?,?,?)',(cid,order['user_id'],delta,None,'PayPal credit refund: '+order['id'],int(time.time())))
                c.execute("INSERT INTO payment_reconciliation_movements VALUES('paypal',?,?,?,?)",(event_id,cid,order['id'],delta))
        elif order['kind']=='subscription':
            # Record authenticated cash even for legacy orders, but never infer
            # the original fee from today's mutable refundable balance.
            from .subscription_receivables import original_loss_position
            position=original_loss_position(c,order)
            if position is not None:
                target, remaining_surplus = position
                allocated=c.execute('SELECT coalesce(sum(amount_micro),0) FROM paypal_subscription_reversals WHERE order_id=?',(order['id'],)).fetchone()[0]
                if allocated > target:
                    raise ValueError('Subscription obligation exceeds proved original loss')
                receivable=max(0,target-allocated)
                c.execute('INSERT INTO paypal_subscription_reversals VALUES(?,?,?,?,?)',(rid,order['id'],order['user_id'],order['period_start'],receivable))
                c.execute('UPDATE paypal_orders SET refund_due_micro=? WHERE id=?',(remaining_surplus,order['id']))
        if order['kind']!='subscription':
            c.execute('UPDATE paypal_orders SET refund_due_micro=max(0,refund_due_micro-?) WHERE id=?',(amount*10000,order['id']))
    _record_position(c,order,'capture:'+order['provider_order'])
    mark_applied(c,'paypal',event_id,order['id'])
    c.execute('INSERT OR IGNORE INTO paypal_events VALUES(?,?)',(event_id,int(time.time())))
    return True


def _replay_pending_refunds(c,local_id):
    capture_ids={row[0] for row in c.execute('SELECT id FROM paypal_captures WHERE order_id=?',(local_id,))}
    pending=c.execute("SELECT event_id,normalized_json FROM payment_reconciliation_events WHERE provider='paypal' AND state='pending'").fetchall()
    for event_id,raw in pending:
        data=json.loads(raw)
        if data.get('capture_id') in capture_ids:
            if data.get('type')=='refund':_apply_refund(c,data,event_id)
            elif data.get('type')=='risk':_apply_risk(c,data,event_id)


def refund_event(payload,cfg,*,webhook_digest=None):
    resource=payload.get('resource',{});rid=str(resource.get('id',''))
    if not re.fullmatch(r'[A-Z0-9]{6,64}',rid):raise ValueError('Invalid PayPal refund ID')
    capture_id=_refund_capture(resource,cfg['environment'])
    # Fixed provider endpoint; never follow a supplied URL. Revalidate canonical
    # linkage so a signed refund cannot be attributed to a different capture.
    canonical=_api(cfg,'GET','/v2/payments/refunds/'+rid)
    if canonical.get('id')!=rid or canonical.get('status')!='COMPLETED':raise ValueError('Refund is not completed')
    if _refund_capture(canonical,cfg['environment'])!=capture_id:raise ValueError('Canonical refund capture mismatch')
    amount=_cents(canonical['amount'])
    normalized={'type':'refund','refund_id':rid,'capture_id':capture_id,'amount_minor':amount,
                'environment':cfg['environment'],'merchant_fingerprint':hashlib.sha256(cfg['client_id'].encode()).hexdigest()}
    digest=webhook_digest or hashlib.sha256(json.dumps(payload,sort_keys=True).encode()).hexdigest()
    from .payment_reconciliation import record_event
    with auth.db() as c:
        r.init(c);init(c);c.execute('BEGIN IMMEDIATE')
        if record_event(c,'paypal',payload['id'],digest,normalized):return {'received':True,'duplicate':True}
        applied=_apply_refund(c,normalized,payload['id'])
    return {'received':True,'pending':not applied}


def _risk_schema(c):
    c.execute('''CREATE TABLE IF NOT EXISTS paypal_financial_holds(
      hold_id TEXT PRIMARY KEY,order_id TEXT NOT NULL,capture_id TEXT NOT NULL,
      amount_cents INTEGER NOT NULL CHECK(amount_cents>0),status TEXT NOT NULL,
      updated_ms INTEGER NOT NULL,kind TEXT NOT NULL)''')


def _held_minor(c,order_id):
    if not c.execute("SELECT 1 FROM sqlite_master WHERE name='paypal_financial_holds'").fetchone():return 0
    total=0
    for capture_id,amount in c.execute('SELECT id,amount_cents FROM paypal_captures WHERE order_id=?',(order_id,)):
        refunded=c.execute('SELECT coalesce(sum(amount_cents),0) FROM paypal_refunds WHERE capture_id=?',(capture_id,)).fetchone()[0]
        exposure=c.execute("SELECT coalesce(sum(amount_cents),0) FROM paypal_financial_holds WHERE capture_id=? AND status!='released'",(capture_id,)).fetchone()[0]
        total+=min(max(0,amount-refunded),exposure)
    return total


def _apply_risk(c,data,event_id):
    from .payment_reconciliation import mark_applied
    capture=c.execute('SELECT * FROM paypal_captures WHERE id=?',(data['capture_id'],)).fetchone()
    if capture is None:return False
    order=c.execute('SELECT * FROM paypal_orders WHERE id=?',(capture['order_id'],)).fetchone()
    if (order['environment'],order['client_fingerprint'])!=(data['environment'],data['merchant_fingerprint']):raise ValueError('Risk event merchant mismatch')
    if not 0<data['amount_minor']<=capture['amount_cents']:raise ValueError('Risk event amount mismatch')
    from .regime_checkout_fence import verify_enrolled_payment
    verify_enrolled_payment(c,'paypal',order['id'])
    _risk_schema(c)
    old=c.execute('SELECT capture_id,amount_cents,status,updated_ms,kind,order_id FROM paypal_financial_holds WHERE hold_id=?',(data['hold_id'],)).fetchone()
    if old and (old[0],old[1],old[4],old[5])!=(data['capture_id'],data['amount_minor'],data['kind'],order['id']):raise ValueError('Risk event identity changed')
    # Associate unresolved evidence with its verified local owner/order too.
    c.execute("UPDATE payment_reconciliation_events SET order_id=? WHERE provider='paypal' AND event_id=? AND state='pending'",(order['id'],event_id))
    # A replay of the identical canonical case must retain its original
    # authenticated report resolution. Changed case bytes still require review.
    if old and old[2]=='released' and data['status']=='uncertain' and data.get('dispute_document_sha256'):
        from .paypal_report_reconciliation import verified_replay
        if verified_replay(c,data):
            mark_applied(c,'paypal',event_id,order['id'])
            return True
    if old and old[2] in ('released','permanent') and data['status']!=old[2]:
        if data['status'] not in ('released','permanent') and data['updated_ms']<old[3]:
            mark_applied(c,'paypal',event_id,order['id'])
            c.execute('INSERT OR IGNORE INTO paypal_events VALUES(?,?)',(event_id,int(time.time())))
            return True  # Older provisional evidence cannot reopen a final result.
        # A terminal provider outcome is not undone by a newer provisional or
        # contradictory terminal document. Preserve it as durable pending.
        return False
    report_upgrade = (old and old[2]=='uncertain' and data['status']=='released'
                      and data.get('settlement_report_proof',{}).get('schema')=='mta-paypal-defended-settlement-1')
    if old and old[3]==data['updated_ms'] and old[2]!=data['status'] and not report_upgrade:raise ValueError('Ambiguous risk event order')
    position=c.execute("SELECT net_micro FROM payment_reconciliation_positions WHERE provider='paypal' AND order_id=?",(order['id'],)).fetchone()
    if position is None:raise ValueError('PayPal financial position missing')
    if not old or data['updated_ms']>old[3] or (report_upgrade and data['updated_ms']==old[3]):
        c.execute('''INSERT INTO paypal_financial_holds VALUES(?,?,?,?,?,?,?)
          ON CONFLICT(hold_id) DO UPDATE SET status=excluded.status,updated_ms=excluded.updated_ms''',
          (data['hold_id'],order['id'],data['capture_id'],data['amount_minor'],data['status'],data['updated_ms'],data['kind']))
    _record_position(c,order,'capture:'+order['provider_order'])
    target=c.execute("SELECT net_micro FROM payment_reconciliation_positions WHERE provider='paypal' AND order_id=?",(order['id'],)).fetchone()[0]
    delta=target-position[0]
    if order['kind']=='subscription' and data['status']=='permanent':
        from .subscription_receivables import accrue_original_loss
        accrue_original_loss(c,order,data['hold_id'])
    if delta and order['kind']=='credits':
        cid='paypal-risk:'+event_id
        c.execute('INSERT INTO resource_credits VALUES(?,?,?,?,?,?)',(cid,order['user_id'],delta,None,'PayPal risk adjustment: '+order['id'],int(time.time())))
        c.execute("INSERT INTO payment_reconciliation_movements VALUES('paypal',?,?,?,?)",(event_id,cid,order['id'],delta))
    if data['status']=='uncertain':return False
    mark_applied(c,'paypal',event_id,order['id'])
    # Superseded unresolved snapshots remain in the audit trail, but stop
    # blocking once the provider supplies a later unambiguous resolution.
    for pending_id,raw in c.execute("SELECT event_id,normalized_json FROM payment_reconciliation_events WHERE provider='paypal' AND state='pending'").fetchall():
        prior=json.loads(raw)
        same_report_resolution=(data['status']=='released' and data.get('settlement_report_proof')
            and prior.get('status')=='uncertain' and prior.get('dispute_document_sha256')
            and prior.get('dispute_document_sha256')==data.get('dispute_document_sha256')
            and prior.get('updated_ms')==data['updated_ms'])
        if (prior.get('hold_id')==data['hold_id'] and (prior.get('updated_ms',0)<data['updated_ms'] or same_report_resolution)
            and not (prior.get('status') in ('released','permanent') and prior['status']!=data['status'])):
            mark_applied(c,'paypal',pending_id,order['id'])
    c.execute('INSERT OR IGNORE INTO paypal_events VALUES(?,?)',(event_id,int(time.time())))
    return True


def financial_risk_event(payload,cfg,digest):
    from .payment_reconciliation import record_event
    # Verification of the webhook has already succeeded. Re-delivery uses the
    # original immutable canonical snapshot rather than changing event identity.
    with auth.db() as c:
        exists=c.execute("SELECT 1 FROM sqlite_master WHERE name='payment_reconciliation_events'").fetchone()
        old=c.execute("SELECT digest,normalized_json,state FROM payment_reconciliation_events WHERE provider='paypal' AND event_id=?",(payload['id'],)).fetchone() if exists else None
    if old:
        if old[0]!=digest:raise ValueError('Conflicting PayPal event identity')
        if old[2]=='applied':return {'received':True,'duplicate':True}
        data=json.loads(old[1])
    else:
        resource=payload.get('resource',{});kind=payload['event_type']
        fingerprint=hashlib.sha256(cfg['client_id'].encode()).hexdigest()
        if kind=='PAYMENT.CAPTURE.REVERSED':
            capture_id=resource.get('id')
            if not isinstance(capture_id,str) or not re.fullmatch('[A-Z0-9]{6,64}',capture_id):raise ValueError('Invalid reversal capture')
            amount=_cents(resource.get('amount'))
            # A verified reversal notification is authoritative for this capture;
            # a later ordinary COMPLETED snapshot must not undo the reversal.
            data={'hold_id':'reversal:'+capture_id,'capture_id':capture_id,'amount_minor':amount,
                  'status':'permanent','updated_ms':0,'kind':'reversal'}
        else:
            did=resource.get('dispute_id')
            if not isinstance(did,str) or not re.fullmatch('[A-Za-z0-9-]{1,100}',did):raise ValueError('Invalid dispute ID')
            canonical=_api(cfg,'GET','/v1/customer/disputes/'+did)
            if canonical.get('dispute_id')!=did:raise ValueError('Dispute identity mismatch')
            from .paypal_dispute_history import normalize
            normalized=normalize(canonical,cfg)
            if len(normalized)!=1:raise ValueError('Multicapture webhook requires complete history reconciliation')
            data=normalized[0]
        data.update(type='risk',environment=cfg['environment'],merchant_fingerprint=fingerprint)
    with auth.db() as c:
        r.init(c);init(c);c.execute('BEGIN IMMEDIATE')
        if record_event(c,'paypal',payload['id'],digest,data):return {'received':True,'duplicate':True}
        applied=_apply_risk(c,data,payload['id'])
    return {'received':True,'pending':not applied}
