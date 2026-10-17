"""Administrator-only metering, tariff and period-closing endpoints."""
from __future__ import annotations
import os
import csv
import io
import hashlib
import secrets
from pathlib import Path
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, Response
from .auth import require_admin
from . import ai_billing, ai_access

router=APIRouter()


@router.get('/api/admin/ai-billing/gpu-profiler')
def gpu_profiler_reports(request: Request):
    require_admin(request)
    from .ai_torch_diagnostics import recent_reports
    return {'billing_eligible': False, 'reports': recent_reports()}

def _error(call):
    try: return call()
    except (ValueError,TypeError,KeyError,OverflowError) as exc: raise HTTPException(400,str(exc)) from exc

@router.get('/api/admin/ai-billing/report')
def report(request:Request,period:str='month',user_id:int|None=None,anchor:str|None=None,start:str|None=None,end:str|None=None):
    require_admin(request)
    return _error(lambda:ai_billing.report(period,user_id=user_id,anchor=anchor,start=start,end=end))

@router.get('/api/admin/ai-billing/readiness')
def billing_readiness(request: Request):
    require_admin(request)
    from .ai_billing_readiness import check
    return check()

@router.get('/api/admin/ai-billing/reconcile')
def reconcile(request: Request, user_id: int, start: str, end: str):
    require_admin(request)
    return _error(lambda: ai_billing.reconcile_period(user_id, start, end))


@router.get('/api/admin/ai-billing/gpu-slots/preview')
def gpu_slot_preview(request: Request, gpu_key: str = 'gpu0',
                     start_ms: int = 0, end_ms: int = 0):
    """Read-only GPU slot report. Always zero-rate; never an invoice."""
    require_admin(request)
    from .ai_gpu_slot_accounting import preview
    return _error(lambda: preview(gpu_key,start_ms=start_ms,end_ms=end_ms,
                                  rate_micro_per_second=0))


@router.get('/api/admin/ai-billing/gpu-slots/recovery')
def gpu_slot_recovery(request: Request, older_than_ms: int = 3_600_000):
    """Only show stale candidates; destructive recovery remains operator CLI only."""
    require_admin(request)
    from .ai_gpu_slot_accounting import recover_stale_leases
    return _error(lambda:recover_stale_leases(older_than_ms=older_than_ms,dry_run=True))


@router.get('/api/admin/ai-billing/gpu-host-agent')
def gpu_host_agent(request: Request):
    require_admin(request)
    from .ai_proxmox_gpu_agent_client import snapshot
    return snapshot()


@router.get('/api/admin/ai-billing/gpu-host-agent/diagnostics')
def gpu_host_agent_diagnostics(request: Request):
    """Safe status view; telemetry is never a basis for per-job charges."""
    require_admin(request)
    from .ai_proxmox_gpu_agent_client import diagnostics
    return diagnostics()


@router.get('/api/admin/ai-billing/suggested-prices')
def suggested_prices(request: Request, cpu_model: str | None = None, gpu_model: str | None = None):
    require_admin(request)
    from .ai_billing_profiles import suggested_prices as get_suggestions
    return get_suggestions(cpu_model=cpu_model, gpu_model=gpu_model)


@router.get('/api/admin/ai-billing/user-settings')
def billing_users(request: Request):
    require_admin(request)
    return {'items': ai_billing.user_billing_settings(), 'default_enabled': False}


@router.put('/api/admin/ai-billing/user-settings/{user_id}')
def update_billing_user(request: Request, user_id: int, body: dict):
    require_admin(request)
    return _error(lambda: ai_billing.set_user_billing_enabled(user_id, body['enabled']))


@router.get('/api/admin/ai-billing/prices')
def prices(request:Request):
    require_admin(request)
    return {'currency':'EUR','prices_micro':ai_billing.prices(),'units':ai_billing.UNITS,'validity':ai_billing.tariff_history(), 'billing_default_enabled':False}

@router.put('/api/admin/ai-billing/prices/{resource}')
def update_price(resource:str,body:dict,request:Request):
    require_admin(request)
    return _error(lambda:(ai_billing.set_price(resource,body['micro_per_unit'],valid_from=body.get('valid_from'),valid_until=body.get('valid_until')),{'ok':True})[1])

@router.post('/api/admin/ai-billing/close')
def close(request:Request,body:dict):
    require_admin(request)
    def close_if_enabled():
        user_id = int(body['user_id'])
        if not ai_billing.user_billing_enabled(user_id):
            raise ValueError('Billing is disabled for this user; statistics remain available')
        return ai_billing.close_period(user_id, body['start'], body['end'])
    return _error(close_if_enabled)

@router.get('/api/admin/ai-billing/audit-closed')
def audit_closed(request: Request, user_id: int | None = None):
    require_admin(request)
    return _error(lambda: ai_billing.audit_closed_invoices(user_id))

@router.get('/api/admin/ai-billing/invoices')
def invoices(request:Request,user_id:int|None=None):
    require_admin(request)
    return {'items':ai_billing.bills(user_id)}

@router.put('/api/admin/ai-billing/schedules/{user_id}')
def schedule(request:Request,user_id:int,body:dict):
    require_admin(request)
    return _error(lambda:(ai_billing.configure_schedule(user_id,body['cadence'],body.get('enabled',True)),{'ok':True})[1])

@router.get('/api/admin/ai-billing/schedules')
def schedule_list(request:Request):
    require_admin(request)
    return {'items':ai_billing.schedules()}

@router.post('/api/admin/ai-billing/run-schedules')
def process_schedules(request:Request):
    require_admin(request)
    return {'items':ai_billing.run_scheduled_closures()}

@router.get('/api/admin/ai-billing/export.csv')
def export_csv(request:Request,period:str='month',user_id:int|None=None,anchor:str|None=None,start:str|None=None,end:str|None=None):
    require_admin(request)
    data=_error(lambda:ai_billing.report(period,user_id=user_id,anchor=anchor,start=start,end=end))
    buf=io.StringIO()
    writer=csv.writer(buf)
    writer.writerow(['utc_date','user_id','jobs','metered_jobs','cost_micro_eur','resources_json'])
    for r in data['rows']:
        writer.writerow([r['day'],r['user_id'],r['jobs'],r['metered_jobs'],r['cost_micro'],
                         __import__('json').dumps(r['resources'],sort_keys=True)])
    return Response(buf.getvalue(),media_type='text/csv',headers={'Content-Disposition':'attachment; filename="ai-usage.csv"'})

@router.get('/api/admin/ai-billing/gpu-calibrations')
def list_gpu_calibrations(request: Request):
    require_admin(request)
    from .ai_gpu_energy_estimator import calibrations
    return {'items': calibrations()}


@router.put('/api/admin/ai-billing/gpu-calibrations')
def save_gpu_calibration(request: Request, body: dict):
    require_admin(request)
    from .ai_gpu_energy_estimator import EnergyCalibration, store_calibration
    def save():
        profile = EnergyCalibration(gpu_id=body['gpu_id'],
                                    idle_watts=float(body['idle_watts']),
                                    full_load_watts=float(body['full_load_watts']))
        store_calibration(profile)
        return {'ok': True, 'billing_status': 'calibration_only_not_certified'}
    return _error(save)


@router.post('/api/admin/ai-billing/gpu-energy-estimate')
def admin_gpu_energy_estimate(request: Request, body: dict):
    require_admin(request)
    from .ai_gpu_energy_estimator import EnergyCalibration, calibrations, estimate_job_energy
    def calculate():
        p = next((row for row in calibrations() if row['gpu_id'] == body['gpu_id']), None)
        if p is None:
            raise ValueError('GPU calibration not found')
        return estimate_job_energy(EnergyCalibration(p['gpu_id'],p['idle_watts'],p['full_load_watts']),
            gpu_engine_seconds=float(body['gpu_engine_seconds']),
            job_wall_seconds=float(body['job_wall_seconds']),
            exclusive_gpu=body.get('exclusive_gpu') is True,
            complete_lifecycle=body.get('complete_lifecycle') is True,
            baseline_policy=body.get('baseline_policy','incremental'))
    return _error(calculate)


@router.post('/api/ai-jobs')
def start_remote_job(request:Request,body:dict):
    header=request.headers.get('authorization','')
    token=header[7:] if header.lower().startswith('bearer ') else ''
    identity=ai_access.authenticate(token)
    if not identity:
        raise HTTPException(401,'Valid AI user token required')
    # The backend worker must independently claim/execute the job. Creating a
    # ledger entry does not itself schedule arbitrary commands on the host.
    return _error(lambda:{'job_id':ai_billing.create_job(identity['user_id'],body['kind'],identity['id']),
                          'status':'running','execution':'worker-required'})

@router.post('/api/internal/ai-metering/jobs/{job_id}/finish')
def submit_metering(job_id:str,request:Request,body:dict):
    # Strictly opt-in; must not be exposed through ingress. A service-specific key
    # is not an end-user token; avoid forwarding it to ACE-Step.
    expected=os.getenv('MTA_AI_METERING_KEY','')
    provided=request.headers.get('x-mta-metering-key','')
    if not expected or not secrets.compare_digest(provided,expected):
        raise HTTPException(403,'Metering agent authentication required')
    return _error(lambda:(ai_billing.finish_job(job_id,body['status'],body.get('usage'),source=body.get('source','worker')),{'ok':True})[1])

@router.get('/admin/ai-billing',response_class=HTMLResponse)
def billing_page(request:Request):
    require_admin(request)
    return HTMLResponse((Path(__file__).parent / 'templates' / 'ai_billing.html').read_text(encoding='utf-8'))

def _verified_worker_response(result, meta, *, max_bytes=None):
    """Validate a billable worker result before caching or acknowledging it.

    An already-metered oversized/broken result must never be advertised as a
    completed, recoverable request. No retry may execute the worker again.
    """
    from .ai_remote_client import ALLOWED_TYPES
    if max_bytes is None:
        from .ai_payload_limits import MAX_RESULT_BYTES
        max_bytes = MAX_RESULT_BYTES
    if not isinstance(result, bytes) or not result:
        raise HTTPException(502, 'Worker returned an empty or invalid result')
    if len(result) > max_bytes:
        raise HTTPException(413, 'AI result exceeds response limit')
    if not isinstance(meta, dict):
        raise HTTPException(502, 'Worker result metadata missing')
    job_id = meta.get('job_id')
    if (not isinstance(job_id, str) or not 1 <= len(job_id) <= 128
            or any(ord(ch) < 33 or ord(ch) > 126 for ch in job_id)):
        raise HTTPException(502, 'Worker job identifier invalid')
    media_type = meta.get('media_type', 'audio/wav')
    if media_type not in ALLOWED_TYPES:
        raise HTTPException(502, 'Worker result media type invalid')
    return job_id, media_type


def _remote_metering_headers(meta: dict, request_key: str) -> dict[str, str]:
    """Optional operator-signed CPU evidence for one persisted remote request.

    Never attest GPU, anonymous requests, or unisolated process measurements.
    Missing configuration preserves backwards-compatible result delivery, but
    malformed *configured* signing policy fails closed.
    """
    import json
    from .ai_remote_metering_attestation import sign_rotating
    from .ai_remote_keyring import active_keyring
    key_id = os.getenv('MTA_AI_REMOTE_METERING_SIGNING_KEY_ID', '')
    if not key_id:
        return {}
    if not request_key or not meta.get('process_tree_metered'):
        return {}
    usage = meta.get('usage')
    if not isinstance(usage, dict) or 'cpu_seconds' not in usage:
        return {}
    # Operator-selected identity, not a caller-supplied arbitrary claim.
    worker_id = os.getenv('MTA_AI_REMOTE_METERING_WORKER_ID', '')
    keys = active_keyring()
    if key_id not in keys:
        raise ValueError('Configured metering signing key unavailable or revoked')
    envelope = sign_rotating(keys[key_id], key_id=key_id,
        job_id=meta['job_id'], request_id=request_key, worker_id=worker_id,
        usage={'cpu_seconds': usage['cpu_seconds']})
    return {'X-MTA-AI-Metering-V2': json.dumps(envelope, sort_keys=True, separators=(',', ':'))}


@router.post('/api/ai-jobs/execute')
def execute_remote_ai_job(request: Request, body: dict):
    """Authenticated execution with fixed operator-configured worker and CPU metering.

    This endpoint only handles self-contained JSON plans. Audio input transport
    is not yet supported: do not expose arbitrary filesystem paths or commands.
    """
    header = request.headers.get('authorization', '')
    token = header[7:] if header.lower().startswith('bearer ') else ''
    identity = ai_access.authenticate(token)
    if not identity:
        raise HTTPException(401, 'Valid AI token required')
    from .ai_metering_agent import execute_registered_worker
    from .ai_worker_protocol import WorkerUnavailable
    kind = body.get('kind', '')
    plan = body.get('plan')
    if not isinstance(plan, dict):
        raise HTTPException(400, 'JSON worker plan required')
    # Local filesystem paths must never be provided by remote callers.
    if any(k in plan for k in ('source_audio', 'input_path', 'output_path', 'command', 'executable')):
        raise HTTPException(400, 'File-backed plans require staged authenticated transfer')
    from . import ai_request_dedup as dedup
    import json
    key = request.headers.get('x-mta-ai-idempotency-key', '')
    if key:
        try:
            dedup.admit(identity['user_id'], key, dedup.fingerprint(kind, json.dumps(plan, sort_keys=True).encode(), b''))
        except dedup.DuplicateAIRequest as exc:
            raise HTTPException(409, {'reason': 'duplicate_request', 'state': exc.state, 'job_id': exc.job_id}) from exc
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
    try:
        result, meta = execute_registered_worker(identity['user_id'], kind, plan, token_id=identity['id'],
            cancel_check=(lambda: dedup.is_cancelled(identity['user_id'], key)) if key else None)
    except WorkerUnavailable as exc:
        if key and not dedup.is_cancelled(identity['user_id'], key): dedup.finalize(identity['user_id'], key, state='failed')
        raise HTTPException(503, str(exc)) from exc
    except RuntimeError as exc:
        if key and dedup.is_cancelled(identity['user_id'], key):
            raise HTTPException(409, 'AI request cancelled; worker stopped') from exc
        raise
    except (ValueError, TypeError) as exc:
        if key and not dedup.is_cancelled(identity['user_id'], key): dedup.finalize(identity['user_id'], key, state='failed')
        raise HTTPException(400, str(exc)) from exc
    finally:
        pass  # Unexpected crashes deliberately retain an admitted claim.
    try:
        worker_job_id, worker_media_type = _verified_worker_response(result, meta)
    except HTTPException:
        if key and not dedup.is_cancelled(identity['user_id'], key): dedup.finalize(identity['user_id'], key, state='failed')
        raise
    try:
        metering_headers = _remote_metering_headers(meta, key)
    except ValueError as exc:
        if key and not dedup.is_cancelled(identity['user_id'], key): dedup.finalize(identity['user_id'], key, state='failed')
        raise HTTPException(503, 'Remote worker metering attestation unavailable') from exc
    if key:
        from .ai_request_dedup import is_cancelled
        if is_cancelled(identity['user_id'], key):
            raise HTTPException(409, 'AI request cancelled; worker result discarded')
        from .ai_result_cache import save as save_result
        # A billable request must not be advertised as completed until its
        # replay artifact is durable. A failed cache write never authorizes
        # executing the billed inference a second time with the same key.
        try:
            save_result(identity['user_id'], key, result, worker_media_type, worker_job_id, **({'metering_envelope': __import__('json').loads(metering_headers['X-MTA-AI-Metering-V2'])} if metering_headers else {}))
        except (OSError, ValueError) as exc:
            dedup.finalize(identity['user_id'], key, state='failed')
            raise HTTPException(503, 'Remote AI result could not be durably published; request cannot be retried') from exc
        try:
            dedup.finalize(identity['user_id'], key, job_id=worker_job_id)
        except ValueError as exc:
            raise HTTPException(409, 'AI request changed while publishing; result not accepted') from exc
    return Response(result, media_type=worker_media_type, headers={'X-MTA-AI-Job-ID': worker_job_id, 'X-MTA-AI-Result-SHA256': hashlib.sha256(result).hexdigest(), 'X-MTA-AI-Request-ID': key, **metering_headers} if key else {'X-MTA-AI-Job-ID': worker_job_id, 'X-MTA-AI-Result-SHA256': hashlib.sha256(result).hexdigest()})


@router.post('/api/ai-jobs/request-cancel/{request_key}')
def remote_request_cancel(request_key: str, request: Request):
    """Owner-only, durable cancellation barrier (not a force-kill guarantee)."""
    header = request.headers.get('authorization', '')
    token = header[7:] if header.lower().startswith('bearer ') else ''
    identity = ai_access.authenticate(token)
    if not identity:
        raise HTTPException(401, 'Valid AI token required')
    from .ai_request_dedup import cancel_admitted
    try:
        status = cancel_admitted(identity['user_id'], request_key)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    if status is None:
        raise HTTPException(404, 'AI request not found')
    return {**status, 'worker_stop_guaranteed': False}


@router.get('/api/ai-jobs/requests')
def remote_request_history(request: Request, limit: int = 50, offset: int = 0, state: str | None = None):
    """Authenticated durable request discovery for clients after a restart."""
    header = request.headers.get('authorization', '')
    token = header[7:] if header.lower().startswith('bearer ') else ''
    identity = ai_access.authenticate(token)
    if not identity:
        raise HTTPException(401, 'Valid AI token required')
    from .ai_request_dedup import list_requests
    try:
        return list_requests(identity['user_id'], limit=limit, offset=offset, state=state)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.get('/api/ai-jobs/request-status/{request_key}')
def remote_request_status(request_key: str, request: Request):
    """Safe status lookup for timed-out remote requests; never starts a job."""
    header = request.headers.get('authorization', '')
    token = header[7:] if header.lower().startswith('bearer ') else ''
    identity = ai_access.authenticate(token)
    if not identity:
        raise HTTPException(401, 'Valid AI token required')
    from .ai_request_dedup import reconcile_published
    try:
        status = reconcile_published(identity['user_id'], request_key)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    if status is None:
        raise HTTPException(404, 'AI request not found')
    return status


@router.get('/api/ai-jobs/request-result/{request_key}')
def remote_request_result(request_key: str, request: Request):
    """Owner-only, read-only replay of a completed request, never inference."""
    header = request.headers.get('authorization', '')
    token = header[7:] if header.lower().startswith('bearer ') else ''
    identity = ai_access.authenticate(token)
    if not identity:
        raise HTTPException(401, 'Valid AI token required')
    from .ai_request_dedup import reconcile_published
    from .ai_result_cache import load_with_metering
    try:
        status = reconcile_published(identity['user_id'], request_key)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    if status is None:
        raise HTTPException(404, 'AI request not found')
    if status['state'] != 'completed' or not status['job_id']:
        raise HTTPException(409, 'AI request has no completed result')
    result = load_with_metering(identity['user_id'], request_key, status['job_id'])
    if result is None:
        raise HTTPException(410, 'Result not retained or expired; inference will not be repeated')
    payload, media_type, envelope = result
    metering_headers = {'X-MTA-AI-Metering-V2': __import__('json').dumps(envelope, sort_keys=True, separators=(',', ':'))} if envelope is not None else {}
    return Response(payload, media_type=media_type, headers={**metering_headers, 'X-MTA-AI-Job-ID': status['job_id'], 'X-MTA-AI-Result-SHA256': hashlib.sha256(payload).hexdigest(), 'X-MTA-AI-Request-ID': request_key, 'Cache-Control':'private, no-store'})


@router.get('/api/ai-jobs/worker-capabilities')
def ai_worker_capabilities(request: Request):
    header = request.headers.get('authorization', '')
    token = header[7:] if header.lower().startswith('bearer ') else ''
    if not ai_access.authenticate(token):
        raise HTTPException(401, 'Valid AI token required')
    from .ai_worker_registry import available_workers
    from .ai_gpu_verified import readiness,VERIFIED_KINDS
    return {'workers': available_workers(), 'audio_transport': 'wav', 'output': ['wav', 'artifact-zip-v1'],
            'admission':'global-ai-queue','gpu_billing':readiness(),'gpu_evidence_kinds':sorted(VERIFIED_KINDS)}


@router.post('/api/ai-jobs/execute-audio/{kind}')
async def execute_remote_ai_audio_job(kind: str, request: Request):
    """WAV upload to a fixed per-kind adapter; never accept a client filesystem path."""
    header = request.headers.get('authorization', '')
    token = header[7:] if header.lower().startswith('bearer ') else ''
    identity = ai_access.authenticate(token)
    if not identity:
        raise HTTPException(401, 'Valid AI token required')
    from .ai_worker_registry import resolve_worker
    from .ai_metering_agent import execute_registered_worker
    from .ai_worker_protocol import WorkerUnavailable
    try:
        if resolve_worker(kind) is None:
            raise HTTPException(503, 'This AI model adapter is not installed or enabled')
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    if request.headers.get('content-type', '').split(';')[0].strip().lower() not in ('audio/wav', 'audio/x-wav', 'application/octet-stream'):
        raise HTTPException(415, 'WAV content required')
    from .ai_payload_limits import MAX_SOURCE_BYTES
    max_bytes = MAX_SOURCE_BYTES
    declared_length = request.headers.get('content-length', '0') or '0'
    if not declared_length.isdecimal():
        raise HTTPException(400, 'Invalid content length')
    if int(declared_length) > max_bytes:
        raise HTTPException(413, 'Input audio exceeds size limit')
    from .ai_remote_transport import decode_audio_options
    try:
        options = decode_audio_options(request.headers.get('x-mta-ai-options', ''))
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    data = bytearray()
    async for chunk in request.stream():
        data.extend(chunk)
        if len(data) > max_bytes:
            raise HTTPException(413, 'Input audio exceeds size limit')
    if not data:
        raise HTTPException(400, 'Empty audio input')
    if request.headers.get('content-length') is not None and len(data) != int(declared_length):
        raise HTTPException(400, 'Audio body length differs from Content-Length')
    if 'kind' in options and options['kind'] != kind:
        raise HTTPException(400, 'AI options cannot override worker kind')
    from . import ai_request_dedup as dedup
    import json
    key = request.headers.get('x-mta-ai-idempotency-key', '')
    if key:
        try:
            digest = dedup.fingerprint(kind, json.dumps(options, sort_keys=True).encode(), bytes(data))
            dedup.admit(identity['user_id'], key, digest)
        except dedup.DuplicateAIRequest as exc:
            raise HTTPException(409, {'reason': 'duplicate_request', 'state': exc.state, 'job_id': exc.job_id}) from exc
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
    # A cancellation may arrive after durable admission but before worker
    # dispatch. Do not spend resources on a request already tombstoned.
    if key and dedup.is_cancelled(identity['user_id'], key):
        raise HTTPException(409, 'AI request cancelled before worker dispatch')
    try:
        from starlette.concurrency import run_in_threadpool
        result, meta = await run_in_threadpool(execute_registered_worker, identity['user_id'], kind, {'kind': kind, **options},
            token_id=identity['id'], source_wav=bytes(data),
            **({'timeout_seconds': __import__('app.ai_execution_limits',fromlist=['inference_timeout']).inference_timeout(options)} if kind=='ace-step' else {}),
            cancel_check=(lambda: dedup.is_cancelled(identity['user_id'], key)) if key else None)
    except WorkerUnavailable as exc:
        if key and not dedup.is_cancelled(identity['user_id'], key): dedup.finalize(identity['user_id'], key, state='failed')
        raise HTTPException(503, str(exc)) from exc
    except RuntimeError as exc:
        if key and dedup.is_cancelled(identity['user_id'], key):
            raise HTTPException(409, 'AI request cancelled; worker stopped') from exc
        raise
    except (ValueError, TypeError) as exc:
        if key and not dedup.is_cancelled(identity['user_id'], key): dedup.finalize(identity['user_id'], key, state='failed')
        raise HTTPException(400, str(exc)) from exc
    try:
        worker_job_id, worker_media_type = _verified_worker_response(result, meta)
    except HTTPException:
        if key and not dedup.is_cancelled(identity['user_id'], key): dedup.finalize(identity['user_id'], key, state='failed')
        raise
    try:
        metering_headers = _remote_metering_headers(meta, key)
    except ValueError as exc:
        if key and not dedup.is_cancelled(identity['user_id'], key): dedup.finalize(identity['user_id'], key, state='failed')
        raise HTTPException(503, 'Remote worker metering attestation unavailable') from exc
    if key:
        from .ai_request_dedup import is_cancelled
        if is_cancelled(identity['user_id'], key):
            raise HTTPException(409, 'AI request cancelled; worker result discarded')
        from .ai_result_cache import save as save_result
        # A billable request must not be advertised as completed until its
        # replay artifact is durable. A failed cache write never authorizes
        # executing the billed inference a second time with the same key.
        try:
            save_result(identity['user_id'], key, result, worker_media_type, worker_job_id, **({'metering_envelope': __import__('json').loads(metering_headers['X-MTA-AI-Metering-V2'])} if metering_headers else {}))
        except (OSError, ValueError) as exc:
            dedup.finalize(identity['user_id'], key, state='failed')
            raise HTTPException(503, 'Remote AI result could not be durably published; request cannot be retried') from exc
        try:
            dedup.finalize(identity['user_id'], key, job_id=worker_job_id)
        except ValueError as exc:
            raise HTTPException(409, 'AI request changed while publishing; result not accepted') from exc
    return Response(result, media_type=worker_media_type, headers={'X-MTA-AI-Job-ID': worker_job_id, 'X-MTA-AI-Result-SHA256': hashlib.sha256(result).hexdigest(), 'X-MTA-AI-Request-ID': key, **metering_headers} if key else {'X-MTA-AI-Job-ID': worker_job_id, 'X-MTA-AI-Result-SHA256': hashlib.sha256(result).hexdigest()})


@router.get('/api/admin/ai-billing/remote-metering-keys/status')
def remote_metering_key_status(request: Request):
    """Administrator-only diagnostics, never expose key IDs or key material."""
    require_admin(request)
    from .ai_remote_keyring import public_status
    return public_status()


@router.get('/api/ai-jobs/resources/{job_id}')
def remote_job_resources(job_id: str,request: Request):
    """Owner-bound resource receipt; never treat diagnostic estimates as billed use."""
    header=request.headers.get('authorization','')
    identity=ai_access.authenticate(header[7:] if header.lower().startswith('bearer ') else '')
    if not identity:raise HTTPException(401,'Valid AI token required')
    import json
    with ai_billing.db() as con:
        ai_billing._init(con)
        row=con.execute('SELECT * FROM ai_compute_jobs WHERE id=? AND user_id=? AND token_id=?',
                        (job_id,identity['user_id'],identity['id'])).fetchone()
        if not row:raise HTTPException(404,'AI job not found')
        row=dict(row)
        exists=con.execute("SELECT 1 FROM sqlite_master WHERE name='ai_verified_gpu_evidence'").fetchone()
        proof=con.execute('SELECT envelope FROM ai_verified_gpu_evidence WHERE job_id=?',(job_id,)).fetchone() if exists else None
    result={'job_id':job_id,'queue_job_id':row['queue_job_id'],'status':row['status'],
            'usage':json.loads(row['usage_json']),'metering_source':row['resource_source'],
            'gpu_verified':bool(proof),'billing_enabled':ai_billing.user_billing_enabled(identity['user_id'])}
    if proof:
        value=json.loads(proof[0])['payload']
        result['gpu_evidence']={key:value[key] for key in ('id','method','calibration_id','trace_sha256')}
    return result
