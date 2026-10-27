"""Authenticated owner/admin resource controls, shared across native/web users."""
import sqlite3
from fastapi import APIRouter,Request,HTTPException,Response
from . import auth,resource_accounts as resources,resource_entitlements as entitlements
from .regime_operation_fence import FenceBlocked
router=APIRouter()


def call(fn):
    try:return fn()
    except FenceBlocked as exc:raise HTTPException(409,str(exc)) from exc
    except (ValueError,TypeError,KeyError,OverflowError,sqlite3.IntegrityError) as exc:raise HTTPException(422,str(exc)) from exc


def view(uid):
    from . import storage
    from .account_limits import project_storage
    import time
    from .paypal_payments import settings as paypal_settings
    from .service_regime import commercial_allowed,current_regime
    used=project_storage(uid,storage.list_projects(),storage.pdir)['used_bytes']
    resources.sample(uid,used)
    state=resources.state(uid,used);cfg=resources.config();now=time.time()
    week=next(p for p in cfg['plans'] if p['code']=='week')
    plans=[{**week,'code':'trial','price_micro':0},*cfg['plans']]
    start=min(now-1,(state['period'] or {}).get('start',max(0,now-30*86400)))
    paypal=paypal_settings()
    with auth.db() as c:
        pending_periods=[row[0] for row in c.execute("SELECT DISTINCT period_start FROM paypal_orders WHERE user_id=? AND kind='subscription' AND status NOT IN ('paid','cancelled','canceled','failed','refunded')",(uid,))]
    return {**state,'service_regime':current_regime().value,'repayment_available':commercial_allowed() and paypal['configured'],'pending_subscription_periods':pending_periods,'history':resources.history(uid),'transactions':resources.transactions(uid),'plans':plans,'self_service':bool(cfg['self_service']),'storage_overusage':entitlements.storage_report(uid,start,now),'ordinary_tariffs':__import__('app.ai_billing',fromlist=['prices']).prices()}



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
    from .service_regime import require_commercial
    try:require_commercial()
    except ValueError as exc:raise HTTPException(403,str(exc)) from exc
    auth.require_admin(request);return call(lambda:resources.configure(body))


@router.get('/api/admin/subscriptions/users/{uid}')
def user(request:Request,uid:int):
    auth.require_admin(request);return call(lambda:view(uid))


@router.put('/api/admin/subscriptions/users/{uid}')
def assign(request:Request,uid:int,body:dict):
    from .service_regime import require_commercial
    try:require_commercial()
    except ValueError as exc:raise HTTPException(403,str(exc)) from exc
    actor=auth.require_admin(request);return call(lambda:resources.assign(uid,body,actor['id']))


@router.post('/api/admin/subscriptions/users/{uid}/credits')
def credit(request:Request,uid:int,body:dict):
    from .service_regime import require_commercial
    try:require_commercial()
    except ValueError as exc:raise HTTPException(403,str(exc)) from exc
    actor=auth.require_admin(request)
    if set(body)=={'credits','credit_value_micro','reason','request_id'}:
        from .resource_access import grant_credits
        return call(lambda:grant_credits(uid,body['credits'],body['credit_value_micro'],body['reason'],actor['id'],body['request_id']))
    if set(body)!={'amount_micro','reason','request_id'}:raise HTTPException(422,'Invalid credit request')
    return call(lambda:resources.grant(uid,body['amount_micro'],body['reason'],actor['id'],body['request_id']))


@router.post('/api/account/subscription')
def subscribe(request:Request,body:dict):
    from .service_regime import require_commercial
    try:require_commercial()
    except ValueError as exc:raise HTTPException(403,str(exc)) from exc
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
    from .service_regime import require_commercial
    try:require_commercial()
    except ValueError as exc:raise HTTPException(403,str(exc)) from exc
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
    from .service_regime import require_commercial
    try:require_commercial()
    except ValueError as exc:raise HTTPException(403,str(exc)) from exc
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
    from .service_regime import require_commercial
    try:require_commercial()
    except ValueError as exc:raise HTTPException(403,str(exc)) from exc
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
    except (ValueError,TypeError,KeyError,FenceBlocked,sqlite3.IntegrityError):raise HTTPException(400,'Invalid payment event') from None


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
    from .service_regime import require_commercial
    try:require_commercial()
    except ValueError as exc:raise HTTPException(403,str(exc)) from exc
    from .paypal_payments import checkout
    return call(lambda:checkout(auth.require_user(request)['id'],body))


@router.post('/api/account/paypal/{order_id}/capture')
def paypal_capture(request:Request,order_id:str):
    from .service_regime import require_commercial
    try:require_commercial()
    except ValueError as exc:raise HTTPException(403,str(exc)) from exc
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
    except (ValueError,TypeError,KeyError,FenceBlocked,sqlite3.IntegrityError):raise HTTPException(400,'Invalid PayPal event') from None


@router.get('/api/service-regime')
def public_service_regime():
    from .service_regime import current_regime
    return {'regime':current_regime().value}


@router.get('/api/admin/service-regime/cutovers/lifecycle')
def cutover_lifecycle(request:Request,offset:int=0,limit:int=25):
    actor=auth.require_admin(request)
    from .regime_transition_status import overview
    from fastapi.responses import JSONResponse
    try:
        return JSONResponse(call(lambda:overview(actor=actor['id'],offset=offset,limit=limit)),
                            headers={'Cache-Control':'no-store','Pragma':'no-cache'})
    except sqlite3.DatabaseError:
        raise HTTPException(409,'Transition lifecycle unavailable') from None


@router.post('/api/admin/service-regime/cutovers/reservations/{identifier}/abort')
def cutover_abort_reservation(identifier:str,request:Request,body:dict):
    actor=auth.require_admin(request)
    if set(body)!={'expected_revision','confirm'}:raise HTTPException(422,'Exact reservation confirmation required')
    from .regime_transition_status import abort_reservation
    return call(lambda:abort_reservation(actor=actor['id'],identifier=identifier,**body))


@router.get('/api/admin/service-regime/cutovers/preview')
def admin_cutover_preview(request: Request, target: str):
    actor = auth.require_admin(request)
    from . import regime_admin_cutover as cutover
    from .regime_operation_fence import FenceBlocked
    try:
        return cutover.preview(target=target, actor=int(actor['id']))
    except (ValueError, TypeError) as exc:
        raise HTTPException(422, 'Invalid transition target or financial basis') from exc
    except (FenceBlocked, sqlite3.DatabaseError) as exc:
        raise HTTPException(409, str(exc) if isinstance(exc, FenceBlocked) else 'Cutover audit unavailable') from exc
    except OSError as exc:
        raise HTTPException(409, 'Local-authority cutover prerequisites unavailable') from exc


@router.get('/api/admin/service-regime/cutovers')
def admin_cutover_history(request: Request, limit: int = 25, offset: int = 0):
    actor = auth.require_admin(request)
    from . import regime_admin_cutover as cutover
    from .regime_operation_fence import FenceBlocked
    try:
        return cutover.history(actor=int(actor['id']), limit=limit, offset=offset)
    except ValueError as exc:
        raise HTTPException(422, 'Invalid audit page') from exc
    except (FenceBlocked, sqlite3.DatabaseError) as exc:
        raise HTTPException(409, 'Administrative audit unavailable') from exc


@router.post('/api/admin/service-regime/cutovers')
def admin_execute_cutover(request: Request, body: dict):
    actor = auth.require_admin(request)
    if set(body) != {'request_id', 'target', 'expected_revision', 'preview_sha256', 'confirm'}:
        raise HTTPException(422, 'Exact transition confirmation required')
    from . import regime_admin_cutover as cutover
    from .regime_operation_fence import FenceBlocked
    try:
        return cutover.execute(identifier=body['request_id'], target=body['target'],
            expected_revision=body['expected_revision'], preview_sha256=body['preview_sha256'],
            confirm=body['confirm'], actor=int(actor['id']))
    except (ValueError, TypeError) as exc:
        raise HTTPException(422, 'Invalid transition confirmation') from exc
    except (FenceBlocked, sqlite3.DatabaseError) as exc:
        raise HTTPException(409, str(exc) if isinstance(exc, FenceBlocked) else 'Cutover blocked; inspect audit before retry') from exc
    except OSError as exc:
        raise HTTPException(503, 'Cutover interrupted; inspect audit and use forward recovery') from exc


@router.get('/api/admin/service-regime/cutovers/{identifier}')
def admin_cutover_status(identifier: str, request: Request):
    actor = auth.require_admin(request)
    from . import regime_admin_cutover as cutover
    result = cutover.status(identifier=identifier, actor=int(actor['id']))
    if result is None:
        raise HTTPException(404, 'No committed transition with this identity')
    return result


@router.post('/api/admin/service-regime/cutovers/{identifier}/recover')
def admin_recover_cutover(identifier: str, request: Request, body: dict):
    actor = auth.require_admin(request)
    if set(body) != {'expected_revision', 'confirm'}:
        raise HTTPException(422, 'Exact recovery confirmation required')
    from . import regime_admin_cutover as cutover
    from .regime_operation_fence import FenceBlocked
    try:
        return cutover.recover(identifier=identifier, expected_revision=body['expected_revision'],
                               confirm=body['confirm'], actor=int(actor['id']))
    except (ValueError, TypeError) as exc:
        raise HTTPException(422, 'Invalid recovery confirmation') from exc
    except (FenceBlocked, sqlite3.DatabaseError) as exc:
        raise HTTPException(409, str(exc) if isinstance(exc, FenceBlocked) else 'Forward recovery blocked') from exc
    except OSError as exc:
        raise HTTPException(503, 'Recovery interrupted; original barrier remains held') from exc

@router.get('/api/admin/service-regime')
def admin_service_regime(request:Request):
    auth.require_admin(request)
    from .service_regime import read_regime
    state=read_regime(auth.data_root() / 'service-regime.json')
    return {'regime':state.regime.value,'revision':state.revision,'transition_enabled':False,
            'note':'Regime transitions require reconciled historic billing and are disabled until migration is complete'}


@router.get('/api/admin/service-regime/transition-audit')
def admin_service_regime_transition_audit(request: Request, target: str):
    auth.require_admin(request)
    from .service_regime import Regime, RegimeError, audit_transition_database
    try:
        destination = Regime(target)
    except ValueError as exc:
        raise HTTPException(422, 'Unknown service regime') from exc
    with auth.db() as conn:
        try:
            return audit_transition_database(conn, destination,
                                             path=auth.data_root() / 'service-regime.json')
        except (RegimeError, sqlite3.DatabaseError) as exc:
            raise HTTPException(409, 'Service-regime audit unavailable') from exc


@router.get('/api/admin/service-regime/reconciliation-report')
def admin_regime_reconciliation_report(request: Request, target: str):
    """Read-only reconciliation inventory; does not authorize a regime change."""
    auth.require_admin(request)
    from .service_regime import Regime, current_regime
    from .regime_reconciliation import readiness_report
    try:
        destination = Regime(target)
    except ValueError as exc:
        raise HTTPException(422, 'Unknown service regime') from exc
    with auth.db() as connection:
        return readiness_report(connection, current=current_regime().value, target=destination.value)


@router.get('/api/admin/service-regime/combined-readiness')
def admin_regime_combined_readiness(request: Request, target: str):
    """Read-only combined financial/fence readiness, always fail closed."""
    auth.require_admin(request)
    from .service_regime import Regime, read_regime
    from .regime_reconciliation import combined_readiness
    try:
        destination = Regime(target)
    except ValueError as exc:
        raise HTTPException(422, 'Unknown service regime') from exc
    try:
        with auth.db() as connection:
            mirror=read_regime(auth.data_root() / 'service-regime.json')
            result=combined_readiness(connection,current=mirror.regime.value,target=destination.value)
            if result['fence'] and result['fence']['revision']!=mirror.revision:
                result['unresolved']=sorted(set(result['unresolved']+['operation_fence_revision_drift']))
            result['configuration_revision']=mirror.revision
            return result
    except sqlite3.DatabaseError as exc:
        raise HTTPException(409, 'Reconciliation unavailable') from exc


@router.get('/api/admin/service-regime/worker-processes')
def admin_worker_processes(request: Request, limit: int=50, offset: int=0):
    auth.require_admin(request)
    from .worker_cgroup_recovery import report
    with auth.db() as c:return call(lambda:report(c,limit=limit,offset=offset))


def _worker_recovery_call(fn):
    try:return call(fn)
    except (OSError,sqlite3.DatabaseError,RuntimeError) as exc:
        raise HTTPException(409,'Original worker evidence unavailable; resolution remains blocked') from exc


@router.get('/api/admin/service-regime/worker-losses/{job_id}/preview')
def worker_loss_preview(request: Request, job_id: str):
    actor=auth.require_admin(request)
    from .worker_loss_resolution import preview
    with auth.db() as c:return _worker_recovery_call(lambda:preview(c,job_id,actor['id']))


@router.post('/api/admin/service-regime/worker-losses/{job_id}/resolve')
def worker_loss_resolve(request: Request, job_id: str, body: dict):
    actor=auth.require_admin(request)
    from .worker_loss_resolution import resolve
    return _worker_recovery_call(lambda:resolve(job_id,actor['id'],body))


@router.get('/api/account/worker-losses')
def own_worker_losses(request: Request):
    actor=auth.require_user(request)
    from .worker_loss_resolution import history
    with auth.db() as c:return _worker_recovery_call(lambda:{'losses':history(c,actor['id'])})


@router.post('/api/admin/service-regime/worker-losses/{job_id}/recover-frozen')
def recover_frozen_worker_result(request: Request, job_id: str, body: dict):
    actor=auth.require_admin(request)
    if body!={'confirm_recover':True} or body.get('confirm_recover') is not True:
        raise HTTPException(422,'Explicit frozen-result recovery confirmation required')
    from .worker_loss_resolution import recover_frozen
    from .main import _publish_durable_generated_audio
    with auth.db() as c:
        owner=c.execute('SELECT user_id FROM ai_compute_jobs WHERE id=?',(job_id,)).fetchone()
    if owner is None:raise HTTPException(422,'Unknown original job')
    publish=lambda jid,pid,audio,metadata:_publish_durable_generated_audio(jid,pid,audio,metadata,expected_owner=owner[0])
    return _worker_recovery_call(lambda:recover_frozen(job_id,actor['id'],publish))


@router.get('/api/admin/service-regime/worker-losses')
def admin_worker_losses(request: Request):
    auth.require_admin(request)
    from .worker_loss_resolution import history
    with auth.db() as c:return _worker_recovery_call(lambda:{'losses':history(c)})


@router.post('/api/admin/service-regime/worker-processes/{scope_id}/quiesce')
def admin_quiesce_worker(request: Request, scope_id: str, body: dict):
    actor=auth.require_admin(request)
    if set(body)!={'request_id','confirm_stop'} or body['confirm_stop'] is not True:
        raise HTTPException(422,'Explicit worker stop confirmation required')
    from .worker_cgroup_recovery import recover
    try:return call(lambda:recover(scope_id,actor['id'],body['request_id']))
    except (OSError,sqlite3.DatabaseError) as exc:
        raise HTTPException(409,'Kernel quiescence unavailable; economic claim retained') from exc


@router.get('/api/admin/service-regime/payment-outbox-review')
def admin_regime_payment_outbox_review(request: Request, limit: int = 100, offset: int = 0):
    """Admin-only, read-only queue for unresolved external checkout outcomes."""
    auth.require_admin(request)
    from .regime_outbox_review import review
    from .regime_operation_fence import FenceBlocked
    try:
        with auth.db() as connection:
            return review(connection, limit=limit, offset=offset)
    except ValueError as exc:
        raise HTTPException(422, 'Invalid outbox pagination') from exc
    except (FenceBlocked, sqlite3.DatabaseError) as exc:
        raise HTTPException(409, 'Payment outbox review unavailable') from exc


@router.post('/api/admin/service-regime/close-negative-checkout')
def admin_close_negative_checkout(request: Request, body: dict):
    """Close only an already provider-verified non-created financial checkout."""
    auth.require_admin(request)
    if not isinstance(body, dict) or set(body) != {'provider', 'order_id'}:
        raise HTTPException(422, 'Provider and local order ID required')
    from .regime_admin_closure import close_negative_checkout
    from .regime_operation_fence import FenceBlocked
    try:
        with auth.db() as connection:
            return close_negative_checkout(connection, provider=body['provider'], order_id=body['order_id'])
    except (FenceBlocked, sqlite3.DatabaseError) as exc:
        raise HTTPException(409, 'Checkout cannot be reconciled safely') from exc
    except (ValueError, TypeError) as exc:
        raise HTTPException(422, 'Invalid checkout identity') from exc


@router.get('/api/admin/service-regime/transition-reservations')
def admin_regime_transition_reservations(request: Request):
    """Inspect stuck/pending reservations before an operator recovery decision."""
    auth.require_admin(request)
    from .regime_transition_journal import inspect_reservations
    from .regime_operation_fence import FenceBlocked
    try:
        with auth.db() as connection:
            return inspect_reservations(connection)
    except (FenceBlocked, sqlite3.DatabaseError) as exc:
        raise HTTPException(409, 'Transition reservation inspection unavailable') from exc


@router.post('/api/admin/service-regime/abort-transition-reservation')
def admin_abort_regime_transition_reservation(request: Request, body: dict):
    """Recover a pending reservation; never changes the effective regime."""
    auth.require_admin(request)
    if not isinstance(body, dict) or set(body) != {'transition_id', 'expected_revision'}:
        raise HTTPException(422, 'Transition identity and expected revision required')
    from .regime_transition_journal import abort_verified
    from .regime_operation_fence import FenceBlocked
    try:
        with auth.db() as connection:
            connection.execute('BEGIN IMMEDIATE')
            return abort_verified(connection, transition_id=body['transition_id'],
                                  expected_revision=body['expected_revision'])
    except (FenceBlocked, sqlite3.DatabaseError) as exc:
        raise HTTPException(409, 'Transition reservation cannot be safely cancelled') from exc
    except (ValueError, TypeError) as exc:
        raise HTTPException(422, 'Invalid transition identity or revision') from exc


@router.get('/api/admin/service-regime/transition-plan')
def admin_regime_transition_plan(request: Request, target: str):
    """Read-only, integrity-hashed transition snapshot; never switches mode."""
    auth.require_admin(request)
    from .regime_transition_plan import build_plan
    try:
        with auth.db() as connection:
            return build_plan(connection, target=target,
                              config_path=auth.data_root() / 'service-regime.json')
    except (ValueError, sqlite3.DatabaseError) as exc:
        raise HTTPException(409, 'Transition plan unavailable') from exc


@router.get('/api/service-regime/terms')
def public_regime_terms(lang: str = 'it', response: Response = None):
    from .service_regime import current_regime, Regime
    """Read-only, bilingual terms for the active service regime."""
    import hashlib
    from pathlib import Path
    if lang not in ('it', 'en'):
        raise HTTPException(422, 'Unsupported terms language')
    if response is not None:
        response.headers['Cache-Control'] = 'no-store'
        response.headers['X-Content-Type-Options'] = 'nosniff'
    mode = current_regime()
    label = 'COMMERCIAL' if mode == Regime.COMMERCIAL else 'NON_COMMERCIAL'
    filename = f'SHARED_INFRASTRUCTURE_{label}_{lang.upper()}.md'
    path = Path(__file__).resolve().parents[1] / 'docs' / 'legal' / filename
    body = path.read_text(encoding='utf-8')
    return {'regime': mode.value, 'language': lang, 'version': 'r210.1',
            'effective_date': None, 'sha256': hashlib.sha256(body.encode('utf-8')).hexdigest(),
            'text': body, 'legal_review_required': True}


@router.get('/service-terms/{lang}')
def service_terms_document(lang: str):
    """Display active regime draft terms without exposing administrator data."""
    from fastapi.responses import HTMLResponse
    from html import escape
    if lang not in ('it', 'en'):
        raise HTTPException(404, 'Unsupported terms language')
    item = public_regime_terms(lang)
    title = 'Regolamento del servizio' if lang == 'it' else 'Service Terms'
    warning = ('Bozza da verificare legalmente' if lang == 'it' else 'Draft subject to legal review')
    page = (f'<!doctype html><html lang="{lang}"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>{escape(title)}</title></head><body><main style="max-width:75ch;margin:2rem auto;padding:1rem;white-space:pre-wrap;font:1rem/1.55 system-ui">'
            f'<h1>{escape(title)}</h1><p>{escape(item["regime"])} — {escape(warning)}</p>'
            f'<article>{escape(item["text"])}</article></main></body></html>')
    return HTMLResponse(page, headers={'Cache-Control':'no-store','X-Content-Type-Options':'nosniff'})


@router.post('/api/admin/service-regime/noncommercial-statements')
def create_noncommercial_statement(request: Request, body: dict):
    """Freeze measured usage allocation without creating a payment obligation."""
    auth.require_admin(request)
    from .service_regime import current_regime, Regime
    from .noncommercial_statements import create_statement
    if current_regime() != Regime.NON_COMMERCIAL:
        raise HTTPException(409, 'Non-commercial statements require NON_COMMERCIAL mode')
    if not isinstance(body, dict) or set(body) - {'start', 'end', 'documented_cost_cents', 'recovered_cents','operator_cost_exclusion_confirmed'} or not {'start', 'end', 'documented_cost_cents'} <= set(body):
        raise HTTPException(422, 'Invalid statement request')
    if any(type(value) is not (bool if key=='operator_cost_exclusion_confirmed' else int) for key,value in body.items()):
        raise HTTPException(422, 'Invalid statement amounts or period')
    try:
        with auth.db() as connection:
            return create_statement(connection, **body)
    except (ValueError, sqlite3.DatabaseError) as exc:
        raise HTTPException(409, 'Period cannot be safely closed') from exc


@router.get('/api/admin/service-regime/noncommercial-statements')
def get_noncommercial_statements(request: Request):
    auth.require_admin(request)
    from .noncommercial_statements import list_statements
    try:
        with auth.db() as connection:
            return {'statements': list_statements(connection)}
    except (ValueError, sqlite3.DatabaseError) as exc:
        raise HTTPException(409, 'Statements cannot be verified') from exc


@router.get('/api/service-regime/my-noncommercial-statements')
def my_noncommercial_statements(request: Request):
    """Authenticated account-only cost statements (not payment receipts)."""
    user = auth.require_user(request)
    from .noncommercial_statements import user_statements
    try:
        with auth.db() as connection:
            return {'statements': user_statements(connection, str(user['id']))}
    except (ValueError, sqlite3.DatabaseError) as exc:
        raise HTTPException(409, 'Personal statements unavailable or inconsistent') from exc


@router.get('/api/service-regime/my-noncommercial-statements/export-csv')
def my_noncommercial_statement_csv(request: Request, start: int, end: int, lang: str='en'):
    """Verified single-user CSV without exposing other accounts."""
    user = auth.require_user(request)
    from .noncommercial_statements import user_statement_csv
    try:
        with auth.db() as connection:
            return user_statement_csv(connection, str(user['id']), start=start, end=end,language=lang)
    except (ValueError, sqlite3.DatabaseError) as exc:
        raise HTTPException(409, 'Personal statement unavailable or inconsistent') from exc


@router.get('/api/admin/service-regime/noncommercial-statements/export')
def export_noncommercial_statement(request: Request, start: int, end: int):
    """Read-only, integrity-checked accounting export (not a fiscal invoice)."""
    auth.require_admin(request)
    from .noncommercial_statements import export_statement
    try:
        with auth.db() as connection:
            return export_statement(connection, start=start, end=end)
    except (ValueError, sqlite3.DatabaseError) as exc:
        raise HTTPException(409, 'Statement unavailable or integrity invalid') from exc


@router.get('/api/admin/service-regime/noncommercial-statements/export-csv')
def export_noncommercial_statement_csv(request: Request, start: int, end: int, lang: str='en'):
    """Verified CSV; never a fiscal invoice or a payment instruction."""
    auth.require_admin(request)
    from .noncommercial_statements import export_statement_csv
    try:
        with auth.db() as connection:
            return export_statement_csv(connection, start=start, end=end,language=lang)
    except (ValueError, sqlite3.DatabaseError) as exc:
        raise HTTPException(409, 'Statement unavailable or integrity invalid') from exc


@router.get('/api/admin/service-regime/operation-fence')
def regime_operation_fence_status(request: Request):
    """Diagnostic visibility without falsely enabling financial regime switching."""
    auth.require_admin(request)
    from .regime_operation_fence import inspect
    try:
        with auth.db() as connection:
            # Do not initialize here: this endpoint is read-only.
            return inspect(connection)
    except sqlite3.DatabaseError as exc:
        raise HTTPException(409, 'Fence unavailable') from exc


@router.post('/api/admin/service-regime/noncommercial-preview')
def noncommercial_period_preview(request: Request, body: dict):
    """Read-only admin cost allocation, never charges or changes accounting."""
    auth.require_admin(request)
    from .service_regime import current_regime, Regime, RegimeError
    from .noncommercial_allocation import preview_from_metered_jobs
    if current_regime() != Regime.NON_COMMERCIAL:
        raise HTTPException(409, 'Non-commercial contribution preview requires NON_COMMERCIAL mode')
    if not isinstance(body, dict) or set(body) - {'start', 'end', 'documented_cost_cents', 'recovered_cents','operator_cost_exclusion_confirmed'} or not {'start', 'end', 'documented_cost_cents'} <= set(body):
        raise HTTPException(422, 'Invalid cost allocation request')
    try:
        with auth.db() as connection:
            return preview_from_metered_jobs(connection, **body)
    except (ValueError, RegimeError, sqlite3.DatabaseError) as exc:
        raise HTTPException(422, 'Cannot produce verified contribution preview') from exc


@router.get('/api/admin/service-regime/payment-ledger')
def admin_payment_ledger(request:Request,limit:int=50,offset:int=0):
    auth.require_admin(request)
    from .payment_reconciliation import report
    if not 1<=limit<=200 or offset<0:raise HTTPException(422,'Invalid report pagination')
    with auth.db() as c:
        try:return report(c,limit=limit,offset=offset)
        except (sqlite3.DatabaseError,ValueError,FenceBlocked) as exc:raise HTTPException(409,'Payment ledger cannot be verified') from exc


@router.post('/api/admin/service-regime/reconcile-payment')
def admin_reconcile_payment(request:Request,body:dict):
    auth.require_admin(request)
    if set(body)!={'provider','order_id'}:raise HTTPException(422,'Provider and local order ID required')
    from .payment_reconcile_service import reconcile_checkout
    return call(lambda:reconcile_checkout(body['provider'],body['order_id']))


@router.post('/api/admin/service-regime/recover-checkout-reference')
def admin_recover_checkout_reference(request:Request,body:dict):
    auth.require_admin(request)
    if set(body)!={'provider','order_id','provider_reference'}:raise HTTPException(422,'Provider, local order and remote reference required')
    from .checkout_reference_recovery import recover
    return call(lambda:recover(body['provider'],body['order_id'],body['provider_reference']))


@router.get('/api/admin/payment-refunds')
def admin_payment_refunds(request:Request,limit:int=50,offset:int=0):
    auth.require_admin(request)
    from .operator_refunds import overview
    return call(lambda:overview(limit=limit,offset=offset))


@router.get('/api/account/payment-refunds')
def owner_payment_refunds(request:Request,limit:int=50,offset:int=0):
    uid=auth.require_user(request)['id']
    from .operator_refunds import overview
    return call(lambda:overview(owner=uid,limit=limit,offset=offset))


@router.post('/api/admin/payment-refunds')
def prepare_payment_refund(request:Request,body:dict):
    actor=auth.require_admin(request)['id']
    from .operator_refunds import prepare
    return call(lambda:prepare(actor,body))


@router.post('/api/admin/payment-refunds/{refund_id}/{action}')
def act_on_payment_refund(request:Request,refund_id:str,action:str,body:dict):
    actor=auth.require_admin(request)['id']
    from . import operator_refunds as refunds
    if action not in ('execute','verify','cancel'):raise HTTPException(404,'Unknown refund action')
    if (set(body) not in ({'expected_revision'},{'expected_revision','provider_reference'})
        or ('provider_reference' in body and action!='verify')):raise HTTPException(422,'Exact refund revision required')
    if action=='verify':return call(lambda:refunds.verify(actor,refund_id,body['expected_revision'],body.get('provider_reference')))
    return call(lambda:getattr(refunds,action)(actor,refund_id,body['expected_revision']))


@router.get('/api/account/noncommercial-contributions')
def nc_owner_contributions(request:Request):
    from .noncommercial_contributions import overview
    uid=auth.require_user(request)['id']
    with auth.db() as c:return call(lambda:overview(c,uid))


@router.post('/api/account/noncommercial-contributions')
def nc_create_contribution(request:Request,body:dict):
    from .noncommercial_contributions import create
    uid=auth.require_user(request)['id']
    return call(lambda:create(uid,body))


@router.get('/api/account/noncommercial-contributions/export-csv')
def nc_owner_contribution_export(request:Request,lang:str='en'):
    from .noncommercial_contributions import export_csv
    uid=auth.require_user(request)['id']
    with auth.db() as c:return call(lambda:export_csv(c,uid,lang))


@router.post('/api/account/noncommercial-contributions/{contribution_id}/events')
def nc_owner_contribution_event(request:Request,contribution_id:str,body:dict):
    from .noncommercial_contributions import event
    uid=auth.require_user(request)['id']
    return call(lambda:event(uid,contribution_id,body))


@router.get('/api/admin/noncommercial-contributions')
def nc_admin_contributions(request:Request):
    from .noncommercial_contributions import overview
    auth.require_admin(request)
    with auth.db() as c:return call(lambda:overview(c))


@router.put('/api/admin/noncommercial-contributions/settings')
def nc_admin_contribution_settings(request:Request,body:dict):
    from .noncommercial_contributions import configure
    actor=auth.require_admin(request)['id']
    return call(lambda:configure(actor,body))


@router.post('/api/admin/noncommercial-contributions/{contribution_id}/events')
def nc_admin_contribution_event(request:Request,contribution_id:str,body:dict):
    from .noncommercial_contributions import event
    actor=auth.require_admin(request)['id']
    return call(lambda:event(actor,contribution_id,body,admin=True))


@router.get('/api/account/payments')
def owner_payment_history(request:Request,offset:int=0,limit:int=20):
    from .owner_payments import history
    uid=auth.require_user(request)['id']
    return call(lambda:history(uid,offset,limit))


@router.post('/api/account/payments/{provider}/{order_id}/verify')
def owner_payment_verify(request:Request,provider:str,order_id:str,body:dict):
    from .owner_payments import verify
    from .regime_provider_probe import ProviderProbeError
    import httpx
    uid=auth.require_user(request)['id']
    if body!={'confirm':True} or type(body.get('confirm')) is not bool:
        raise HTTPException(422,'Explicit confirmation required')
    try:return verify(uid,provider,order_id)
    except (ValueError,TypeError,KeyError,OverflowError,FenceBlocked,ProviderProbeError,httpx.HTTPError):
        raise HTTPException(409,'Payment could not be verified; refresh history or contact the administrator') from None


@router.get('/api/admin/paypal/merchant-history')
def merchant_history_list(request:Request,offset:int=0,limit:int=10):
    actor=auth.require_admin(request)
    from .paypal_merchant_history import snapshots
    return _merchant_history_response(lambda:snapshots(actor['id'],offset=offset,limit=limit))


@router.post('/api/admin/paypal/merchant-history')
def merchant_history_acquire(request:Request,body:dict):
    actor=auth.require_admin(request)
    if set(body)!={'start_date','end_date','confirm'}:
        raise HTTPException(422,'Exact reporting range and confirmation required')
    from .paypal_merchant_history import acquire
    return _merchant_history_response(lambda:acquire(actor['id'],**body))


@router.get('/api/admin/paypal/merchant-history/{snapshot_id}')
def merchant_history_detail(snapshot_id:str,request:Request,offset:int=0,limit:int=50):
    actor=auth.require_admin(request)
    from .paypal_merchant_history import details
    return _merchant_history_response(lambda:details(actor['id'],snapshot_id,offset=offset,limit=limit))


def _merchant_history_response(fn):
    from fastapi.responses import JSONResponse
    try:
        return JSONResponse(call(fn),headers={'Cache-Control':'no-store','Pragma':'no-cache'})
    except PermissionError as exc:
        raise HTTPException(403,'Active administrator required') from exc
    except sqlite3.DatabaseError as exc:
        raise HTTPException(409,'Merchant history unavailable') from exc


@router.get('/api/admin/service-regime/subscription-evidence')
def subscription_evidence(request:Request,offset:int=0,limit:int=50):
    auth.require_admin(request)
    from fastapi.responses import JSONResponse
    from .subscription_basis_audit import review
    if not 1<=limit<=200 or offset<0:
        raise HTTPException(422,'Invalid subscription evidence pagination')
    with auth.db() as connection:
        try:
            return JSONResponse(review(connection,offset=offset,limit=limit),
                                headers={'Cache-Control':'no-store','Pragma':'no-cache'})
        except sqlite3.DatabaseError as exc:
            raise HTTPException(409,'Original subscription evidence unavailable') from exc
