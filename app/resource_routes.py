"""Authenticated owner/admin resource controls, shared across native/web users."""
import sqlite3
from fastapi import APIRouter,Request,HTTPException
from . import auth,resource_accounts as resources,resource_entitlements as entitlements
router=APIRouter()


def call(fn):
    try:return fn()
    except (ValueError,TypeError,KeyError,OverflowError,sqlite3.IntegrityError) as exc:raise HTTPException(422,str(exc)) from exc


def view(uid):
    from . import storage
    from .account_limits import project_storage
    import time
    used=project_storage(uid,storage.list_projects(),storage.pdir)['used_bytes']
    resources.sample(uid,used)
    state=resources.state(uid,used);cfg=resources.config();now=time.time()
    week=next(p for p in cfg['plans'] if p['code']=='week')
    plans=[{**week,'code':'trial','price_micro':0},*cfg['plans']]
    start=min(now-1,(state['period'] or {}).get('start',max(0,now-30*86400)))
    return {**state,'history':resources.history(uid),'transactions':resources.transactions(uid),'plans':plans,'self_service':bool(cfg['self_service']),'storage_overusage':entitlements.storage_report(uid,start,now),'ordinary_tariffs':__import__('app.ai_billing',fromlist=['prices']).prices()}



@router.get('/api/account/subscription')
def personal(request:Request):return call(lambda:view(auth.require_user(request)['id']))


@router.patch('/api/account/subscription')
def overage(request:Request,body:dict):return call(lambda:resources.options(auth.require_user(request)['id'],body))


@router.post('/api/account/subscription/storage')
def storage(request:Request,body:dict):
    uid=auth.require_user(request)['id']
    if set(body)!={'gb','request_id','max_cost_micro'}:raise HTTPException(422,'Invalid storage request')
    return call(lambda:resources.unlock_storage(uid,body['gb'],body['request_id'],body['max_cost_micro']))


@router.get('/api/admin/subscriptions')
def config(request:Request):
    auth.require_admin(request);return resources.config()


@router.put('/api/admin/subscriptions')
def configure(request:Request,body:dict):
    auth.require_admin(request);return call(lambda:resources.configure(body))


@router.get('/api/admin/subscriptions/users/{uid}')
def user(request:Request,uid:int):
    auth.require_admin(request);return call(lambda:view(uid))


@router.put('/api/admin/subscriptions/users/{uid}')
def assign(request:Request,uid:int,body:dict):
    actor=auth.require_admin(request);return call(lambda:resources.assign(uid,body,actor['id']))


@router.post('/api/admin/subscriptions/users/{uid}/credits')
def credit(request:Request,uid:int,body:dict):
    actor=auth.require_admin(request)
    if set(body)=={'credits','credit_value_micro','reason','request_id'}:
        from .resource_access import grant_credits
        return call(lambda:grant_credits(uid,body['credits'],body['credit_value_micro'],body['reason'],actor['id'],body['request_id']))
    if set(body)!={'amount_micro','reason','request_id'}:raise HTTPException(422,'Invalid credit request')
    return call(lambda:resources.grant(uid,body['amount_micro'],body['reason'],actor['id'],body['request_id']))


@router.post('/api/account/subscription')
def subscribe(request:Request,body:dict):
    uid=auth.require_user(request)['id']
    if set(body)-{'plan','expected_price_micro','next_plan','next_price_micro'} or not {'plan','expected_price_micro'}<=set(body):raise HTTPException(422,'Invalid subscription request')
    return call(lambda:resources.subscribe(uid,body['plan'],body['expected_price_micro'],next_plan=body.get('next_plan'),next_price=body.get('next_price_micro')))


@router.post('/api/account/subscription/cancel')
def cancel(request:Request):
    uid=auth.require_user(request)['id']
    return call(lambda:resources.cancel_renewal(uid))


@router.patch('/api/admin/subscriptions/users/{uid}/policy')
def policy(request:Request,uid:int,body:dict):
    actor=auth.require_admin(request)
    return call(lambda:entitlements.set_policy(uid,body,actor['id']))


@router.put('/api/admin/subscriptions/users/{uid}/storage')
def admin_storage(request:Request,uid:int,body:dict):
    actor=auth.require_admin(request)
    if set(body)!={'quota_bytes','free','reason'}:raise HTTPException(422,'Invalid storage allocation')
    return call(lambda:entitlements.set_storage(uid,body['quota_bytes'],actor=actor['id'],free=body['free'],reason=body['reason']))


@router.put('/api/account/subscription/storage')
def capacity(request:Request,body:dict):
    uid=auth.require_user(request)['id']
    if set(body)!={'quota_bytes','request_id','max_rate_micro'}:raise HTTPException(422,'Invalid storage allocation')
    if not isinstance(body['request_id'],str) or not 8<=len(body['request_id'])<=80:raise HTTPException(422,'Invalid storage request ID')
    return call(lambda:entitlements.set_storage(uid,body['quota_bytes'],actor=uid,owner=True,key=body['request_id'],max_rate=body['max_rate_micro']))


@router.get('/api/account/subscription/storage-report')
def storage_report(request:Request,start:int,end:int):
    return call(lambda:entitlements.storage_report(auth.require_user(request)['id'],start,end))


@router.get('/api/admin/subscriptions/users/{uid}/storage-report')
def admin_storage_report(request:Request,uid:int,start:int,end:int):
    auth.require_admin(request)
    return call(lambda:entitlements.storage_report(uid,start,end))


@router.post('/api/account/subscription/renewal')
def renewal(request:Request,body:dict):
    uid=auth.require_user(request)['id']
    if set(body)!={'plan','expected_price_micro'}:raise HTTPException(422,'Invalid renewal request')
    return call(lambda:entitlements.next_plan(uid,body['plan'],body['expected_price_micro']))


@router.get('/api/account/access')
def access(request:Request):
    from .resource_access import status
    return call(lambda:status(auth.require_user(request)['id']))


@router.get('/api/admin/subscription-users')
def search_users(request:Request,q:str='',limit:int=20):
    auth.require_admin(request)
    if len(q)>160 or not 1<=limit<=100:raise HTTPException(422,'Invalid search')
    # instr uses literal substring matching; %, _ and SQL syntax are not wildcards.
    with auth.db() as c:
        rows=c.execute("SELECT id,username,email,display_name,role FROM users WHERE instr(lower(username||' '||email||' '||coalesce(display_name,'')),lower(?))>0 ORDER BY username COLLATE NOCASE,id LIMIT ?",(q,limit)).fetchall()
    return [dict(row) for row in rows]


@router.put('/api/admin/subscriptions/tariffs')
def tariffs(request:Request,body:dict):
    auth.require_admin(request)
    from .resource_access import DEFAULT_TARIFFS
    from .ai_billing import set_price
    if set(body)!=set(DEFAULT_TARIFFS):raise HTTPException(422,'CPU, GPU and storage tariffs required')
    # Validate all fields before changing any tariff; historical API owns overlap checks.
    values=call(lambda:{key:resources.number(value,integer=True) for key,value in body.items()})
    def save():
        with auth.db() as c:
            resources.init(c);c.execute('BEGIN IMMEDIATE')
            for key,value in values.items():set_price(key,value,_connection=c)
    call(save)
    return resources.config()


@router.get('/api/account/credits')
def credit_catalog(request:Request):
    from .credit_purchases import catalog
    return call(lambda:catalog(auth.require_user(request)['id']))


@router.post('/api/account/credits/checkout')
def credit_checkout(request:Request,body:dict):
    from .credit_purchases import checkout
    if set(body)!={'amount_cents','request_id'}:raise HTTPException(422,'Invalid purchase')
    return call(lambda:checkout(auth.require_user(request)['id'],body['amount_cents'],body['request_id']))


@router.get('/api/admin/credit-payments')
def payment_config(request:Request):
    auth.require_admin(request)
    from .credit_purchases import settings
    return settings()


@router.put('/api/admin/credit-payments')
def payment_save(request:Request,body:dict):
    auth.require_admin(request)
    from .credit_purchases import settings
    return call(lambda:settings(body))


@router.post('/api/billing/credits/stripe-webhook')
async def stripe_webhook(request:Request):
    from .credit_purchases import event
    raw=bytearray()
    async for chunk in request.stream():
        raw.extend(chunk)
        if len(raw)>1024*1024:raise HTTPException(413,'Payment event too large')
    try:return event(bytes(raw),request.headers.get('stripe-signature',''))
    except (ValueError,TypeError,KeyError):raise HTTPException(400,'Invalid payment event') from None


@router.patch('/api/admin/subscriptions/users/{uid}/limits')
def amend_limits(request:Request,uid:int,body:dict):
    actor=auth.require_admin(request)
    from .resource_contracts import amend
    return call(lambda:amend(uid,body,actor['id']))


@router.post('/api/admin/subscriptions/users/{uid}/terminate')
def terminate_contract(request:Request,uid:int,body:dict):
    actor=auth.require_admin(request)
    from .resource_contracts import terminate
    return call(lambda:terminate(uid,body,actor['id']))


@router.get('/api/admin/paypal')
def paypal_config(request:Request):
    auth.require_admin(request)
    from .paypal_payments import settings
    return settings()


@router.put('/api/admin/paypal')
def paypal_save(request:Request,body:dict):
    auth.require_admin(request)
    from .paypal_payments import settings
    return call(lambda:settings(body))


@router.post('/api/account/paypal/checkout')
def paypal_checkout(request:Request,body:dict):
    from .paypal_payments import checkout
    return call(lambda:checkout(auth.require_user(request)['id'],body))


@router.post('/api/account/paypal/{order_id}/capture')
def paypal_capture(request:Request,order_id:str):
    from .paypal_payments import capture
    return call(lambda:capture(auth.require_user(request)['id'],order_id))


@router.post('/api/billing/paypal/webhook')
async def paypal_webhook(request:Request):
    from .paypal_payments import webhook
    raw=bytearray()
    async for chunk in request.stream():
        raw.extend(chunk)
        if len(raw)>1024*1024:raise HTTPException(413,'Payment event too large')
    try:return webhook(bytes(raw),request.headers)
    except (ValueError,TypeError,KeyError,sqlite3.IntegrityError):raise HTTPException(400,'Invalid PayPal event') from None
