"""Subscription-only credit checkout. Only signed provider events credit wallets."""
import hashlib
import hmac
import json
import time
import uuid
from urllib.parse import urlsplit
import httpx
from . import auth,resource_accounts as r


def init(c):
    c.executescript('''CREATE TABLE IF NOT EXISTS credit_payment_config(id INTEGER PRIMARY KEY CHECK(id=1),secret_key TEXT NOT NULL DEFAULT '',webhook_secret TEXT NOT NULL DEFAULT '');
    INSERT OR IGNORE INTO credit_payment_config(id) VALUES(1);
    CREATE TABLE IF NOT EXISTS credit_purchase_orders(id TEXT PRIMARY KEY,user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,request_id TEXT NOT NULL,amount_cents INTEGER NOT NULL,credit_value_micro INTEGER NOT NULL,created_at INTEGER NOT NULL,session_id TEXT,checkout_url TEXT,status TEXT NOT NULL DEFAULT 'pending',paid_at INTEGER,payment_intent TEXT,refunded_cents INTEGER NOT NULL DEFAULT 0,UNIQUE(user_id,request_id));
    CREATE TABLE IF NOT EXISTS credit_payment_events(id TEXT PRIMARY KEY,received_at INTEGER NOT NULL);
    ''')


def settings(body=None):
    with auth.db() as c:
        r.init(c);init(c)
        if body is not None:
            if not isinstance(body,dict) or set(body)-{'secret_key','webhook_secret'}:raise ValueError('Invalid payment configuration')
            for key,value in body.items():
                if not isinstance(value,str) or len(value)>512 or any(ch.isspace() for ch in value):raise ValueError('Invalid payment key')
                if value and not value.startswith(('sk_test_','sk_live_') if key=='secret_key' else ('whsec_',)):raise ValueError('Invalid payment key prefix')
                if value:c.execute({'secret_key':'UPDATE credit_payment_config SET secret_key=? WHERE id=1','webhook_secret':'UPDATE credit_payment_config SET webhook_secret=? WHERE id=1'}[key],(auth._seal(value),))
        row=c.execute('SELECT * FROM credit_payment_config WHERE id=1').fetchone()
        return {'provider':'stripe','secret_key_set':bool(row['secret_key']),'webhook_secret_set':bool(row['webhook_secret']),'configured':bool(row['secret_key'] and row['webhook_secret'])}


def catalog(uid):
    s=r.state(uid);cfg=r.config()
    with auth.db() as c:
        init(c)
        orders=[dict(x) for x in c.execute('SELECT id,amount_cents,created_at,status,paid_at,refunded_cents FROM credit_purchase_orders WHERE user_id=? ORDER BY created_at DESC LIMIT 100',(uid,))]
    return {'eligible':s['credits_enabled'],'enabled':bool(cfg['credits_enabled']),'subscription':s['subscription'],'denominations_cents':json.loads(cfg['credit_denominations']),'credit_value_micro':s['credit_value_micro'],'credits_micro':s['credits_micro'],'provider':settings(),'orders':orders}


def _stripe(data,key,order):
    try:
        with httpx.Client(timeout=30,follow_redirects=False) as client:
            response=client.post('https://api.stripe.com/v1/checkout/sessions',data=data,headers={'Authorization':'Bearer '+key,'Idempotency-Key':'mta-credits-'+order})
    except httpx.HTTPError as exc:raise ValueError('Checkout unavailable; contact the server administrator') from exc
    if response.status_code!=200:raise ValueError('Checkout unavailable; contact the server administrator')
    return response.json()


def checkout(uid,amount,request_id):
    if type(amount) is not int or not isinstance(request_id,str) or not 8<=len(request_id)<=80:raise ValueError('Invalid purchase request')
    from .legal import snapshot
    base=snapshot()[0]['public_url'];url=urlsplit(base)
    if url.scheme!='https' or not url.hostname or url.username or url.password:raise ValueError('Configure the public HTTPS URL first')
    with auth.db() as c:
        r.init(c);init(c);c.execute('BEGIN IMMEDIATE');s=r._state(c,uid,0,int(time.time()))
        if not s['credits_enabled']:raise ValueError('Credits require an enabled credit service and an active subscription')
        cfg=c.execute('SELECT * FROM resource_config WHERE id=1').fetchone()
        if amount not in json.loads(cfg['credit_denominations']):raise ValueError('Credit denomination changed; refresh the page')
        keys=c.execute('SELECT * FROM credit_payment_config WHERE id=1').fetchone()
        if not keys['secret_key'] or not keys['webhook_secret']:raise ValueError('Credit checkout is not configured; contact the administrator')
        old=c.execute('SELECT * FROM credit_purchase_orders WHERE user_id=? AND request_id=?',(uid,request_id)).fetchone()
        if old:
            if old['amount_cents']!=amount:raise ValueError('Conflicting purchase retry')
            if old['status']=='paid':return {'status':'paid','order_id':old['id']}
            if old['checkout_url']:return {'checkout_url':old['checkout_url'],'order_id':old['id']}
            order=old['id']
        else:
            order=uuid.uuid4().hex;c.execute('INSERT INTO credit_purchase_orders(id,user_id,request_id,amount_cents,credit_value_micro,created_at) VALUES(?,?,?,?,?,?)',(order,uid,request_id,amount,s['credit_value_micro'],int(time.time())))
        key=auth._open(keys['secret_key'])
    data={'mode':'payment','client_reference_id':order,'metadata[mta_order]':order,'line_items[0][price_data][currency]':'eur','line_items[0][price_data][unit_amount]':str(amount),'line_items[0][price_data][product_data][name]':'MTA Audio Editor credits','line_items[0][quantity]':'1','success_url':base+'/account/credits?payment=received','cancel_url':base+'/account/credits?payment=cancelled'}
    session=_stripe(data,key,order);target=urlsplit(str(session.get('url','')))
    if target.scheme!='https' or target.hostname!='checkout.stripe.com' or not isinstance(session.get('id'),str):raise ValueError('Invalid checkout response')
    with auth.db() as c:
        c.execute('UPDATE credit_purchase_orders SET session_id=?,checkout_url=? WHERE id=? AND status=?',(session['id'],session['url'],order,'pending'))
    return {'checkout_url':session['url'],'order_id':order}


def event(raw,signature):
    if len(raw)>1024*1024:raise ValueError('Webhook too large')
    with auth.db() as c:
        r.init(c);init(c);key=auth._open(c.execute('SELECT webhook_secret FROM credit_payment_config WHERE id=1').fetchone()[0])
    parts=[p.split('=',1) for p in signature.split(',') if '=' in p];times=[v for k,v in parts if k=='t'];signatures=[v for k,v in parts if k=='v1']
    if not key or len(times)!=1:raise ValueError('Invalid payment signature')
    try:stamp=int(times[0])
    except ValueError as exc:raise ValueError('Invalid payment signature') from exc
    if abs(time.time()-stamp)>300:raise ValueError('Expired payment signature')
    expected=hmac.new(key.encode(),times[0].encode()+b'.'+raw,hashlib.sha256).hexdigest()
    if not any(hmac.compare_digest(expected,v) for v in signatures):raise ValueError('Invalid payment signature')
    payload=json.loads(raw)
    if not isinstance(payload,dict):raise ValueError('Invalid payment event')
    kind=payload.get('type');identifier=payload.get('id')
    if not isinstance(identifier,str) or len(identifier)>200:raise ValueError('Invalid payment event')
    if kind not in ('checkout.session.completed','checkout.session.async_payment_succeeded','charge.refunded'):return {'received':True}
    obj=payload['data']['object']
    with auth.db() as c:
        c.execute('BEGIN IMMEDIATE')
        if c.execute('SELECT 1 FROM credit_payment_events WHERE id=?',(identifier,)).fetchone():return {'received':True}
        if kind=='charge.refunded':
            order=c.execute('SELECT * FROM credit_purchase_orders WHERE payment_intent=? AND status=?',(obj.get('payment_intent'),'paid')).fetchone()
            if not order:return {'received':True}
            refunded=obj.get('amount_refunded')
            if type(refunded) is not int or not 0<=refunded<=order['amount_cents'] or obj.get('currency')!='eur':raise ValueError('Invalid refund')
            if refunded<order['refunded_cents']:return {'received':True}
            delta=(refunded-order['refunded_cents'])*10000
            if delta:c.execute('INSERT INTO resource_credits VALUES(?,?,?,?,?,?)',('refund:'+identifier,order['user_id'],-delta,None,'Stripe credit refund: '+order['id'],int(time.time())))
            c.execute('UPDATE credit_purchase_orders SET refunded_cents=? WHERE id=?',(refunded,order['id']))
        else:
            if obj.get('payment_status')!='paid':return {'received':True}
            oid=obj.get('metadata',{}).get('mta_order')
            order=c.execute('SELECT * FROM credit_purchase_orders WHERE id=?',(oid,)).fetchone()
            if not order:raise ValueError('Unknown credit purchase')
            if type(obj.get('amount_total')) is not int or obj.get('amount_total')!=order['amount_cents'] or obj.get('currency')!='eur' or obj.get('client_reference_id')!=order['id']:raise ValueError('Payment amount or identity mismatch')
            if order['session_id'] is not None and obj.get('id')!=order['session_id']:raise ValueError('Payment session mismatch')
            if order['status']!='paid':
                # A later policy change locks usage, but cannot discard money paid
                # for a checkout legitimately issued before that change.
                c.execute('INSERT INTO resource_credits VALUES(?,?,?,?,?,?)',('purchase:'+order['id'],order['user_id'],order['amount_cents']*10000,None,'Stripe credit purchase: '+order['id'],int(time.time())))
                c.execute("UPDATE credit_purchase_orders SET status='paid',paid_at=?,payment_intent=?,session_id=? WHERE id=?",(int(time.time()),obj.get('payment_intent'),obj['id'],order['id']))
        c.execute('INSERT INTO credit_payment_events VALUES(?,?)',(identifier,int(time.time())))
    return {'received':True}
