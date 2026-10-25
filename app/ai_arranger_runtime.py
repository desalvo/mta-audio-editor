"""SQLite-coordinated web inference queue (POSIX server).

Cross-process admissions and FIFO ordering are transactional. Pending work is
persisted and resumable queued requests can be reconstructed by a registered
adapter. Running work is never automatically replayed after process death,
because its external side effects may already have happened.
"""
from __future__ import annotations
import json
import re
import os
from pathlib import Path
import sqlite3
import sys
import tempfile
import threading
import time
import uuid

# Server installations keep the queue under persistent data storage.
# Native single-user desktop installations retain a user-writable local default.
_DEFAULT_ROOT = (Path(tempfile.gettempdir()) / 'mta-ai-arranger-runtime'
                 if os.environ.get('MTA_NATIVE_SINGLE_USER', '').lower() in ('1', 'true', 'yes')
                 else Path('/var/lib/mta/ai-jobs'))
_ROOT = Path(os.environ.get('MTA_AI_JOB_STATE_DIR', str(_DEFAULT_ROOT)))
_MUTEX = threading.RLock()
_LOCAL: dict[str, threading.Event] = {}
_CANCELLABLE: set[str] = set()
_RESTORERS = {}  # operation -> payload-to-executor factory
_SAFE_JOB_ID = re.compile(r"[A-Za-z0-9_-]{1,160}\Z")


def _validate_job_id(job_id):
    if not isinstance(job_id, str) or not _SAFE_JOB_ID.fullmatch(job_id):
        raise ValueError("Invalid AI job identifier")
    return job_id

_SCHEMA = '''CREATE TABLE IF NOT EXISTS jobs (
 job_id TEXT PRIMARY KEY, project_id TEXT NOT NULL, operation TEXT NOT NULL,
 state TEXT NOT NULL, rank INTEGER NOT NULL, created_at REAL NOT NULL,
 started_at REAL, completed_at REAL, phase TEXT NOT NULL, message TEXT NOT NULL,
 progress_percent REAL, cancel_requested INTEGER NOT NULL DEFAULT 0,
 cpu_seconds REAL, gpu_seconds REAL, runner_pid INTEGER,
 runner_identity TEXT
)'''


def _db():
    _ROOT.mkdir(parents=True, mode=0o700, exist_ok=True)
    os.chmod(_ROOT, 0o700)
    con = sqlite3.connect(str(_ROOT / 'jobs.sqlite3'), timeout=30, isolation_level=None)
    con.row_factory = sqlite3.Row
    con.execute('PRAGMA busy_timeout=30000')
    con.execute('PRAGMA journal_mode=WAL')
    con.execute(_SCHEMA)
    columns = {row[1] for row in con.execute('PRAGMA table_info(jobs)')}
    for column, sqltype in (('actor_user_id', 'INTEGER'), ('runner_identity', 'TEXT'), ('payload_json', 'TEXT'), ('idempotency_key', 'TEXT'), ('gpu_seconds_estimated', 'REAL'), ('cpu_seconds_estimated', 'REAL'), ('gpu_metrics_status', 'TEXT'), ('gpu_metrics_source', 'TEXT'), ('progress_source', 'TEXT'), ('progress_estimated', 'INTEGER'), ('steps_completed', 'INTEGER'), ('steps_total', 'INTEGER')):
        if column not in columns:
            try:
                con.execute(f'ALTER TABLE jobs ADD COLUMN {column} {sqltype}')
            except sqlite3.OperationalError as exc:
                # A concurrent opener may have completed the same migration.
                # Suppress only that exact harmless race; preserve other errors.
                if 'duplicate column name' not in str(exc).lower():
                    raise
    con.execute('CREATE UNIQUE INDEX IF NOT EXISTS jobs_idempotency_key_unique ON jobs(idempotency_key) WHERE idempotency_key IS NOT NULL')
    con.execute('CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY,value TEXT NOT NULL)')
    # Audit/outbox share the same SQLite transaction as the terminal queue state.
    # Each job has at most one terminal receipt; consumers must use job_id as
    # their own idempotency key when crossing an external billing database.
    con.execute('''CREATE TABLE IF NOT EXISTS terminal_receipts (
        job_id TEXT PRIMARY KEY REFERENCES jobs(job_id),
        state TEXT NOT NULL CHECK(state IN ('completed','failed','cancelled','interrupted')),
        committed_at REAL NOT NULL
    )''')
    # SQLite creates journal sidecars on demand. Restrict the DB and existing
    # sidecars without changing process-wide umask or relying on installer ACLs.
    for suffix in ('', '-wal', '-shm'):
        candidate = _ROOT / ('jobs.sqlite3' + suffix)
        if candidate.exists() and not candidate.is_symlink():
            os.chmod(candidate, 0o600)
    return con


def _limit():
    with _db() as con:
        value = con.execute("SELECT value FROM settings WHERE key='max_concurrent_jobs'").fetchone()
    try:
        return max(1, min(32, int(value[0] if value else os.environ.get('MTA_AI_MAX_CONCURRENT_JOBS', '1'))))
    except ValueError:
        return 1


def configure(limit):
    if isinstance(limit, bool) or str(limit).strip() != str(int(limit)):
        raise ValueError('Concurrent AI jobs must be an integer')
    value = int(limit)
    if not 1 <= value <= 32:
        raise ValueError('Concurrent AI jobs must be between 1 and 32')
    with _db() as con:
        con.execute("INSERT INTO settings(key,value) VALUES('max_concurrent_jobs',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (str(value),))
    return value


def artifact_limit_mib():
    from .ai_payload_limits import validate_artifact_mib
    with _db() as con:
        row = con.execute("SELECT value FROM settings WHERE key='max_artifact_mib'").fetchone()
    # A corrupt persisted policy must fail closed, not silently grant more space.
    return validate_artifact_mib(int(row[0])) if row else 1024


def configure_execution_settings(body):
    """Validate all fields before one atomic update; old concurrency-only PUTs work."""
    from .ai_payload_limits import validate_artifact_mib
    if not isinstance(body, dict) or not body or set(body) - {'max_concurrent_jobs', 'max_artifact_mib'}:
        raise ValueError('Unsupported AI execution setting')
    updates = {}
    if 'max_concurrent_jobs' in body:
        value = body['max_concurrent_jobs']
        if type(value) is not int or not 1 <= value <= 32:
            raise ValueError('Concurrent AI jobs must be an integer from 1 to 32')
        updates['max_concurrent_jobs'] = value
    if 'max_artifact_mib' in body:
        updates['max_artifact_mib'] = validate_artifact_mib(body['max_artifact_mib'])
    with _db() as con:
        con.execute('BEGIN IMMEDIATE')
        con.executemany('INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value',
                        [(key, str(value)) for key, value in updates.items()])
    return {'max_concurrent_jobs': _limit(), 'max_artifact_mib': artifact_limit_mib()}


def _process_identity(pid):
    """Linux boot ID and process start tick; prevent PID-reuse false positives.

    None means confirmed absent/exited; '' means unavailable, never dead.
    Windows uses a query-only process creation identity; other OSes use PID checks.
    """
    if type(pid) is not int or pid <= 0:
        return ''
    if sys.platform == 'win32':
        from .windows_process_identity import process_identity
        return process_identity(pid)
    try:
        boot = Path('/proc/sys/kernel/random/boot_id').read_text().strip()
        if not boot:
            return ''
    except (OSError, ValueError):
        return ''
    try:
        from .linux_proc_view import directory
        process = directory(pid)
        if process is None:
            raise FileNotFoundError('Namespace-local process is not visible')
        stat = (process / 'stat').read_text()
        # Field 2 (comm) may contain spaces or parentheses.
        fields = stat.rsplit(')', 1)[1].split()
        if fields[0] in ('Z', 'X', 'x'):
            return None
        if not fields[19].isdigit() or int(fields[19]) <= 0:
            return ''
        return f'{boot}:{fields[19]}'  # field 22 (starttime)
    except (FileNotFoundError, ProcessLookupError):
        # hidepid/proc mount restrictions can conceal a process which is
        # still alive. Only ESRCH from the kernel proves absence here.
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return None
        except OSError:
            pass
        return ''
    except (OSError, ValueError, IndexError):
        return ''


def _recover_dead_runners(con):
    """Mark orphaned jobs interrupted, never replay side-effecting callables.

    A stored PID is not enough: Linux may reuse it between invocations.
    """
    con.execute("UPDATE jobs SET state='interrupted',phase='interrupted',completed_at=?,message='Remote admission cannot be replayed' WHERE state='queued' AND runner_pid IS NULL AND operation LIKE 'worker:%'",(time.time(),))
    rows = con.execute("SELECT job_id,runner_pid,runner_identity,state FROM jobs WHERE state IN ('queued','running')").fetchall()
    for jid, pid, identity, state in rows:
        if not pid:
            continue
        dead = False
        if identity:
            current = _process_identity(pid)
            dead = current != '' and current != identity
        elif sys.platform == 'win32':
            dead = _process_identity(pid) is None
        else:
            try:
                os.kill(int(pid), 0)
            except ProcessLookupError:
                dead = True
            except PermissionError:
                pass
        if dead and state == 'running':
            stamp = time.time()
            changed = con.execute("UPDATE jobs SET state='interrupted',phase='interrupted',completed_at=?,message='Execution interrupted; review before retry to avoid duplicate output' WHERE job_id=? AND state='running'", (stamp, jid))
            if changed.rowcount:
                con.execute("INSERT OR IGNORE INTO terminal_receipts(job_id,state,committed_at) VALUES(?,?,?)", (jid, 'interrupted', stamp))
        elif dead and state == 'queued':
            operation=con.execute('SELECT operation FROM jobs WHERE job_id=?',(jid,)).fetchone()[0]
            if operation.startswith('worker:'):
                stamp=time.time()
                con.execute("UPDATE jobs SET state='interrupted',phase='interrupted',completed_at=?,message='Remote admission owner exited; request will not be replayed' WHERE job_id=?",(stamp,jid))
                con.execute("INSERT OR IGNORE INTO terminal_receipts VALUES(?,?,?)",(jid,'interrupted',stamp))
                continue
            # Only the scheduler's admission owner has exited; no work ran.
            con.execute("UPDATE jobs SET runner_pid=NULL,runner_identity=NULL,message='Waiting for scheduler recovery' WHERE job_id=? AND state='queued'", (jid,))


def _rows(con):
    rows = [dict(row) for row in con.execute('SELECT * FROM jobs ORDER BY rank, created_at')]
    queue = [r for r in rows if r['state'] == 'queued']
    for idx, job in enumerate(queue):
        job['queue_position'] = idx + 1
        job['jobs_ahead'] = idx
    return rows


def _public(con, job):
    row = dict(job)
    if row['state'] == 'queued':
        earlier = con.execute("SELECT COUNT(*) FROM jobs WHERE state='queued' AND (rank < ? OR (rank = ? AND created_at < ?))", (row['rank'], row['rank'], row['created_at'])).fetchone()[0]
        row.update(queue_position=earlier + 1, jobs_ahead=earlier)
    else:
        row.update(queue_position=None, jobs_ahead=0)
    row['cancel_requested'] = bool(row['cancel_requested'])
    # Arguments can contain private user content; only a trusted worker reads them.
    if row.get('actor_user_id') is None:
        try:
            row['actor_user_id'] = json.loads(row.get('payload_json') or '{}').get('actor_user_id')
        except (ValueError, AttributeError):
            pass
    row.pop('payload_json', None)
    row.pop('idempotency_key', None)
    now = time.time()
    row['elapsed_seconds'] = max(0.0, (row['completed_at'] or now) - row['started_at']) if row['started_at'] else 0.0
    from .ai_queue_usage import enrich
    return enrich(row)


def _gpu_metadata(payload):
    from .ace_gpu_process_meter import GPU_STATUSES, GPU_SOURCES
    return {key: payload[key] for key, allowed in (
        ('gpu_metrics_status', GPU_STATUSES), ('gpu_metrics_source', GPU_SOURCES))
        if isinstance(payload.get(key), str) and payload[key] in allowed}


def _with_live_progress(row):
    """Expose trustworthy backend progress on both client and admin endpoints.

    The progress sidecar contains backend measurements, never wall-clock
    approximations of GPU time or a fabricated percentage.
    """
    value = dict(row)
    if value.get('state') != 'running':
        return value
    try:
        path = _ROOT / (_validate_job_id(value['job_id']) + '.progress.json')
        payload = json.loads(path.read_text(encoding='utf-8'))
        if not isinstance(payload, dict):
            return value
        for field, maximum in (('phase', 80), ('message', 240)):
            if isinstance(payload.get(field), str):
                value[field] = payload[field][:maximum]
        pct = payload.get('progress_percent')
        if isinstance(pct, (int, float)) and not isinstance(pct, bool) and 0 <= pct <= 100:
            value['progress_percent'] = float(pct)
        if payload.get('progress_source') in ('ace-stage-estimate', 'ace-dit-evaluations','studio-sources'):
            value['progress_source'] = payload['progress_source']
            value['progress_estimated'] = payload.get('progress_source')!='studio-sources'
            for key in ('steps_completed', 'steps_total'):
                if type(payload.get(key)) is int and 0 <= payload[key] <= 1000:
                    value[key] = payload[key]
        value.update(_gpu_metadata(payload))
        for field in ('cpu_seconds', 'gpu_seconds', 'cpu_seconds_estimated', 'gpu_seconds_estimated'):
            # The ledger projection can include earlier stages of this job.
            # A sidecar describes only the current worker, so must not replace
            # an already aggregated partial estimate.
            if field.endswith('_estimated') and value.get('resource_metrics_partial') and value.get(field) is not None:
                continue
            amount = payload.get(field)
            if isinstance(amount, (int, float)) and not isinstance(amount, bool) and 0 <= amount < float('inf'):
                value[field] = float(amount)
    except (OSError, ValueError, TypeError):
        pass
    if value.get('cancel_requested'):
        value.update(phase='cancelling', message='Cancellation requested; discarding output and stopping ACE cooperatively')
    return value


def list_jobs(limit=100):
    with _db() as con:
        _recover_dead_runners(con)
        return [_with_live_progress(_public(con, row)) for row in con.execute('SELECT * FROM jobs ORDER BY created_at DESC LIMIT ?', (max(1, min(int(limit), 500)),))]


def get(job_id):
    with _db() as con:
        _recover_dead_runners(con)
        row = con.execute('SELECT * FROM jobs WHERE job_id=?', (job_id,)).fetchone()
        return _with_live_progress(_public(con, row)) if row else None


def job_operation(job_id):
    """Read the immutable scheduler operation for admission validation."""
    _validate_job_id(job_id)
    with _db() as con:
        row = con.execute('SELECT operation FROM jobs WHERE job_id=?', (job_id,)).fetchone()
    return row[0] if row else None


def _claim(job_id):
    # A second web process can recover an admitted-but-not-yet-provisioned
    # request before the original HTTP handler finishes its ledger transaction.
    # Never execute a billable durable job without its ledger identity.
    # Any persisted payload for audio inference is a durable admission attempt.
    # Malformed JSON/schema must never be mistaken for a legacy in-memory job.
    if durable_audio_job(job_id):
        try:
            payload = read_payload(job_id)
            if (not isinstance(payload, dict) or payload.get('schema_version') != 1
                    or ('actor_user_id' in payload and
                        (type(payload['actor_user_id']) is not int or payload['actor_user_id'] <= 0))
                    or ('adapter' in payload and payload['adapter'] != job_operation(job_id))):
                raise ValueError('Invalid durable audio identity or schema')
        except (ValueError, TypeError, KeyError, json.JSONDecodeError):
            with _db() as con:
                con.execute("UPDATE jobs SET state='blocked',phase='blocked',message='Invalid durable audio admission' WHERE job_id=? AND state='queued'", (job_id,))
            return False
    else:
        payload = None
    if isinstance(payload, dict) and type(payload.get('actor_user_id')) is int:
        try:
            from . import ai_metering_bridge, ai_billing
            user_id, operation = ai_metering_bridge._identity(job_id)
            if (ai_billing.user_billing_enabled(user_id)
                    and ai_billing.existing_inference_ledger_job(job_id, user_id, operation) is None):
                with _db() as con:
                    con.execute("UPDATE jobs SET state='blocked',phase='blocked',message='Ledger admission needs reconciliation' WHERE job_id=? AND state='queued'", (job_id,))
                return False
        except Exception:
            # DB unavailable or malformed immutable identity: fail closed.
            with _db() as con:
                con.execute("UPDATE jobs SET state='blocked',phase='blocked',message='Ledger admission needs reconciliation' WHERE job_id=? AND state='queued'", (job_id,))
            return False
    with _db() as con:
        con.execute('BEGIN IMMEDIATE')
        _recover_dead_runners(con)
        row = con.execute('SELECT * FROM jobs WHERE job_id=?', (job_id,)).fetchone()
        first = con.execute("SELECT job_id FROM jobs WHERE state='queued' ORDER BY rank,created_at LIMIT 1").fetchone()
        running = con.execute("SELECT COUNT(*) FROM jobs WHERE state='running'").fetchone()[0]
        if not row or row['state'] != 'queued' or not first or first[0] != job_id or running >= _limit():
            con.execute('COMMIT')
            return False
        identity = _process_identity(os.getpid())
        if not identity and sys.platform in ('linux', 'win32'):
            con.execute("UPDATE jobs SET message='Waiting for verifiable scheduler identity' WHERE job_id=?", (job_id,))
            con.execute('COMMIT')
            return False
        con.execute("UPDATE jobs SET state='running', started_at=?, phase='preparing',message='Preparing source audio',runner_pid=?,runner_identity=? WHERE job_id=?", (time.time(), os.getpid(), identity, job_id))
        con.execute('COMMIT')
        return True


def register_restorer(operation, factory):
    """Register a trusted local factory accepting (project_id, payload, job_id).

    Only queued jobs are eligible for automatic restoration, never interrupted
    executions whose external effects cannot be atomically rolled back.
    """
    if not operation or not callable(factory):
        raise ValueError('Invalid AI restorer')
    _RESTORERS[operation] = factory


def recover_queued():
    """Resume only durable *unstarted* requests with registered adapters.

    Multiple web server processes may recover the same row; SQLite _claim
    enforces single execution. Jobs lacking sufficient payload remain queued
    with an explicit explanation instead of silently losing work.
    """
    with _db() as con:
        con.execute('BEGIN IMMEDIATE')
        _recover_dead_runners(con)
        rows = con.execute("SELECT job_id,project_id,operation,payload_json FROM jobs WHERE state IN ('queued','blocked') AND NOT (state='blocked' AND message='Ledger admission needs reconciliation') ORDER BY rank,created_at").fetchall()
        con.execute('COMMIT')
    recovered = 0
    for jid, pid, operation, encoded in rows:
        if not encoded or operation not in _RESTORERS:
            # Do not let a request without a restorable adapter occupy the
            # head of a FIFO queue indefinitely. It remains durable and can
            # be retried by recovery when an adapter is installed.
            with _db() as con:
                con.execute("UPDATE jobs SET state='blocked',phase='blocked',message='Waiting for compatible persistent AI adapter',runner_pid=NULL,runner_identity=NULL WHERE job_id=? AND state IN ('queued','blocked')", (jid,))
            continue
        with _MUTEX:
            if jid in _LOCAL:
                continue
        try:
            payload = json.loads(encoded)
            fn = _RESTORERS[operation](pid, payload, jid)
            if not callable(fn):
                raise TypeError('AI adapter returned no executor')
        except Exception:
            with _db() as con:
                con.execute("UPDATE jobs SET state='blocked',phase='blocked',message='Stored job payload incompatible with adapter; administrator review required',runner_pid=NULL,runner_identity=NULL WHERE job_id=? AND state IN ('queued','blocked')", (jid,))
            continue
        with _db() as con:
            con.execute("UPDATE jobs SET state='queued',phase='queued',message='Restored durable request; waiting for inference slot' WHERE job_id=? AND state='blocked'", (jid,))
        if _spawn(jid, fn, cancellable=True):
            recovered += 1
    return recovered



def durable_audio_job(job_id):
    """Apply the finalization gate to durable Arranger/Remix requests only.

    Legacy in-memory jobs remain compatible; they cannot be replayed after a
    crash and must not be confused with durable audio publishing operations.
    """
    _validate_job_id(job_id)
    with _db() as con:
        row = con.execute('SELECT operation,payload_json FROM jobs WHERE job_id=?', (job_id,)).fetchone()
    if not row or row[0] not in ('arranger', 'remix') or not row[1]:
        return False
    # Nonempty persisted audio payloads must pass durable finalization gates,
    # including corrupt entries; only truly in-memory jobs are legacy.
    return True


def _spawn(job_id, fn, *, cancellable=False):
    _validate_job_id(job_id)
    with _MUTEX:
        if job_id in _LOCAL:
            return False
        stop = threading.Event()
        _LOCAL[job_id] = stop
        if cancellable:
            _CANCELLABLE.add(job_id)

    def execute():
        progress = _ROOT / (job_id + '.progress.json')
        try:
            while not stop.wait(0.4):
                current = get(job_id)
                if not current or current['state'] != 'queued':
                    return
                if _claim(job_id):
                    break
            else:
                return
            try:
                from .deferred_execution_owner import execution_scope
                with execution_scope(job_id,stop):
                    from .ai_global_execution import current_job,current_cancel
                    context_token=current_job.set(job_id)
                    cancel_token=current_cancel.set(stop)
                    try:
                        if cancellable:
                            fn(progress, stop)
                        else:
                            fn(progress)
                    finally:
                        current_job.reset(context_token)
                        current_cancel.reset(cancel_token)
                    state, message = 'completed', ('AI processing complete; remote result ready' if current['operation'].startswith('worker:') else 'Generated track added to project')
                    # A normal return is not a durable commit. For audio-generating
                    # adapters require the publication receipt and (when explicitly
                    # associated) the ledger acknowledgement before completion.
                    if durable_audio_job(job_id):
                        from . import ai_metering_bridge
                        try:
                            if (read_payload(job_id) or {}).get('actor_user_id') is not None:
                                ai_metering_bridge.register_settlement(job_id)
                        except Exception:
                            # The audio can be published, but without verified usage
                            # a billable job must never be announced completed.
                            state, message = 'interrupted', 'Billing finalization pending verified metering'
                        from . import ai_finalization
                        evidence = ai_finalization.readiness(job_id)
                        if evidence['publication'] == 'published' and evidence['billing'] == 'pending':
                            try:
                                from . import ai_billing_outbox
                                ai_billing_outbox.deliver(job_id=job_id)
                            except Exception:
                                # The durable outbox keeps the pending settlement for recovery.
                                # A missing acknowledgement is handled by readiness() below.
                                state, message = 'interrupted', 'Billing outbox delivery pending recovery'
                            evidence = ai_finalization.readiness(job_id)
                        if not evidence['ready']:
                            state, message = 'interrupted', 'Publication or billing awaits durable recovery'
            except Exception as exc:
                state, message = ('cancelled', 'Cancelled during inference') if stop.is_set() else ('failed', str(exc)[:500])
            # Capture genuine backend counters before deleting the progress
            # sidecar. These numbers are measurements provided by the trusted
            # worker, never derived from wall time. Missing metrics remain NULL.
            final_usage = {}
            progress_metadata = _with_live_progress({'job_id': job_id, 'state': 'running'})
            gpu_metadata = {}
            try:
                import math
                payload = json.loads(progress.read_text(encoding='utf-8'))
                if isinstance(payload, dict):
                    gpu_metadata = _gpu_metadata(payload)
                    for metric in ('cpu_seconds', 'gpu_seconds', 'cpu_seconds_estimated', 'gpu_seconds_estimated'):
                        value = payload.get(metric)
                        if (isinstance(value, (int, float)) and not isinstance(value, bool)
                                and math.isfinite(value) and value >= 0):
                            final_usage[metric] = float(value)
            except (OSError, ValueError, TypeError):
                pass
            with _db() as con:
                con.execute('BEGIN IMMEDIATE')
                cancelled_row = con.execute('SELECT cancel_requested FROM jobs WHERE job_id=?', (job_id,)).fetchone()
                if cancelled_row is None:
                    con.execute('ROLLBACK')
                    return
                if cancelled_row[0]:
                    state, message = 'cancelled', 'Job cancelled; worker exited and output discarded'
                stamp = time.time()
                identity = _process_identity(os.getpid())
                if not identity and sys.platform in ('linux', 'win32'):
                    con.execute('ROLLBACK')
                    return  # Unknown ownership cannot authorize a terminal receipt.
                changed = con.execute("UPDATE jobs SET state=?,phase=?,message=?,completed_at=?,progress_percent=? WHERE job_id=? AND state='running' AND runner_pid=? AND runner_identity IS ?", (state, state, message, stamp, 100 if state == 'completed' else None, job_id, os.getpid(), identity))
                if changed.rowcount:
                    con.execute('UPDATE jobs SET progress_source=?,progress_estimated=?,steps_completed=?,steps_total=? WHERE job_id=?', (progress_metadata.get('progress_source'), progress_metadata.get('progress_estimated'), progress_metadata.get('steps_completed'), progress_metadata.get('steps_total'), job_id))
                    if gpu_metadata:
                        con.execute('UPDATE jobs SET gpu_metrics_status=?,gpu_metrics_source=? WHERE job_id=?',
                                    (gpu_metadata.get('gpu_metrics_status'), gpu_metadata.get('gpu_metrics_source'), job_id))
                    if final_usage:
                        con.execute('UPDATE jobs SET cpu_seconds=COALESCE(cpu_seconds,?), gpu_seconds=COALESCE(gpu_seconds,?), cpu_seconds_estimated=COALESCE(cpu_seconds_estimated,?), gpu_seconds_estimated=COALESCE(gpu_seconds_estimated,?) WHERE job_id=?',
                                    (final_usage.get('cpu_seconds'), final_usage.get('gpu_seconds'), final_usage.get('cpu_seconds_estimated'), final_usage.get('gpu_seconds_estimated'), job_id))
                    con.execute("INSERT OR IGNORE INTO terminal_receipts(job_id,state,committed_at) VALUES(?,?,?)", (job_id, state, stamp))
                con.execute('COMMIT')
        finally:
            progress.unlink(missing_ok=True)
            with _MUTEX:
                _LOCAL.pop(job_id, None)
                _CANCELLABLE.discard(job_id)

    threading.Thread(target=execute, daemon=True, name='mta-ai-job-' + job_id[:8]).start()
    return True


def start(pid, operation, fn, *, job_id=None, cancellable=False, payload=None, idempotency_key=None, defer_spawn=False):
    """Submit a real job. Return (accepted, job). Never silently discard queued work."""
    job_id = _validate_job_id(job_id if job_id is not None else uuid.uuid4().hex)
    # Persist only JSON-compatible requests; never serialize closures or credentials.
    encoded = json.dumps(payload, allow_nan=False, sort_keys=True) if payload is not None else None
    if encoded is not None and len(encoded.encode('utf-8')) > 1024 * 1024:
        raise ValueError('AI payload exceeds 1 MiB')
    if idempotency_key is not None and (not isinstance(idempotency_key, str) or not 1 <= len(idempotency_key) <= 160):
        raise ValueError('Invalid AI idempotency key')
    with _db() as con:
        con.execute('BEGIN IMMEDIATE')
        existing = con.execute('SELECT job_id,project_id,operation,payload_json FROM jobs WHERE job_id=? OR (idempotency_key IS NOT NULL AND idempotency_key=?)', (job_id, idempotency_key)).fetchone()
        if existing:
            if (existing['project_id'], existing['operation'], existing['payload_json']) != (str(pid), operation, encoded):
                con.execute('ROLLBACK')
                raise ValueError('Conflicting replay of AI job identifier')
            con.execute('COMMIT')
            return False, get(existing['job_id'])
        from .ai_job_context import actor
        owner=payload.get('actor_user_id',actor.get()) if isinstance(payload,dict) else actor.get()
        from .resource_access import preflight
        from .model_license_policy import FREE_ADMISSION
        if not FREE_ADMISSION.get():preflight(owner)
        rank = con.execute('SELECT COALESCE(MAX(rank),0)+1 FROM jobs').fetchone()[0]
        con.execute("INSERT INTO jobs(job_id,project_id,operation,state,rank,created_at,phase,message,runner_pid,runner_identity,payload_json,idempotency_key) VALUES(?,?,?,'queued',?,?,'queued','Waiting for inference slot',?,?,?,?)", (job_id, str(pid), operation, rank, time.time(), os.getpid(), _process_identity(os.getpid()), encoded, idempotency_key))
        from .ai_job_context import actor
        owner = payload.get('actor_user_id',actor.get()) if isinstance(payload,dict) else actor.get()
        if type(owner) is int and owner>0:con.execute('UPDATE jobs SET actor_user_id=? WHERE job_id=?',(owner,job_id))
        con.execute('COMMIT')
    if not defer_spawn:
        _spawn(job_id, fn, cancellable=cancellable)
    return True, get(job_id)


def activate(job_id, fn, *, cancellable=True):
    """Start a previously admitted job after external admission is reconciled."""
    _validate_job_id(job_id)
    with _db() as con:
        row = con.execute('SELECT state,payload_json FROM jobs WHERE job_id=?', (job_id,)).fetchone()
    if not row or row['state'] != 'queued' or not row['payload_json']:
        return False
    return _spawn(job_id, fn, cancellable=cancellable)


def cancel(job_id):
    with _db() as con:
        con.execute('BEGIN IMMEDIATE')
        row = con.execute('SELECT state,phase FROM jobs WHERE job_id=?', (job_id,)).fetchone()
        if not row:
            con.execute('ROLLBACK')
            return None
        if row[0] in ('queued', 'blocked'):
            stamp = time.time()
            changed = con.execute("UPDATE jobs SET state='cancelled',phase='cancelled',completed_at=?,message='Cancelled before execution' WHERE job_id=? AND state IN ('queued','blocked')", (stamp, job_id))
            if changed.rowcount:
                con.execute("INSERT OR IGNORE INTO terminal_receipts(job_id,state,committed_at) VALUES(?,?,?)", (job_id, 'cancelled', stamp))
        elif row[0] == 'running':
            if row[1]=='studio-committing':
                con.execute('ROLLBACK');raise ValueError('Atomic result publication has started; wait for completion')
            with _MUTEX:
                event = _LOCAL.get(job_id)
                cancellable = job_id in _CANCELLABLE
            if event is None or not cancellable:
                con.execute('ROLLBACK')
                raise ValueError('This running worker does not support confirmed cancellation')
            con.execute("UPDATE jobs SET cancel_requested=1,phase='cancelling',message='Terminating inference subprocess' WHERE job_id=?", (job_id,))
            event.set()
        con.execute('COMMIT')
    with _MUTEX:
        if job_id in _LOCAL and row[0] in ('queued', 'blocked'):
            _LOCAL[job_id].set()
    from .resource_accounts import reconcile_cancelled_reservations
    reconcile_cancelled_reservations(job_id)
    return get(job_id)


def move(job_id, position):
    with _db() as con:
        con.execute('BEGIN IMMEDIATE')
        queued = [r[0] for r in con.execute("SELECT job_id FROM jobs WHERE state='queued' ORDER BY rank,created_at")]
        if job_id not in queued:
            con.execute('ROLLBACK')
            raise ValueError('Only queued jobs can be reordered')
        queued.remove(job_id)
        if not 1 <= int(position) <= len(queued) + 1:
            con.execute('ROLLBACK')
            raise ValueError('Queue position out of range')
        queued.insert(int(position) - 1, job_id)
        for i, jid in enumerate(queued):
            con.execute('UPDATE jobs SET rank=? WHERE job_id=?', (i + 1, jid))
        con.execute('COMMIT')
    return get(job_id)


def inspect(pid):
    # Historical route: show the project's newest active job (including waiting).
    with _db() as con:
        _recover_dead_runners(con)
        row = con.execute("SELECT * FROM jobs WHERE project_id=? AND state IN ('running','queued','blocked') ORDER BY created_at DESC LIMIT 1", (str(pid),)).fetchone()
        if row is None:
            row = con.execute('SELECT * FROM jobs WHERE project_id=? ORDER BY created_at DESC LIMIT 1', (str(pid),)).fetchone()
        if not row:
            return {'state': 'idle'}
        value = _public(con, row)
    return _with_live_progress(value)


def read_payload(job_id):
    """Internal worker-only interface; never expose this through public job APIs."""
    with _db() as con:
        row = con.execute('SELECT payload_json FROM jobs WHERE job_id=?', (job_id,)).fetchone()
        return json.loads(row[0]) if row and row[0] is not None else None



def terminal_receipt(job_id):
    """Internal durable terminal outcome for idempotent downstream consumers.

    This is an outbox receipt, not proof that a different DB has committed an
    accounting charge. Never expose it as a billing settlement certificate.
    """
    _validate_job_id(job_id)
    with _db() as con:
        row = con.execute('SELECT job_id,state,committed_at FROM terminal_receipts WHERE job_id=?', (job_id,)).fetchone()
        return dict(row) if row else None


def reconcile_published_audio(job_id):
    """Finish a crash-interrupted inference whose durable audio was published.

    Only the independent publication outbox may call this after verifying the
    exact staged checksum and project publication. A cancelled job stays cancelled.
    """
    _validate_job_id(job_id)
    # Never recover a billable publication to completed before the ledger
    # confirms its explicit settlement.  A nonbillable job has no delivery.
    from . import ai_billing_outbox
    settlement = ai_billing_outbox.inspect(job_id)
    from . import ai_metering_bridge
    if (settlement is None and ai_metering_bridge.billing_required(job_id)) or (settlement is not None and settlement['state'] != 'delivered'):
        return False
    with _db() as con:
        con.execute('BEGIN IMMEDIATE')
        _recover_dead_runners(con)
        row = con.execute('SELECT state,cancel_requested FROM jobs WHERE job_id=?', (job_id,)).fetchone()
        if row is None or row['cancel_requested'] or row['state'] not in ('interrupted', 'completed'):
            con.execute('COMMIT')
            return False
        if row['state'] == 'completed':
            con.execute('COMMIT')
            return True
        stamp = time.time()
        con.execute("UPDATE jobs SET state='completed',phase='completed',completed_at=?,progress_percent=100,message='Recovered durable audio publication' WHERE job_id=? AND state='interrupted'", (stamp, job_id))
        con.execute("UPDATE terminal_receipts SET state='completed',committed_at=? WHERE job_id=? AND state='interrupted'", (stamp, job_id))
        con.execute("INSERT OR IGNORE INTO terminal_receipts(job_id,state,committed_at) VALUES(?, 'completed',?)", (job_id, stamp))
        con.execute('COMMIT')
        return True
