"""Private operator and narrowly scoped pull-worker control routes."""
import os
import re

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, Response

from . import auth, ai_pull_coordinator as central
from .regime_operation_fence import FenceBlocked

router = APIRouter()
NO_STORE = {'Cache-Control': 'no-store', 'Pragma': 'no-cache'}


def _server():
    if os.getenv('MTA_NATIVE_SINGLE_USER', '').lower() in ('true', '1', 'yes', 'on'):
        raise HTTPException(404, 'Server worker control is unavailable in native mode')


def _admin(request, *, write=False):
    _server()
    user = auth.session_user(request)
    if not user:
        raise HTTPException(401, 'Authentication required')
    if user['role'] != 'admin' or not user['active']:
        raise HTTPException(403, 'Active administrator required')
    if write and request.headers.get('x-mta-request') != '1':
        raise HTTPException(403, 'Request integrity marker required')
    return user


def worker_credential(request):
    value = request.headers.get('authorization', '')
    return value[7:] if value.startswith('Bearer ') else ''


def authenticated_worker_request(request):
    path = request.url.path
    if request.method != 'POST' or not (path == '/api/pull-worker/claim' or
            re.fullmatch(r'/api/pull-worker/[a-f0-9]{32}/(heartbeat|complete)', path)):
        return False
    return central.authenticate(worker_credential(request)) is not None


async def _body(request, fields, *, limit=24 * 1024 * 1024):
    raw = bytearray()
    async for part in request.stream():
        if len(raw) + len(part) > limit:
            raise HTTPException(413, 'Worker control payload exceeds limit')
        raw.extend(part)
    try:
        value = central.decode(bytes(raw))
        if not isinstance(value, dict) or set(value) != set(fields):
            raise ValueError('Invalid fields')
        return value
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise HTTPException(400, 'Invalid worker control JSON') from exc


@router.get('/api/admin/pull-workers')
def list_workers(request: Request):
    _admin(request)
    nodes = central.nodes()
    with auth.db() as c:
        state = central.inspect_state(c)
    return JSONResponse({'nodes': nodes, 'authority': state, 'transition_enabled': False}, headers=NO_STORE)


@router.post('/api/admin/pull-workers/drain')
async def admission_barrier(request: Request):
    admin = _admin(request, write=True)
    body = await _body(request, ('accepting','expected_generation','confirm'), limit=1024)
    if body.pop('confirm') is not True:
        raise HTTPException(400, 'Explicit admission control confirmation required')
    try:
        return JSONResponse(central.drain(**body, actor_id=admin['id']), headers=NO_STORE)
    except FenceBlocked as exc:
        raise HTTPException(409, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post('/api/admin/pull-workers')
async def register_worker(request: Request):
    admin = _admin(request, write=True)
    body = await _body(request, ('name', 'kinds'), limit=16384)
    try:
        return JSONResponse(central.register(**body, actor_id=admin['id']), headers=NO_STORE)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.patch('/api/admin/pull-workers/{node}')
async def pause_worker(node: str, request: Request):
    admin = _admin(request, write=True)
    body = await _body(request, ('accepting',), limit=1024)
    try:
        return JSONResponse(central.control(node, accepting=body['accepting'], actor_id=admin['id']), headers=NO_STORE)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.delete('/api/admin/pull-workers/{node}')
def revoke_worker(node: str, request: Request):
    admin = _admin(request, write=True)
    try:
        return JSONResponse(central.control(node, revoke=True, actor_id=admin['id']), headers=NO_STORE)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post('/api/pull-worker/claim')
@router.post('/api/pull-worker/{job}/heartbeat')
@router.post('/api/pull-worker/{job}/complete')
async def worker_call(request: Request, job: str = ''):
    _server()
    if central.mode() != 'pull':
        raise HTTPException(404, 'Pull execution is not enabled')
    action = request.url.path.rsplit('/', 1)[-1]
    fields = ('instance',) if action == 'claim' else ('instance', 'nonce', 'outcome') if action == 'complete' else ('instance', 'nonce')
    body = await _body(request, fields)
    try:
        if action == 'claim':
            result = {'task': central.assignment(worker_credential(request), body['instance'])}
        elif action == 'heartbeat':
            result = central.heartbeat(worker_credential(request), job, **body)
        else:
            from starlette.concurrency import run_in_threadpool
            result = await run_in_threadpool(central.complete, worker_credential(request), job, **body)
        return JSONResponse(result, headers=NO_STORE)
    except PermissionError as exc:
        raise HTTPException(401, 'Worker authentication required') from exc
    except (FenceBlocked, central.PullPending):
        return JSONResponse({'code': 'worker_execution_held', 'worker_stopped': False}, status_code=409, headers=NO_STORE)
    except (ValueError, KeyError, TypeError) as exc:
        raise HTTPException(400, 'Invalid worker payload') from exc


@router.post('/api/admin/pull-executions/{job}/recover')
async def recover_execution(job: str, request: Request):
    admin = _admin(request, write=True)
    body = await _body(request, ('confirm_recover',), limit=1024)
    if body['confirm_recover'] is not True:
        raise HTTPException(400, 'Explicit recovery confirmation required')
    try:
        _, meta = central.recover(job)
        with central.transaction() as c:
            target = central.hmac.new(auth._app_key(), job.encode(), central.hashlib.sha256).hexdigest()
            central._audit(c, admin['id'], 'completion-recovery', target,
                           {'execution_replayed': False, 'status': meta['pull_status']})
        return JSONResponse({'job_id': job, 'status': meta['pull_status'], 'execution_replayed': False}, headers=NO_STORE)
    except central.PullPending as exc:
        return JSONResponse(exc.detail(), status_code=409, headers=NO_STORE)
    except FenceBlocked as exc:
        raise HTTPException(409, 'Original economic owner and frozen result required') from exc


@router.get('/api/admin/pull-workers/audit')
def operator_history(request: Request):
    _admin(request)
    with central.transaction() as c:
        rows = [dict(r) for r in c.execute('SELECT actor_id,action,target,detail_json,created_at FROM ai_pull_operator_audit ORDER BY created_at DESC,id DESC LIMIT 100')]
    return JSONResponse({'events': rows}, headers=NO_STORE)


@router.get('/api/account/pull-executions')
def own_executions(request: Request):
    _server()
    user = auth.session_user(request)
    if not user or not user['active']:
        raise HTTPException(401, 'Authentication required')
    with auth.db() as c:
        rows = c.execute('SELECT job_id,kind,state,cancelled,created_at,completed_at FROM ai_pull_tasks WHERE user_id=? ORDER BY created_at DESC LIMIT 256', (user['id'],)).fetchall() if central.present(c) else []
    return JSONResponse({'tasks': [dict(r) for r in rows]}, headers=NO_STORE)


@router.get('/api/account/pull-executions/{job}/result')
def own_result(job: str, request: Request):
    _server()
    user = auth.session_user(request)
    if not user or not user['active']:
        raise HTTPException(401, 'Authentication required')
    with auth.db() as c:
        row = c.execute('SELECT * FROM ai_pull_tasks WHERE job_id=? AND user_id=?', (job, user['id'])).fetchone() if central.present(c) else None
        if row is None:
            raise HTTPException(404, 'Private result unavailable')
        proof = central._receipt(c, row, finished=True)
        if proof['state'] != 'finished' or proof['fence_status'] != 'closed' or row['result'] is None:
            raise HTTPException(409, 'Execution and accounting are still held')
        completion = central.decode(row['completion_json'])
        if completion['execution_status'] != 'done' or central._request_cancelled(c, row):
            raise HTTPException(404, 'No successful result')
        if central.hashlib.sha256(row['result']).hexdigest() != completion['result_sha256']:
            raise HTTPException(409, 'Frozen result integrity failed')
        return Response(bytes(row['result']), media_type=completion['media_type'], headers={**NO_STORE,
            'X-Content-Type-Options': 'nosniff', 'Content-Disposition': 'attachment; filename="result.bin"'})


@router.post('/api/admin/pull-executions/{job}/recover-publication')
async def recover_generated_publication(job: str, request: Request):
    admin = _admin(request, write=True)
    body = await _body(request, ('confirm_recover',), limit=1024)
    if body['confirm_recover'] is not True:
        raise HTTPException(400, 'Explicit recovery confirmation required')
    try:
        from starlette.concurrency import run_in_threadpool
        from .main import _publish_durable_generated_audio
        result = await run_in_threadpool(central.recover_publication, job, _publish_durable_generated_audio)
        with central.transaction() as c:
            target = central.hmac.new(auth._app_key(), job.encode(), central.hashlib.sha256).hexdigest()
            central._audit(c, admin['id'], 'publication-recovery', target, {'execution_replayed': False})
        return JSONResponse(result, headers=NO_STORE)
    except central.PullPending as exc:
        return JSONResponse(exc.detail(), status_code=409, headers=NO_STORE)
    except (FenceBlocked, ValueError) as exc:
        raise HTTPException(409, 'Original frozen publication remains held') from exc
