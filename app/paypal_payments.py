"""PayPal Orders v2: server quotes, authenticated capture and idempotent fulfillment.

One-off EUR payments settle subscription receivables or top up overage credits.
No browser return URL, approval event or unverified webhook grants entitlement.
"""
from decimal import Decimal, InvalidOperation
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


def _quote(c,uid,kind,amount=None,period_start=None):
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
    if set(body)-{'kind','amount_cents','period_start','request_id'} or not {'kind','request_id'}<=set(body):raise ValueError('Invalid PayPal purchase')
    key=body['request_id']
    if not isinstance(key,str) or not 8<=len(key)<=80:raise ValueError('Invalid purchase request ID')
    from .legal import snapshot
    base=snapshot()[0]['public_url'].rstrip('/');url=urlsplit(base)
    if url.scheme!='https' or not url.hostname or url.username or url.password:raise ValueError('Configure the public HTTPS URL first')
    with auth.db() as c:
        r.init(c);init(c);c.execute('BEGIN IMMEDIATE');cfg=_keys(c)
        if not cfg['enabled'] or not cfg['webhook_id']:raise ValueError('PayPal is not configured')
        old=c.execute('SELECT * FROM paypal_orders WHERE user_id=? AND request_id=?',(uid,key)).fetchone()
        if old:
            if old['kind']!=body['kind'] or (body['kind']=='credits' and old['amount_cents']!=body.get('amount_cents')) or (body['kind']=='subscription' and old['period_start']!=body.get('period_start')):raise ValueError('Conflicting purchase retry')
            if old['status']=='paid':return {'status':'paid','order_id':old['id']}
        cents,period=_quote(c,uid,body['kind'],body.get('amount_cents'),body.get('period_start'))
        fingerprint=hashlib.sha256(cfg['client_id'].encode()).hexdigest()
        if old:
            if (old['kind'],old['amount_cents'],old['period_start'],old['environment'],old['client_fingerprint'])!=(body['kind'],cents,period,cfg['environment'],fingerprint):raise ValueError('Conflicting purchase retry')
            if old['checkout_url']:return {'checkout_url':old['checkout_url'],'order_id':old['id']}
            order=old['id']
        else:
            order=uuid.uuid4().hex
            c.execute('INSERT INTO paypal_orders(id,user_id,request_id,kind,period_start,amount_cents,environment,client_fingerprint,created_at) VALUES(?,?,?,?,?,?,?,?,?)',(order,uid,key,body['kind'],period,cents,cfg['environment'],fingerprint,int(time.time())))
    payload={'intent':'CAPTURE','purchase_units':[{'reference_id':order,'custom_id':order,'invoice_id':'mta-'+order,'description':'MTA Audio Editor '+body['kind'],'amount':{'currency_code':'EUR','value':f'{cents//100}.{cents%100:02d}'}}], 'payment_source':{'paypal':{'experience_context':{'user_action':'PAY_NOW','shipping_preference':'NO_SHIPPING','return_url':base+'/account/credits?paypal_order='+order,'cancel_url':base+'/account/credits?payment=cancelled'}}}}
    result=_api(cfg,'POST','/v2/checkout/orders',payload,'mta-create-'+order)
    pid=result.get('id','')
    links=[x.get('href','') for x in result.get('links',[]) if x.get('rel') in ('payer-action','approve')]
    allowed='www.sandbox.paypal.com' if cfg['environment']=='sandbox' else 'www.paypal.com'
    if not re.fullmatch(r'[A-Z0-9]{6,64}',pid) or len(links)!=1:raise ValueError('Invalid PayPal checkout response')
    target=urlsplit(links[0])
    if target.scheme!='https' or target.hostname!=allowed or target.username or target.password:raise ValueError('Invalid PayPal approval URL')
    with auth.db() as c:c.execute('UPDATE paypal_orders SET provider_order=?,checkout_url=? WHERE id=? AND status=?',(pid,links[0],order,'pending'))
    return {'checkout_url':links[0],'order_id':order}


def _cents(amount):
    try:
        value=Decimal(amount['value'])*100
        if amount['currency_code']!='EUR' or not value.is_finite() or value!=value.to_integral_value() or value<0:raise ValueError('Invalid PayPal amount')
        return int(value)
    except (KeyError,InvalidOperation,TypeError) as exc:raise ValueError('Invalid PayPal amount') from exc


def fulfill(local_id,result):
    with auth.db() as c:
        r.init(c);init(c);c.execute('BEGIN IMMEDIATE')
        order=c.execute('SELECT * FROM paypal_orders WHERE id=?',(local_id,)).fetchone()
        if not order:raise ValueError('Unknown PayPal order')
        if result.get('id')!=order['provider_order'] or result.get('status')!='COMPLETED':raise ValueError('PayPal payment is not completed')
        units=result.get('purchase_units',[])
        if len(units)!=1 or units[0].get('custom_id')!=local_id or units[0].get('reference_id')!=local_id or _cents(units[0]['amount'])!=order['amount_cents']:raise ValueError('PayPal payment identity or amount mismatch')
        captures=units[0].get('payments',{}).get('captures',[])
        if not captures or len({x.get('id') for x in captures})!=len(captures) or any(x.get('status')!='COMPLETED' for x in captures) or sum(_cents(x['amount']) for x in captures)!=order['amount_cents']:raise ValueError('PayPal captures do not match payment')
        if order['status']=='paid':return {'status':'paid','order_id':local_id}
        for capture in captures:
            if not re.fullmatch(r'[A-Z0-9]{6,64}',str(capture.get('id',''))):raise ValueError('Invalid capture ID')
            c.execute('INSERT INTO paypal_captures VALUES(?,?,?)',(capture['id'],local_id,_cents(capture['amount'])))
        refund=0
        if order['kind']=='credits':
            c.execute('INSERT INTO resource_credits VALUES(?,?,?,?,?,?)',('paypal:'+local_id,order['user_id'],order['amount_cents']*10000,None,'PayPal credit purchase: '+local_id,int(time.time())))
        else:
            fee=c.execute('SELECT * FROM resource_plan_charges WHERE user_id=? AND period_start=?',(order['user_id'],order['period_start'])).fetchone()
            if not fee:raise ValueError('Subscription receivable missing')
            refund=max(0,order['amount_cents']*10000-(fee['amount_micro'] if fee['status']=='due' else 0))
            c.execute("UPDATE resource_plan_charges SET status='paid' WHERE user_id=? AND period_start=?",(order['user_id'],order['period_start']))
        c.execute("UPDATE paypal_orders SET status='paid',paid_at=?,refund_due_micro=? WHERE id=?",(int(time.time()),refund,local_id))
    return {'status':'paid','order_id':local_id,'refund_due_micro':refund}


def capture(uid,local_id):
    with auth.db() as c:
        r.init(c);init(c);order=c.execute('SELECT * FROM paypal_orders WHERE id=? AND user_id=?',(local_id,uid)).fetchone();cfg=_keys(c)
        if not order:raise ValueError('Unknown PayPal order')
        if order['status']=='paid':return {'status':'paid','order_id':local_id}
        if order['environment']!=cfg['environment'] or order['client_fingerprint']!=hashlib.sha256(cfg['client_id'].encode()).hexdigest():raise ValueError('Payment configuration changed; contact the administrator')
        pid=order['provider_order']
        if not pid:raise ValueError('Checkout is not ready')
        # Revalidate the quote before collecting money after a quota/contract change.
        cents,_=_quote(c,uid,order['kind'],order['amount_cents'],order['period_start'])
        if cents!=order['amount_cents']:raise ValueError('Payment amount changed; refresh the page')
    current=_api(cfg,'GET','/v2/checkout/orders/'+pid)
    if current.get('status')=='APPROVED':
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
    if payload.get('event_type')=='PAYMENT.CAPTURE.REFUNDED':return refund_event(payload,cfg)
    if payload.get('event_type')!='PAYMENT.CAPTURE.COMPLETED':return {'received':True}
    pid=payload.get('resource',{}).get('supplementary_data',{}).get('related_ids',{}).get('order_id','')
    if not re.fullmatch(r'[A-Z0-9]{6,64}',str(pid)):raise ValueError('Invalid PayPal order ID')
    with auth.db() as c:
        if c.execute('SELECT 1 FROM paypal_events WHERE id=?',(payload['id'],)).fetchone():return {'received':True}
        order=c.execute('SELECT * FROM paypal_orders WHERE provider_order=?',(pid,)).fetchone()
    if not order:raise ValueError('Unknown PayPal order')
    if order['environment']!=cfg['environment'] or order['client_fingerprint']!=hashlib.sha256(cfg['client_id'].encode()).hexdigest():raise ValueError('Payment configuration changed')
    fulfill(order['id'],_api(cfg,'GET','/v2/checkout/orders/'+pid))
    with auth.db() as c:c.execute('INSERT OR IGNORE INTO paypal_events VALUES(?,?)',(payload['id'],int(time.time())))
    return {'received':True}


def refund_event(payload,cfg):
    resource=payload.get('resource',{});rid=str(resource.get('id',''))
    if not re.fullmatch(r'[A-Z0-9]{6,64}',rid):raise ValueError('Invalid PayPal refund ID')
    # The provider verifies the webhook. Never follow a URL from its payload.
    capture_id=None
    for link in resource.get('links',[]):
        url=urlsplit(link.get('href',''))
        match=re.fullmatch(r'/v2/payments/captures/([A-Z0-9]{6,64})',url.path)
        if link.get('rel')=='up' and url.scheme=='https' and url.hostname in ('api.paypal.com','api-m.paypal.com','api.sandbox.paypal.com','api-m.sandbox.paypal.com') and match:capture_id=match[1]
    if not capture_id:raise ValueError('Refund capture reference missing')
    canonical=_api(cfg,'GET','/v2/payments/refunds/'+rid)
    if canonical.get('id')!=rid or canonical.get('status')!='COMPLETED':raise ValueError('Refund is not completed')
    amount=_cents(canonical['amount'])
    with auth.db() as c:
        r.init(c);init(c);c.execute('BEGIN IMMEDIATE')
        if c.execute('SELECT 1 FROM paypal_refunds WHERE id=?',(rid,)).fetchone():return {'received':True}
        capture=c.execute('SELECT * FROM paypal_captures WHERE id=?',(capture_id,)).fetchone()
        if not capture:raise ValueError('Unknown refund capture')
        order=c.execute('SELECT * FROM paypal_orders WHERE id=?',(capture['order_id'],)).fetchone()
        if order['environment']!=cfg['environment'] or order['client_fingerprint']!=hashlib.sha256(cfg['client_id'].encode()).hexdigest():raise ValueError('Refund merchant mismatch')
        prior=c.execute('SELECT coalesce(sum(amount_cents),0) FROM paypal_refunds WHERE capture_id=?',(capture_id,)).fetchone()[0]
        if amount<=0 or prior+amount>capture['amount_cents']:raise ValueError('Invalid refund amount')
        c.execute('INSERT INTO paypal_refunds VALUES(?,?,?,?)',(rid,order['id'],capture_id,amount))
        if order['kind']=='credits':c.execute('INSERT INTO resource_credits VALUES(?,?,?,?,?,?)',('paypal-refund:'+rid,order['user_id'],-amount*10000,None,'PayPal credit refund: '+order['id'],int(time.time())))
        c.execute('UPDATE paypal_orders SET refund_due_micro=max(0,refund_due_micro-?) WHERE id=?',(amount*10000,order['id']))
        c.execute('INSERT OR IGNORE INTO paypal_events VALUES(?,?)',(payload['id'],int(time.time())))
    return {'received':True}
