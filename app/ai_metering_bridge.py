"""Fail-closed durable inference metering to billing handoff.

This is a recovery-safe saga. Never derive GPU consumption from wall time or
label anonymous progress numbers as GPU-agent measurements.
"""
from __future__ import annotations

import json

from . import ai_arranger_runtime as queue, ai_billing, ai_billing_outbox


def _identity(job_id):
    queue._validate_job_id(job_id)
    with queue._db() as con:
        row = con.execute('SELECT operation,payload_json FROM jobs WHERE job_id=?', (job_id,)).fetchone()
    if not row or row['operation'] not in ('arranger', 'remix') or not row['payload_json']:
        raise ValueError('Durable audio inference required')
    payload = json.loads(row['payload_json'])
    user = payload.get('actor_user_id')
    if (payload.get('schema_version') != 1 or type(user) is not int or user <= 0
            or ('adapter' in payload and payload['adapter'] != row['operation'])):
        raise ValueError('Authenticated durable payload required')
    return user, row['operation']


def capture(job_id, usage, source):
    """Persist a *trusted-origin* final measurement before sidecars disappear.

    Only the internal executor should invoke this interface. The GPU agent
    must independently authenticate measurements before using gpu-agent.
    """
    _identity(job_id)
    normalized = ai_billing._validate_usage(usage)
    if source not in ('worker', 'cgroup', 'gpu-agent','gpu-kernel-verified','diagnostic-estimate', 'remote-worker') or not normalized:
        raise ValueError('Nonempty trusted measurement required')
    if any(k.startswith('gpu_') for k in normalized) and source not in ('gpu-agent','gpu-kernel-verified','diagnostic-estimate'):
        raise ValueError('GPU accounting requires authenticated GPU agent')
    if source == 'gpu-agent' and not any(k.startswith('gpu_') for k in normalized):
        raise ValueError('GPU agent measurement missing')
    if source in ('gpu-kernel-verified','diagnostic-estimate'):
        import uuid
        if source=='diagnostic-estimate':from .ai_trusted_estimates import require_evidence
        else:from .ai_gpu_verified import require_evidence
        ledger_id=uuid.uuid5(uuid.NAMESPACE_URL,'mta-ai-inference:'+job_id).hex
        with ai_billing.db() as con:
            ai_billing._init(con)
            rows=con.execute('SELECT id FROM ai_compute_jobs WHERE queue_job_id=? AND user_id=?',(job_id,_identity(job_id)[0])).fetchall()
        if len(rows)==1:ledger_id=rows[0][0]
        require_evidence(ledger_id,normalized)
    from .deferred_execution_owner import receipt_for
    owner=receipt_for(job_id)
    if owner:
        from .worker_loss_resolution import mark_evidence
        mark_evidence(owner['ledger_id'],owner['worker_id'],owner['claim_token'])
    encoded = json.dumps({'usage': normalized, 'source': source,**({'execution_owner':owner} if owner else {})}, sort_keys=True, allow_nan=False)
    with queue._db() as con:
        con.execute('''CREATE TABLE IF NOT EXISTS ai_metering_evidence
                       (job_id TEXT PRIMARY KEY, evidence_json TEXT NOT NULL)''')
        con.execute('BEGIN IMMEDIATE')
        row = con.execute('SELECT evidence_json FROM ai_metering_evidence WHERE job_id=?', (job_id,)).fetchone()
        if row and row[0] != encoded:
            con.execute('ROLLBACK')
            raise ValueError('Conflicting immutable metering evidence')
        if not row:
            con.execute('INSERT INTO ai_metering_evidence VALUES(?,?)', (job_id, encoded))
        # Expose only authenticated usage. Unknown GPU time remains NULL,
        # never a wall-clock estimate presented as verified consumption.
        if source=='diagnostic-estimate':
            con.execute('UPDATE jobs SET cpu_seconds_estimated=?,gpu_seconds_estimated=?,gpu_metrics_source=?,gpu_metrics_status=? WHERE job_id=?',
                (normalized.get('cpu_seconds'),normalized.get('gpu_seconds'),source,'diagnostic_estimate_trusted',job_id))
        else:
            con.execute('UPDATE jobs SET cpu_seconds=COALESCE(?,cpu_seconds), gpu_seconds=COALESCE(?,gpu_seconds) WHERE job_id=?',
                        (normalized.get('cpu_seconds'), normalized.get('gpu_seconds'), job_id))
        con.execute('COMMIT')
    return not bool(row)


def billing_required(job_id):
    """Read the durable authenticated billing policy for the inference."""
    try:
        user, operation = _identity(job_id)
    except ValueError:
        return False  # legacy jobs are not automatically bound to billing
    return (ai_billing.existing_inference_ledger_job(job_id, user, operation) is not None
            or ai_billing.user_billing_enabled(user))


def register_settlement(job_id, status='done'):
    """Create a verified billing intent from persisted evidence, if opted in.

    Return True if settlement is registered (including replay), False for
    non-billable jobs. Missing evidence on billable jobs is a hard failure.
    """
    user, operation = _identity(job_id)
    prior_ledger_id = ai_billing.existing_inference_ledger_job(job_id, user, operation)
    if prior_ledger_id is None and not ai_billing.user_billing_enabled(user):
        return False
    with queue._db() as con:
        con.execute('''CREATE TABLE IF NOT EXISTS ai_metering_evidence
                       (job_id TEXT PRIMARY KEY, evidence_json TEXT NOT NULL)''')
        record = con.execute('SELECT evidence_json FROM ai_metering_evidence WHERE job_id=?', (job_id,)).fetchone()
    if not record:
        raise ValueError('Measured consumption is required before billable completion')
    evidence = json.loads(record[0])
    ledger_id = prior_ledger_id or ai_billing.provision_inference_job(job_id, user, operation)
    if ledger_id is None:
        raise ValueError('Billing opt-in changed during finalization')
    owner=evidence.get('execution_owner')
    credentials={}
    if owner is not None:
        if not isinstance(owner,dict) or set(owner)!={'inference_id','ledger_id','worker_id','claim_token'} or owner['inference_id']!=job_id or owner['ledger_id']!=ledger_id:
            raise ValueError('Invalid deferred execution owner binding')
        credentials={k:owner[k] for k in ('worker_id','claim_token')}
    ai_billing_outbox.register_verified(job_id, ledger_id, user, status,
                                       evidence['usage'], source=evidence['source'],**credentials)
    return True


def capture_authenticated_remote(job_id, envelope, *, request_id, worker_id, worker_key):
    """Store a worker-authenticated *CPU* assertion for durable Arranger/Remix.

    This explicitly does not certify GPU use. Callers must authenticate the
    worker identity and bind the originating request before invoking this.
    """
    from .ai_remote_metering_attestation import verify
    _identity(job_id)
    usage = verify(worker_key, envelope, job_id=job_id,
                   request_id=request_id, worker_id=worker_id)
    return capture(job_id, usage, 'remote-worker')


def capture_rotating_remote(job_id, envelope, *, request_id, worker_id, keyring):
    """Capture a v2 CPU assertion after explicit trust-key lookup.

    A revoked key must no longer appear in the keyring; no fallback to v1.
    """
    from .ai_remote_metering_attestation import verify_rotating
    _identity(job_id)
    usage = verify_rotating(keyring, envelope, job_id=job_id,
                            request_id=request_id, worker_id=worker_id)
    return capture(job_id, usage, 'remote-worker')


def capture_operator_authenticated_remote(job_id, envelope, *, request_id, worker_id):
    """Production ingress: verify v2 using freshly loaded operator trust keys.

    This never accepts client-provided secrets or a v1 downgrade and does not
    assert any GPU hardware usage. The caller must still authorize the worker
    and bind the originating durable request to the authenticated principal.
    """
    from .ai_remote_keyring import active_keyring
    return capture_rotating_remote(job_id, envelope, request_id=request_id,
                                   worker_id=worker_id, keyring=active_keyring())


def durable_remote_sink(local_job_id, *, request_id, worker_id):
    """Build a local-ledger sink for an authenticated remote client call.

    The remote client MUST verify the rotating-key envelope before calling
    this closure. Bind the remote identity immutably to the local durable job;
    never assume remote and local job IDs match. This is a trusted internal API.
    """
    import re
    valid = re.compile(r'[A-Za-z0-9_-]{1,128}\Z')
    _identity(local_job_id)
    if not isinstance(request_id, str) or not valid.fullmatch(request_id):
        raise ValueError('Invalid expected remote request ID')
    if not isinstance(worker_id, str) or not valid.fullmatch(worker_id):
        raise ValueError('Invalid expected remote worker ID')

    def accept(envelope, usage):
        if not isinstance(envelope, dict):
            raise ValueError('Missing verified remote metering envelope')
        remote_job_id = envelope.get('job_id')
        if not isinstance(remote_job_id, str) or not valid.fullmatch(remote_job_id):
            raise ValueError('Invalid remote job ID')
        if envelope.get('request_id') != request_id or envelope.get('worker_id') != worker_id:
            raise ValueError('Remote metering binding mismatch')
        normalized = ai_billing._validate_usage(usage)
        if not normalized or 'cpu_seconds' not in normalized or any(k.startswith('gpu_') for k in normalized):
            raise ValueError('Unsupported remote CPU evidence')
        with queue._db() as con:
            con.execute('''CREATE TABLE IF NOT EXISTS ai_remote_job_bindings
                           (local_job_id TEXT PRIMARY KEY, remote_job_id TEXT NOT NULL,
                            request_id TEXT NOT NULL, worker_id TEXT NOT NULL,
                            UNIQUE(request_id, worker_id))''')
            con.execute('BEGIN IMMEDIATE')
            existing = con.execute('SELECT remote_job_id,request_id,worker_id FROM ai_remote_job_bindings WHERE local_job_id=?',
                                   (local_job_id,)).fetchone()
            binding = (remote_job_id, request_id, worker_id)
            if existing is not None and tuple(existing) != binding:
                con.execute('ROLLBACK')
                raise ValueError('Conflicting durable remote-job association')
            if existing is None:
                con.execute('INSERT INTO ai_remote_job_bindings VALUES(?,?,?,?)', (local_job_id, *binding))
            con.execute('COMMIT')
        return capture(local_job_id, normalized, 'remote-worker')

    return accept


def infer_durable_remote(local_job_id, *, base_url, token, wav, options=None,
                         worker_id, timeout_seconds=900, cancel_event=None):
    """Execute/replay a billable durable audio job with a stable remote identity.

    No HTTP endpoint should accept worker_id/base_url/token from an untrusted
    caller. This is an internal operator-configured API. A failed remote request
    cannot silently fall back to a local model or silently skip metering.
    """
    import hashlib
    import re
    from .ai_remote_client import infer_audio
    from .ai_remote_keyring import active_keyring
    user, operation = _identity(local_job_id)
    if operation not in ('arranger', 'remix'):
        raise ValueError('Unsupported durable remote operation')
    from .model_license_policy import authorize_remote_execution
    authorize_remote_execution(operation,options or {})
    if not isinstance(worker_id, str) or re.fullmatch(r'[A-Za-z0-9_-]{1,128}', worker_id) is None:
        raise ValueError('Invalid remote worker identity')
    # Remote request keys must remain unchanged over restarts and across workers.
    request_id = hashlib.sha256(('mta-remote-v1:' + local_job_id).encode('ascii')).hexdigest()
    keys = active_keyring()
    if not keys:
        raise ValueError('No trusted remote metering signing keys configured')
    sink = durable_remote_sink(local_job_id, request_id=request_id, worker_id=worker_id)
    return infer_audio(base_url, token, operation, wav, options,
                       timeout_seconds=timeout_seconds, request_id=request_id,
                       recover_on_failure=True, require_attestation=True,
                       metering_sink=sink, metering_keyring=keys, **({"cancel_event": cancel_event} if cancel_event is not None else {}))


def infer_and_register_remote_settlement(local_job_id, *, base_url, token, wav,
                                         worker_id, options=None, timeout_seconds=900, cancel_event=None):
    """Run/replay trusted remote inference and persist its billing intent.

    Remote output is not returned until its signed CPU evidence has been captured
    and the corresponding billing intent has been made durable. This function
    deliberately does not mark the project audio published; the caller must
    stage/publish the returned WAV through ai_publish_outbox separately.
    """
    result = infer_durable_remote(
        local_job_id, base_url=base_url, token=token, wav=wav,
        worker_id=worker_id, options=options, timeout_seconds=timeout_seconds,
        **({"cancel_event": cancel_event} if cancel_event is not None else {}))
    if cancel_event is not None and cancel_event.is_set():
        raise RuntimeError("Remote AI cancelled before billing settlement")
    if not isinstance(result, tuple) or len(result) != 3:
        raise ValueError('Invalid verified remote inference result')
    payload, mime, remote_job_id = result
    if mime != 'audio/wav' or not isinstance(payload, bytes) or not payload:
        raise ValueError('Durable Arranger/Remix requires a nonempty WAV output')
    if not isinstance(remote_job_id, str) or not remote_job_id:
        raise ValueError('Missing remote job identity')
    # Fail closed for opted-in jobs that lack trusted CPU evidence. Replays
    # reuse the immutable intent and never create a second ledger charge.
    register_settlement(local_job_id)
    return result
