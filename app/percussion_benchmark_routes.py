"""Authenticated administration of benchmark campaigns and listening evidence.

These routes provide no model-rights override and infer no human approval. The
core owns frozen configuration, artifact verification and approval predicates.
"""
import re
import zipfile

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import Response

from . import auth, percussion_adapters as adapters, percussion_benchmark as bench
from . import percussion_dataset_import as dataset_import

router = APIRouter(prefix='/api/admin/ai-benchmarks')


def _actor(request):
    user = auth.require_admin(request)
    actor = int(user['id'])
    if actor <= 0:
        raise HTTPException(400, 'A registered administrator is required for benchmark evaluation')
    from .account_lifecycle import is_deleted
    if is_deleted(actor):
        raise HTTPException(403, 'Benchmark administrator is unavailable')
    return actor


def _call(operation):
    try:
        return operation()
    except (ValueError, TypeError, KeyError, OSError, zipfile.BadZipFile) as exc:
        raise HTTPException(400, str(exc)[:2000]) from exc


def _upload(file, limit):
    parts = []
    size = 0
    while chunk := file.file.read(min(1024 * 1024, limit + 1 - size)):
        size += len(chunk)
        if size > limit:
            raise HTTPException(413, 'Benchmark ZIP exceeds the upload limit')
        parts.append(chunk)
    if not size:
        raise HTTPException(400, 'A nonempty benchmark ZIP is required')
    return b''.join(parts)


def _case_id(value):
    # Composite dataset/case/source keys are lookups, never filesystem paths.
    if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,255}', value):
        raise ValueError('Invalid benchmark case identifier')
    return value


@router.get('/catalog')
def catalog(request: Request):
    _actor(request)
    return _call(bench.catalog)


@router.post('/datasets/synthetic')
def synthetic(request: Request, body: dict):
    _actor(request)
    if body:
        raise HTTPException(400, 'Synthetic corpus preparation accepts no options')
    return _call(bench.prepare_synthetic)


@router.post('/datasets/import')
def import_dataset(request: Request, file: UploadFile = File(...), acknowledge_rights: str = Form('false')):
    actor = _actor(request)
    if acknowledge_rights != 'true':
        raise HTTPException(400, 'Explicit recording-rights acknowledgement is required')
    data = _upload(file, dataset_import.MAX_COMPRESSED_BYTES)

    def import_declared():
        dataset_id = dataset_import.archive_identifier(data)
        with bench.locked('dataset-import'):
            destination = bench.root() / 'datasets' / dataset_id
            manifest = dataset_import.import_archive(data, destination, actor, True)
        return {'dataset': manifest}
    return _call(import_declared)


@router.post('/models/{model_id}/verify')
def verify_model(model_id: str, request: Request, body: dict):
    _actor(request)
    if body:
        raise HTTPException(400, 'Model verification accepts no override configuration')
    return _call(lambda: adapters.verify(bench.identifier(model_id)))


@router.put('/models/{model_id}/enabled')
def enable_model(model_id: str, request: Request, body: dict):
    _actor(request)
    if set(body) != {'enabled'} or type(body['enabled']) is not bool:
        raise HTTPException(400, 'Model activation requires one boolean enabled value')

    def configure():
        model = bench.identifier(model_id)
        known = {item['id'] for item in adapters.catalog()['models']}
        if model not in known:
            raise ValueError('Unknown percussion model')
        with bench.locked('model-activation'):
            enabled = set(adapters.enabled_models())
            if body['enabled']:
                enabled.add(model)
            else:
                enabled.discard(model)
            return adapters.configure_enabled(sorted(enabled))
    return _call(configure)


@router.get('/campaigns')
def campaigns(request: Request):
    _actor(request)
    return _call(bench.campaigns)


@router.post('/campaigns')
def create_campaign(request: Request, body: dict):
    actor = _actor(request)
    return _call(lambda: bench.create(body, actor))


@router.post('/campaigns/restore')
def restore_campaign(request: Request, file: UploadFile = File(...)):
    actor = _actor(request)
    data = _upload(file, bench.MAX_ARCHIVE_BYTES)
    # The recovered peer-review snapshot accepted only data and trusted imported
    # actor/approval fields. Require the actor-bound final core contract instead.
    return _call(lambda: bench.restore(data, actor))


@router.get('/campaigns/{cid}')
def campaign(cid: str, request: Request):
    _actor(request)
    return _call(lambda: bench.get(bench.identifier(cid)))


@router.post('/campaigns/{cid}/run')
def run_campaign(cid: str, request: Request, body: dict):
    actor = _actor(request)
    if set(body) - {'retry_failed'} or type(body.get('retry_failed', False)) is not bool:
        raise HTTPException(400, 'Invalid retry_failed flag')
    return _call(lambda: bench.start(bench.identifier(cid), actor, retry_failed=body.get('retry_failed', False)))


@router.post('/campaigns/{cid}/cancel')
def cancel_campaign(cid: str, request: Request, body: dict):
    _actor(request)
    if body:
        raise HTTPException(400, 'Cancellation accepts no job or actor overrides')

    def cancel():
        from . import ai_arranger_runtime as queue
        campaign_id = bench.identifier(cid)
        with bench.locked(campaign_id):
            value = bench._read(campaign_id)
            job_id = value.get('queue_job_id')
            job = queue.get(job_id) if job_id else None
            if not job or job.get('project_id') != 'benchmark-' + campaign_id or job.get('operation') != 'percussion-benchmark':
                raise ValueError('No original benchmark queue job is available to cancel')
            cancelled = queue.cancel(job_id)
            if not cancelled:
                raise ValueError('Benchmark queue job is unavailable')
            if cancelled['state'] == 'cancelled':
                value['status'] = 'cancelled'
            value['cancel_requested'] = bool(cancelled.get('cancel_requested') or cancelled['state'] == 'cancelled')
            bench._write(bench.folder(campaign_id) / 'campaign.json', value)
        result = bench.get(campaign_id)
        result['job'] = cancelled
        return result
    return _call(cancel)


@router.get('/campaigns/{cid}/blind')
def blind(cid: str, case_id: str, request: Request):
    _actor(request)
    return _call(lambda: bench.blind(bench.identifier(cid), _case_id(case_id)))


@router.get('/campaigns/{cid}/audio/{candidate}')
def candidate_audio(cid: str, candidate: str, request: Request, matched: bool = False):
    _actor(request)
    data = _call(lambda: bench.audio(bench.identifier(cid), bench.identifier(candidate), matched))
    return Response(data, media_type='audio/wav', headers={'Cache-Control': 'private, no-store', 'X-Content-Type-Options': 'nosniff'})


@router.get('/campaigns/{cid}/cases/{case_id}/{role}')
def source_audio(cid: str, case_id: str, role: str, request: Request):
    _actor(request)
    if role not in ('input', 'reference'):
        raise HTTPException(400, 'Invalid benchmark source audio role')
    data = _call(lambda: bench.case_audio(bench.identifier(cid), _case_id(case_id), role))
    return Response(data, media_type='audio/wav', headers={'Cache-Control': 'private, no-store', 'X-Content-Type-Options': 'nosniff'})


@router.post('/campaigns/{cid}/ratings')
def rate(cid: str, request: Request, body: dict):
    actor = _actor(request)
    return _call(lambda: bench.rate(bench.identifier(cid), body, actor))


@router.post('/campaigns/{cid}/approve')
def approve(cid: str, request: Request, body: dict):
    actor = _actor(request)
    return _call(lambda: bench.approve(bench.identifier(cid), body, actor))


@router.get('/campaigns/{cid}/export')
def export(cid: str, request: Request):
    _actor(request)
    campaign_id = _call(lambda: bench.identifier(cid))
    data = _call(lambda: bench.export(campaign_id))
    return Response(data, media_type='application/zip', headers={'Cache-Control': 'private, no-store',
                    'X-Content-Type-Options': 'nosniff', 'Content-Disposition': f'attachment; filename="mta-percussion-{campaign_id}.zip"'})


@router.get('/campaigns/{cid}/reports')
def reports(cid: str, request: Request):
    _actor(request)
    return _call(lambda: bench.reports(bench.identifier(cid)))


def restore_percussion_benchmark(pid, payload, job_id):
    """Existing durable queue integration calls the core's authenticated restorer."""
    return bench._restorer(pid, payload, job_id)
