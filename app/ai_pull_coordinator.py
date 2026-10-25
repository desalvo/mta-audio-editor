"""Single-authority pull execution. Workers never open the ledger SQLite file.

Inputs, assignments and frozen outputs share the economic admission transaction.
There is no expiry/takeover, automatic inference retry, multi-leader or HA mode.
"""
from contextlib import contextmanager
from dataclasses import asdict
import base64
import hashlib
import hmac
import io
import json
import math
import os
import re
import secrets
import sqlite3
import tempfile
import time
from pathlib import Path
import zipfile

from . import auth, ai_billing
from .regime_operation_fence import FenceBlocked

MAX_BYTES = 16 * 1024 * 1024
MAX_STORED = 128 * 1024 * 1024
RETENTION_SECONDS = 7 * 86400
HEX = re.compile(r'[a-f0-9]{32}')
SCHEMA = [
    '''CREATE TABLE IF NOT EXISTS ai_pull_state(singleton INTEGER PRIMARY KEY CHECK(singleton=1),
       accepting INTEGER NOT NULL CHECK(accepting IN(0,1)),generation INTEGER NOT NULL,authority_binding TEXT NOT NULL)''',
    '''CREATE TABLE IF NOT EXISTS ai_pull_operator_audit(id TEXT PRIMARY KEY,actor_id INTEGER,
       action TEXT NOT NULL,target TEXT NOT NULL,detail_json TEXT NOT NULL,created_at INTEGER NOT NULL)''',
    '''CREATE TABLE IF NOT EXISTS ai_pull_nodes(
       id TEXT PRIMARY KEY,key_hash TEXT NOT NULL,name TEXT NOT NULL,kinds_json TEXT NOT NULL,
       enabled INTEGER NOT NULL CHECK(enabled IN(0,1)),accepting INTEGER NOT NULL CHECK(accepting IN(0,1)))''',
    '''CREATE TABLE IF NOT EXISTS ai_pull_tasks(
       job_id TEXT PRIMARY KEY REFERENCES ai_compute_jobs(id) ON DELETE CASCADE,
       user_id INTEGER NOT NULL REFERENCES users(id),kind TEXT NOT NULL,plan_json TEXT NOT NULL,
       policy_json TEXT NOT NULL,source_kind TEXT NOT NULL,source_sha256 TEXT NOT NULL,source BLOB,
       deferred INTEGER NOT NULL,owner_json TEXT NOT NULL,timeout INTEGER NOT NULL,
       request_key TEXT,request_digest TEXT,metering_json TEXT,
       state TEXT NOT NULL CHECK(state IN('queued','dispatched','frozen','done')),
       node_id TEXT REFERENCES ai_pull_nodes(id),instance TEXT,nonce TEXT,
       cancelled INTEGER NOT NULL DEFAULT 0,completion_json TEXT,result BLOB,
       created_at INTEGER NOT NULL,completed_at INTEGER)''',
    "CREATE UNIQUE INDEX IF NOT EXISTS ai_pull_one_active_node ON ai_pull_tasks(node_id) WHERE state='dispatched'",
    'CREATE INDEX IF NOT EXISTS ai_pull_task_owner ON ai_pull_tasks(user_id)',
    '''CREATE TABLE IF NOT EXISTS ai_pull_deferred_admissions(job_id TEXT PRIMARY KEY
       REFERENCES ai_compute_jobs(id) ON DELETE CASCADE,generation INTEGER NOT NULL)''',
    'CREATE UNIQUE INDEX IF NOT EXISTS ai_pull_request_once ON ai_pull_tasks(user_id,request_key) WHERE request_key IS NOT NULL',
    '''CREATE TABLE IF NOT EXISTS ai_pull_publication_intents(job_id TEXT PRIMARY KEY
       REFERENCES ai_pull_tasks(job_id) ON DELETE CASCADE,inference_id TEXT NOT NULL UNIQUE,
       project_id TEXT NOT NULL,operation TEXT NOT NULL,input_source TEXT NOT NULL)''',
    '''CREATE TRIGGER IF NOT EXISTS ai_pull_publication_intent_immutable BEFORE UPDATE ON ai_pull_publication_intents
       BEGIN SELECT RAISE(ABORT,'Immutable pull publication intent'); END''',
    '''CREATE TABLE IF NOT EXISTS ai_pull_acknowledgements(
       receipt TEXT PRIMARY KEY,completion_sha256 TEXT NOT NULL,created_at INTEGER NOT NULL)''',
    '''CREATE TRIGGER IF NOT EXISTS ai_pull_admission_immutable BEFORE UPDATE ON ai_pull_tasks
       WHEN NEW.job_id IS NOT OLD.job_id OR NEW.user_id IS NOT OLD.user_id OR NEW.kind IS NOT OLD.kind
        OR NEW.plan_json IS NOT OLD.plan_json OR NEW.policy_json IS NOT OLD.policy_json
        OR NEW.source_kind IS NOT OLD.source_kind OR NEW.source_sha256 IS NOT OLD.source_sha256
        OR NEW.owner_json IS NOT OLD.owner_json OR NEW.deferred IS NOT OLD.deferred OR NEW.timeout IS NOT OLD.timeout
        OR NEW.request_key IS NOT OLD.request_key OR NEW.request_digest IS NOT OLD.request_digest
       BEGIN SELECT RAISE(ABORT,'Immutable pull admission'); END''',
    '''CREATE TRIGGER IF NOT EXISTS ai_pull_frozen_immutable BEFORE UPDATE ON ai_pull_tasks
       WHEN OLD.state IN('frozen','done') AND (NEW.completion_json IS NOT OLD.completion_json
        OR NEW.node_id IS NOT OLD.node_id OR NEW.instance IS NOT OLD.instance OR NEW.nonce IS NOT OLD.nonce)
       BEGIN SELECT RAISE(ABORT,'Immutable pull completion'); END''',
    '''CREATE TRIGGER IF NOT EXISTS ai_pull_payload_immutable BEFORE UPDATE ON ai_pull_tasks
       WHEN (NEW.source IS NOT OLD.source AND NOT (NEW.source IS NULL AND NEW.state IN('frozen','done')))
        OR (NEW.result IS NOT OLD.result AND NOT
          ((OLD.state='dispatched' AND NEW.state='frozen') OR (NEW.result IS NULL AND NEW.state='done')))
       BEGIN SELECT RAISE(ABORT,'Immutable pull payload'); END''',
    '''CREATE TRIGGER IF NOT EXISTS ai_pull_metering_immutable BEFORE UPDATE ON ai_pull_tasks
       WHEN OLD.metering_json IS NOT NULL AND NEW.metering_json IS NOT OLD.metering_json
       BEGIN SELECT RAISE(ABORT,'Immutable pull delivery evidence'); END''',
]


class PullPending(RuntimeError):
    def __init__(self, job_id):
        self.job_id = job_id
        super().__init__('Pull execution remains held; worker termination is not verified')

    def detail(self):
        from .i18n import current_language
        message = ('Esecuzione remota ancora in sospeso; arresto del worker non verificato' if current_language.get() == 'it'
                   else 'Remote execution remains pending; worker termination is not verified')
        return {'code': 'pull_execution_pending', 'job_id': self.job_id, 'message': message,
                'worker_stopped': False, 'execution_replayed': False}


def mode():
    value = os.getenv('MTA_AI_EXECUTION_MODE', 'local')
    if value not in ('local', 'pull'):
        raise ValueError('Invalid operator AI execution mode')
    return value


def encode(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)


def decode(raw):
    from .ai_remote_transport import _unique_pairs
    return json.loads(raw, object_pairs_hook=_unique_pairs,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError('Nonfinite JSON')))


def initialize(c):
    for statement in SCHEMA:
        c.execute(statement)
    binding = _authority_binding()
    c.execute('INSERT OR IGNORE INTO ai_pull_state VALUES(1,1,0,?)', (binding,))
    if c.execute('SELECT authority_binding FROM ai_pull_state WHERE singleton=1').fetchone()[0] != binding:
        raise FenceBlocked('Pull authority host/storage changed; offline recovery and worker quiescence required')


def _authority_binding():
    """No cloned/relocated database may silently become a second authority."""
    root = auth.data_root()
    info = root.stat()
    boot = Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    if not re.fullmatch(r'[a-f0-9-]{36}', boot):
        raise FenceBlocked('Verifiable Linux authority boot identity required')
    namespace = Path('/proc/self/ns/pid').stat().st_ino
    return hashlib.sha256(encode({'boot': boot, 'device': info.st_dev, 'inode': info.st_ino, 'pid_namespace': namespace}).encode()).hexdigest()


def _audit(c, actor, action, target, detail):
    if actor is not None:
        user = c.execute('SELECT role,active FROM users WHERE id=?', (actor,)).fetchone()
        if not user or tuple(user) != ('admin', 1):
            raise PermissionError('Active operator required')
    c.execute('INSERT INTO ai_pull_operator_audit VALUES(?,?,?,?,?,?)',
              (secrets.token_hex(16), actor, action, target, encode(detail), int(time.time())))


@contextmanager
def transaction():
    with auth.db() as c:
        c.execute('BEGIN IMMEDIATE')
        initialize(c)
        yield c


def present(c):
    return c.execute("SELECT 1 FROM sqlite_master WHERE name='ai_pull_tasks'").fetchone() is not None


def register(name, kinds, *, actor_id=None):
    from .ai_worker_registry import registered_kinds
    if (not isinstance(name, str) or not 1 <= len(name) <= 80 or not name.isprintable()
            or not isinstance(kinds, list) or not kinds or len(kinds) > 64
            or any(not isinstance(k, str) or k not in registered_kinds() for k in kinds)
            or len(set(kinds)) != len(kinds)):
        raise ValueError('Invalid worker name or capabilities')
    node, secret = secrets.token_hex(16), secrets.token_hex(32)
    with transaction() as c:
        c.execute('INSERT INTO ai_pull_nodes VALUES(?,?,?,?,1,1)',
                  (node, hashlib.sha256(secret.encode()).hexdigest(), name, encode(sorted(kinds))))
        _audit(c, actor_id, 'register', node, {'kinds': sorted(kinds)})
    return {'node_id': node, 'credential': node + '.' + secret, 'shown_once': True}


def authenticate(credential):
    if not isinstance(credential, str) or re.fullmatch(r'[a-f0-9]{32}\.[a-f0-9]{64}', credential) is None:
        return None
    node, secret = credential.split('.')
    with auth.db() as c:
        if not c.execute("SELECT 1 FROM sqlite_master WHERE name='ai_pull_nodes'").fetchone():
            return None
        row = c.execute('SELECT key_hash,enabled FROM ai_pull_nodes WHERE id=?', (node,)).fetchone()
    return node if row and row[1] and hmac.compare_digest(row[0], hashlib.sha256(secret.encode()).hexdigest()) else None


def node_record(c, credential):
    # Authentication is checked again under the mutation lock (revocation race).
    if not isinstance(credential, str) or re.fullmatch(r'[a-f0-9]{32}\.[a-f0-9]{64}', credential) is None:
        raise PermissionError('Worker authentication required')
    node, secret = credential.split('.')
    row = c.execute('SELECT * FROM ai_pull_nodes WHERE id=?', (node,)).fetchone()
    if not row or not row['enabled'] or not hmac.compare_digest(row['key_hash'], hashlib.sha256(secret.encode()).hexdigest()):
        raise PermissionError('Worker authentication required')
    return row


def nodes():
    with transaction() as c:
        return [dict(r) for r in c.execute('''SELECT n.id,n.name,n.kinds_json,n.enabled,n.accepting,
            (SELECT COUNT(*) FROM ai_pull_tasks t WHERE t.node_id=n.id AND t.state='dispatched') active
            FROM ai_pull_nodes n ORDER BY n.id''')]


def control(node, *, accepting=None, revoke=False, actor_id=None):
    if not isinstance(node, str) or not HEX.fullmatch(node) or (accepting is not None and type(accepting) is not bool):
        raise ValueError('Invalid node control')
    with transaction() as c:
        row = c.execute('SELECT enabled FROM ai_pull_nodes WHERE id=?', (node,)).fetchone()
        if not row:
            raise ValueError('Unknown worker')
        if revoke:
            c.execute('UPDATE ai_pull_nodes SET enabled=0,accepting=0 WHERE id=?', (node,))
        elif not row[0]:
            raise ValueError('Revoked worker cannot resume')
        else:
            c.execute('UPDATE ai_pull_nodes SET accepting=? WHERE id=?', (int(accepting), node))
        active = c.execute("SELECT COUNT(*) FROM ai_pull_tasks WHERE node_id=? AND state='dispatched'", (node,)).fetchone()[0]
        _audit(c, actor_id, 'revoke' if revoke else 'resume' if accepting else 'pause', node,
               {'active': active, 'quiescence_verified': False})
    return {'node_id': node, 'active': active, 'quiescence_verified': False, 'transition_enabled': False}


def available():
    from .ai_worker_registry import registered_kinds
    supported = set()
    for row in nodes():
        if row['enabled'] and row['accepting']:
            supported.update(decode(row['kinds_json']))
    return {k: k in supported for k in sorted(registered_kinds())}


def _policy(row):
    from .model_license_policy import authorize_remote_execution
    decision = authorize_remote_execution(row['kind'], decode(row['plan_json']))
    if encode(asdict(decision)) != row['policy_json']:
        raise FenceBlocked('Pull admission policy changed before dispatch')


def enqueue(uid, kind, plan, *, source_wav=None, source_json=None, timeout_seconds=1200, token_id=None,
            request_key=None, request_digest=None):
    from .ai_remote_transport import validate_audio_options, MAX_OPTIONS_BYTES
    from .model_license_policy import authorize_remote_execution, record_job
    from .ai_worker_artifacts import _verify_wav_bytes
    validate_audio_options(plan)
    if len(encode(plan).encode()) > MAX_OPTIONS_BYTES:
        raise ValueError('Pull plan exceeds 8 KiB')
    if os.getenv('MTA_NATIVE_SINGLE_USER', '').lower() in ('true','1','yes','on'):
        raise ValueError('Pull authority is server-only')
    if plan.get('kind', kind) != kind or type(timeout_seconds) is not int or not 1 <= timeout_seconds <= 86400:
        raise ValueError('Invalid pull plan or timeout')
    if source_wav is not None and source_json is not None:
        raise ValueError('Exactly one source format is supported')
    source = source_wav if source_wav is not None else source_json
    source = b'' if source is None else source
    if not isinstance(source, bytes) or len(source) > MAX_BYTES:
        raise ValueError('Pull source exceeds 16 MiB')
    if source_wav is not None:
        _verify_wav_bytes(source)
    if source_json is not None:
        from .studio_score import validate
        if kind not in ('vocal-harmony', 'vocal-synthesis'):
            raise ValueError('Unsupported structured source')
        validate(source)
    decision = authorize_remote_execution(kind, plan)
    from .ai_global_execution import current_job
    from . import ai_arranger_runtime as queue
    ledger = None
    if current_job.get():
        with queue._db() as c:
            entry = c.execute('SELECT operation,project_id,payload_json FROM jobs WHERE job_id=?', (current_job.get(),)).fetchone()
        if entry and entry[0] in ('arranger', 'remix'):
            ledger = ai_billing.existing_inference_ledger_job(current_job.get(), uid, entry[0])
    deferred = ledger is not None
    if deferred:
        from .deferred_execution_owner import credentials_for
        owner = credentials_for(ledger)
    else:
        owner = {'worker_id': 'pull:authority:' + secrets.token_hex(16), 'claim_token': secrets.token_hex(32)}
    def admit(c, job):
        initialize(c)
        prior = c.execute('SELECT generation FROM ai_pull_deferred_admissions WHERE job_id=?', (job,)).fetchone() if deferred else None
        if deferred and prior is None:
            raise FenceBlocked('Original pull backend admission required; no legacy owner adoption')
        if c.execute('SELECT accepting FROM ai_pull_state WHERE singleton=1').fetchone()[0] != 1 and prior is None:
            raise FenceBlocked('Pull authority admission is draining')
        if not c.execute('SELECT 1 FROM users WHERE id=? AND active=1', (uid,)).fetchone():
            raise ValueError('Inactive owner')
        if not any(kind in decode(r[0]) for r in c.execute('SELECT kinds_json FROM ai_pull_nodes WHERE enabled=1 AND accepting=1')):
            raise ValueError('No accepting pull worker for this engine')
        count, stored = c.execute('''SELECT COUNT(*),COALESCE(SUM(COALESCE(length(source),0)+
            CASE WHEN state IN('queued','dispatched') THEN ? ELSE COALESCE(length(result),0) END),0)
            FROM ai_pull_tasks''', (MAX_BYTES,)).fetchone()
        if count >= 256 or stored + len(source) + MAX_BYTES > MAX_STORED:
            raise ValueError('Pull storage capacity reached; retain held jobs and prune settled artifacts')
        from .regime_worker_claims import claim
        claim(c, job, worker_id=owner['worker_id'], token=owner['claim_token'])
        record_job(job, decision, _connection=c)
        if request_key is not None:
            from .ai_request_dedup import _KEY
            if deferred or not isinstance(request_key, str) or not _KEY.fullmatch(request_key):
                raise ValueError('Invalid original pull request binding')
            request = c.execute('SELECT fingerprint,state FROM ai_request_dedup WHERE user_id=? AND request_key=?', (uid,request_key)).fetchone()
            if not request or request['fingerprint'] != request_digest or request['state'] != 'admitted':
                raise FenceBlocked('Original admitted remote request required')
        c.execute('''INSERT INTO ai_pull_tasks(job_id,user_id,kind,plan_json,policy_json,source_kind,
            source_sha256,source,deferred,owner_json,timeout,request_key,request_digest,state,created_at)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,'queued',?)''',
            (job, uid, kind, encode(plan), encode(asdict(decision)), 'wav' if source_wav is not None else 'score' if source_json is not None else 'none',
             hashlib.sha256(source).hexdigest(), source, int(deferred), encode(owner), timeout_seconds, request_key, request_digest, int(time.time())))
        if deferred and kind == 'ace-step' and plan.get('input_source') in ('master', 'track'):
            payload = decode(entry['payload_json'])
            if payload.get('actor_user_id') != uid or payload.get('adapter') != entry['operation']:
                raise FenceBlocked('Original publication owner required')
            c.execute('INSERT INTO ai_pull_publication_intents VALUES(?,?,?,?,?)',
                      (job, current_job.get(), entry['project_id'], entry['operation'], plan['input_source']))
        c.execute("UPDATE ai_job_hardware_snapshots SET cpu_model=NULL,gpu_model=NULL,cpu_rate_micro=NULL,gpu_rate_micro=NULL,storage_rate_micro=NULL,origin='unknown',model_version='remote-unverified' WHERE job_id=?", (job,))
    if deferred:
        with transaction() as c:
            admit(c, ledger)
    else:
        with __import__('app.model_license_policy', fromlist=['admission']).admission(decision):
            ledger = ai_billing.create_job(uid, kind, token_id,
                billing_exemption_reason='' if decision.billable else 'license:' + decision.model_id, _admission_hook=admit)
    return ledger


def note_deferred_admission(c, job):
    if not c.in_transaction:
        raise FenceBlocked('Deferred pull admission requires the ledger transaction')
    initialize(c)
    state = c.execute('SELECT accepting,generation FROM ai_pull_state WHERE singleton=1').fetchone()
    if not state[0]:
        raise FenceBlocked('Pull authority admission is draining')
    if not any('ace-step' in decode(r[0]) for r in c.execute('SELECT kinds_json FROM ai_pull_nodes WHERE enabled=1 AND accepting=1')):
        raise ValueError('No accepting pull generation worker')
    c.execute('INSERT INTO ai_pull_deferred_admissions VALUES(?,?)', (job,state[1]))


def _receipt(c, row, *, finished=False):
    from .regime_worker_claims import verify_owner
    owner = decode(row['owner_json'])
    receipt = verify_owner(c, 'job:ledger:' + row['job_id'], worker_id=owner['worker_id'],
                           token=owner['claim_token'], allow_finished=finished)
    ledger = c.execute('SELECT user_id,kind,status FROM ai_compute_jobs WHERE id=?', (row['job_id'],)).fetchone()
    if (not ledger or ledger['user_id'] != row['user_id']
            or (ledger['kind'] not in ('arranger','remix') if row['deferred'] else ledger['kind'] != row['kind'])
            or (receipt['state'] == 'running' and ledger['status'] != 'running')
            or (receipt['state'] == 'finished' and (receipt['fence_status'] != 'closed' or ledger['status'] == 'running'))):
        raise FenceBlocked('Pull assignment does not match its original economic ledger')
    return receipt


def _request(c, row):
    if row['request_key'] is None:
        return None
    request = c.execute('SELECT fingerprint,state,job_id FROM ai_request_dedup WHERE user_id=? AND request_key=?',
                        (row['user_id'],row['request_key'])).fetchone()
    if not request or request['fingerprint'] != row['request_digest']:
        raise FenceBlocked('Original remote request binding changed')
    if request['state'] not in ('admitted','completed','cancelled','failed'):
        raise FenceBlocked('Unknown original remote request state')
    if request['state'] == 'completed' and request['job_id'] != row['job_id']:
        raise FenceBlocked('Original remote request completed under a different ledger')
    if request['state'] == 'completed' and row['state'] in ('queued','dispatched'):
        raise FenceBlocked('Completed request cannot execute again')
    return request


def _request_cancelled(c, row):
    request = _request(c, row)
    return request is not None and request['state'] in ('cancelled','failed')


def assignment(credential, instance):
    if not isinstance(instance, str) or not HEX.fullmatch(instance):
        raise ValueError('Invalid worker instance')
    with transaction() as c:
        node = node_record(c, credential)
        old = c.execute("SELECT * FROM ai_pull_tasks WHERE node_id=? AND state='dispatched'", (node['id'],)).fetchone()
        if old and old['instance'] != instance:
            raise FenceBlocked('Original worker instance still owns uncertain execution')
        row = old
        if row is None and node['accepting']:
            kinds = set(decode(node['kinds_json']))
            for candidate in c.execute("SELECT t.* FROM ai_pull_tasks t JOIN users u ON u.id=t.user_id WHERE t.state='queued' AND t.cancelled=0 AND u.active=1 ORDER BY t.created_at,t.job_id"):
                if candidate['kind'] in kinds:
                    _policy(candidate)
                    _receipt(c, candidate)
                    c.execute("UPDATE ai_pull_tasks SET state='dispatched',node_id=?,instance=?,nonce=? WHERE job_id=? AND state='queued'",
                              (node['id'], instance, secrets.token_hex(32), candidate['job_id']))
                    row = c.execute('SELECT * FROM ai_pull_tasks WHERE job_id=?', (candidate['job_id'],)).fetchone()
                    break
        if row is None:
            return None
        _receipt(c, row)
        active = c.execute('SELECT active FROM users WHERE id=?', (row['user_id'],)).fetchone()
        if row['cancelled'] or not active or not active[0] or _request_cancelled(c, row):
            return {'job_id': row['job_id'], 'instance': instance, 'nonce': row['nonce'], 'cancelled': True}
        _policy(row)
        return {k: row[k] for k in ('job_id', 'kind', 'instance', 'nonce', 'source_kind', 'source_sha256', 'timeout')} | {
            'plan': decode(row['plan_json']), 'policy': decode(row['policy_json']),
            'source_b64': base64.b64encode(row['source']).decode()}


def _assigned(c, credential, job, instance, nonce):
    node = node_record(c, credential)
    row = c.execute('SELECT * FROM ai_pull_tasks WHERE job_id=?', (job,)).fetchone()
    if (not row or row['node_id'] != node['id'] or row['instance'] != instance
            or not isinstance(nonce, str) or not hmac.compare_digest(row['nonce'] or '', nonce)):
        raise FenceBlocked('Original pull assignment required')
    _receipt(c, row, finished=row['state'] in ('frozen', 'done'))
    return row


def heartbeat(credential, job, instance, nonce):
    with transaction() as c:
        row = _assigned(c, credential, job, instance, nonce)
        if row['state'] != 'dispatched':
            raise FenceBlocked('Worker is no longer dispatched')
        from .regime_worker_claims import heartbeat as pulse
        owner = decode(row['owner_json'])
        pulse(c, 'job:ledger:' + job, worker_id=owner['worker_id'], token=owner['claim_token'])
        owner_active = c.execute('SELECT active FROM users WHERE id=?', (row['user_id'],)).fetchone()
        cancel = bool(row['cancelled'] or not owner_active or not owner_active[0] or _request_cancelled(c, row))
        try:
            _policy(row)
        except ValueError:
            cancel = True
        return {'cancelled': cancel}


def validate_payload(payload, media):
    from .ai_worker_artifacts import _verify_wav_bytes, package_artifacts, SAFE_NAME
    if not isinstance(payload, bytes) or not 0 < len(payload) <= MAX_BYTES:
        raise ValueError('Invalid pull result size')
    if media == 'audio/wav':
        _verify_wav_bytes(payload)
        return
    if media != 'application/zip':
        raise ValueError('Unsupported pull output')
    with zipfile.ZipFile(io.BytesIO(payload)) as z:
        infos = z.infolist()
        if not 2 <= len(infos) <= 17 or len({i.filename.casefold() for i in infos}) != len(infos):
            raise ValueError('Invalid pull output entries')
        if any(not SAFE_NAME.fullmatch(i.filename) or i.filename.casefold() == 'output.manifest.json' or i.file_size > MAX_BYTES or i.flag_bits & 1
               or ((i.external_attr >> 16) & 0o170000) == 0o120000 for i in infos):
            raise ValueError('Unsafe pull output')
        if sum(i.file_size for i in infos) > MAX_BYTES:
            raise ValueError('Pull output expansion exceeds capacity')
        manifest = decode(z.read('manifest.json'))
        if not isinstance(manifest, dict) or not isinstance(manifest.get('files'), list):
            raise ValueError('Invalid pull manifest')
        if {i.filename for i in infos} != {'manifest.json'} | {e['name'] for e in manifest['files']}:
            raise ValueError('Pull output differs from manifest')
        with tempfile.TemporaryDirectory(prefix='mta-pull-validate-') as folder:
            directory = Path(folder)
            for i in infos:
                (directory / ('output.manifest.json' if i.filename == 'manifest.json' else i.filename)).write_bytes(z.read(i))
            package_artifacts(directory, max_bytes=MAX_BYTES)


def complete(credential, job, instance, nonce, outcome):
    if not isinstance(outcome, dict) or set(outcome) != {'status', 'cpu_seconds', 'media_type', 'result_b64'}:
        raise ValueError('Invalid pull completion fields')
    status, cpu, media = outcome['status'], outcome['cpu_seconds'], outcome['media_type']
    if status not in ('done', 'failed', 'cancelled') or (cpu is not None and
            (type(cpu) not in (int, float) or not math.isfinite(cpu) or not 0 <= cpu <= 86400 * 4096)):
        raise ValueError('Invalid pull status or measured CPU')
    encoded = outcome['result_b64']
    if not isinstance(encoded, str) or len(encoded) > 4 * MAX_BYTES // 3 + 8:
        raise ValueError('Oversized pull result')
    payload = base64.b64decode(encoded, validate=True)
    if status == 'done':
        validate_payload(payload, media)
    elif payload or media is not None:
        raise ValueError('Failed/cancelled execution cannot publish output')
    proof = encode({'status': status, 'cpu_seconds': cpu, 'media_type': media,
                    'result_sha256': hashlib.sha256(payload).hexdigest()})
    with transaction() as c:
        node = node_record(c, credential)
        receipt = _ack_key(node['id'], job, instance, nonce)
        retired = c.execute('SELECT completion_sha256 FROM ai_pull_acknowledgements WHERE receipt=?', (receipt,)).fetchone()
        if retired:
            if not hmac.compare_digest(retired[0], hashlib.sha256(proof.encode()).hexdigest()):
                raise FenceBlocked('Conflicting retired worker acknowledgement')
            return {'job_id': job, 'acknowledged': True}
        row = _assigned(c, credential, job, instance, nonce)
        if row['state'] in ('frozen', 'done'):
            if decode(row['completion_json'])['worker_proof_sha256'] != hashlib.sha256(proof.encode()).hexdigest():
                raise FenceBlocked('Conflicting immutable worker completion')
        elif row['state'] == 'dispatched':
            active = c.execute('SELECT active FROM users WHERE id=?', (row['user_id'],)).fetchone()
            effective = 'cancelled' if row['cancelled'] or not active or not active[0] or _request_cancelled(c, row) else status
            frozen = encode({**decode(proof), 'execution_status': effective,
                             'worker_proof_sha256': hashlib.sha256(proof.encode()).hexdigest()})
            c.execute("UPDATE ai_pull_tasks SET state='frozen',completion_json=?,result=?,source=NULL,completed_at=? WHERE job_id=?",
                      (frozen, payload, int(time.time()), job))
        else:
            raise FenceBlocked('Task was never dispatched')
    recover(job)
    return {'job_id': job, 'acknowledged': True}


def recover(job):
    with transaction() as c:
        row = c.execute('SELECT * FROM ai_pull_tasks WHERE job_id=?', (job,)).fetchone()
        if not row or row['state'] not in ('frozen', 'done'):
            raise PullPending(job)
        _receipt(c, row, finished=True)
        proof = decode(row['completion_json'])
        owner = decode(row['owner_json'])
        if hashlib.sha256(row['result'] or b'').hexdigest() != proof['result_sha256']:
            raise FenceBlocked('Frozen pull result changed or expired')
    usage = {} if proof['cpu_seconds'] is None else {'cpu_seconds': proof['cpu_seconds']}
    source = 'remote-worker' if usage else 'unmetered'
    meta = {'job_id': job, 'media_type': proof['media_type'], 'usage': usage,
        'metering_source': source, 'gpu_metered': False, 'process_tree_metered': proof['cpu_seconds'] is not None,
        'billable': decode(row['policy_json'])['mode'] == 'cost_recovery',
        'license_model': decode(row['policy_json'])['model_id'], 'license_policy_sha256': decode(row['policy_json'])['policy_sha256'],
        'gpu_diagnostics': {}, 'audio': {'format': 'wav' if proof['media_type'] == 'audio/wav' else 'artifact-zip'},
        'pull_status': proof['execution_status']}
    if not row['deferred'] or proof['execution_status'] != 'done':
        ai_billing.finish_job_idempotent(job, proof['execution_status'], usage, source=source, **owner)
        with transaction() as c:
            current = c.execute('SELECT * FROM ai_pull_tasks WHERE job_id=?', (job,)).fetchone()
            _receipt(c, current, finished=True)
            request = _request(c, current)
            if current['request_key'] is not None:
                from .ai_remote_metering_service import headers
                delivery = decode(current['metering_json']) if current['metering_json'] is not None else headers(meta, current['request_key'])
                c.execute('UPDATE ai_pull_tasks SET metering_json=? WHERE job_id=?', (encode(delivery),job))
                meta['_pull_metering_headers'] = delivery
                if request['state'] == 'admitted':
                    state = 'completed' if proof['execution_status'] == 'done' else 'failed'
                    c.execute('UPDATE ai_request_dedup SET state=?,job_id=? WHERE user_id=? AND request_key=? AND state=?',
                              (state,job if state == 'completed' else None,row['user_id'],row['request_key'],'admitted'))
            c.execute("UPDATE ai_pull_tasks SET state='done' WHERE job_id=? AND state='frozen'", (job,))
    return row['result'] or b'', meta


def load_request_result(uid, key, job):
    """Read existing settled bytes for the original client, never finalize or infer."""
    with auth.db() as c:
        if not present(c):
            return None
        row = c.execute('SELECT * FROM ai_pull_tasks WHERE user_id=? AND request_key=? AND job_id=?', (uid,key,job)).fetchone()
        if not row or row['state'] != 'done' or row['result'] is None:
            return None
        request = _request(c, row)
        receipt = _receipt(c, row, finished=True)
        if request['state'] != 'completed' or receipt['state'] != 'finished' or receipt['fence_status'] != 'closed':
            return None
        proof = decode(row['completion_json'])
        if proof['execution_status'] != 'done' or hashlib.sha256(row['result']).hexdigest() != proof['result_sha256']:
            raise FenceBlocked('Frozen request result changed')
        metering = decode(row['metering_json'] or '{}')
        envelope = decode(metering['X-MTA-AI-Metering-V2']) if metering else None
        if envelope:
            from .ai_remote_metering_service import headers
            headers({'job_id':job,'_pull_metering_headers':metering}, key)
        return bytes(row['result']), proof['media_type'], envelope


def request_cancel(c, uid):
    if present(c):
        c.execute("UPDATE ai_pull_tasks SET cancelled=1 WHERE user_id=? AND state IN('queued','dispatched')", (uid,))


def cancel(job):
    with transaction() as c:
        row = c.execute('SELECT * FROM ai_pull_tasks WHERE job_id=?', (job,)).fetchone()
        if not row:
            raise ValueError('Unknown pull execution')
        if row['state'] in ('queued', 'dispatched'):
            c.execute('UPDATE ai_pull_tasks SET cancelled=1 WHERE job_id=?', (job,))
        if row['state'] == 'queued':
            # The authority can close ONLY work that was never assigned.
            proof = encode({'status': 'cancelled', 'cpu_seconds': None, 'media_type': None,
                            'result_sha256': hashlib.sha256(b'').hexdigest(), 'execution_status': 'cancelled',
                            'worker_proof_sha256': hashlib.sha256(b'authority-undispatched').hexdigest()})
            c.execute("UPDATE ai_pull_tasks SET state='dispatched' WHERE job_id=?", (job,))
            c.execute("UPDATE ai_pull_tasks SET state='frozen',completion_json=?,result=?,source=NULL,completed_at=? WHERE job_id=?",
                      (proof, b'', int(time.time()), job))
    if row['state'] == 'queued':
        recover(job)


def execute(uid, kind, plan, *, cancel_check=None, **options):
    job = enqueue(uid, kind, plan, **options)
    deadline = time.monotonic() + options.get('timeout_seconds', 1200)
    while True:
        if cancel_check and cancel_check():
            cancel(job)
            try:
                recover(job)
            except PullPending:
                pass
            raise PullPending(job)
        try:
            payload, meta = recover(job)
            if cancel_check and cancel_check():
                raise PullPending(job)
            if meta['pull_status'] != 'done':
                from .ai_worker_protocol import WorkerUnavailable
                raise WorkerUnavailable('Pull worker failed or cancelled; no inference retry')
            return payload, meta
        except PullPending:
            if time.monotonic() >= deadline:
                cancel(job)
                raise PullPending(job)
            time.sleep(.05)


def erasure_safe(c, uid):
    if not present(c):
        return
    if c.execute('SELECT authority_binding FROM ai_pull_state WHERE singleton=1').fetchone()[0] != _authority_binding():
        raise FenceBlocked('Original pull authority required for erasure')
    rows = c.execute('SELECT * FROM ai_pull_tasks WHERE user_id=?', (uid,)).fetchall()
    for row in rows:
        if row['state'] not in ('frozen', 'done'):
            raise PullPending(row['job_id'])
        receipt = _receipt(c, row, finished=True)
        if receipt['fence_status'] != 'closed' or receipt['state'] != 'finished':
            raise PullPending(row['job_id'])


def _ack_key(node, job, instance, nonce):
    if not all(isinstance(v, str) for v in (node, job, instance, nonce)):
        raise ValueError('Invalid pull acknowledgement')
    return hmac.new(auth._app_key(), encode([node, job, instance, nonce]).encode(), hashlib.sha256).hexdigest()


def record_erasure(c, uid):
    """Anonymous exact-completion acknowledgement; never retain owner/media/nonces."""
    erasure_safe(c, uid)
    if not present(c):
        return
    for row in c.execute('SELECT * FROM ai_pull_tasks WHERE user_id=?', (uid,)):
        _record_ack(c, row)


def _record_ack(c, row):
    if row['node_id'] is not None:
        c.execute('INSERT OR IGNORE INTO ai_pull_acknowledgements VALUES(?,?,?)',
                  (_ack_key(row['node_id'], row['job_id'], row['instance'], row['nonce']),
                   decode(row['completion_json'])['worker_proof_sha256'], int(time.time())))


def maintenance():
    with auth.db() as c:
        if not present(c):
            return {'cancelled_undispatched': 0, 'expired_artifacts': 0, 'transition_enabled': False}
    with transaction() as c:
        pending = [r[0] for r in c.execute("SELECT t.job_id FROM ai_pull_tasks t JOIN users u ON u.id=t.user_id WHERE t.state='queued' AND (t.cancelled=1 OR u.active=0) LIMIT 16")]
    for job in pending:
        cancel(job)
    with transaction() as c:
        # Clear private artifacts only for economically closed historical work.
        tables = {r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        expired = [r[0] for r in c.execute('''SELECT t.job_id FROM ai_pull_tasks t
            JOIN regime_worker_claims w ON w.operation_id='job:ledger:'||t.job_id
            JOIN regime_fence_operations f ON f.operation_id=w.operation_id
            WHERE t.state IN('frozen','done') AND w.state='finished' AND f.status='closed'
            AND t.completed_at<?''', (int(time.time()) - RETENTION_SECONDS,))] if {'regime_worker_claims', 'regime_fence_operations'} <= tables else []
        for job in expired:
            row = c.execute('SELECT * FROM ai_pull_tasks WHERE job_id=?', (job,)).fetchone()
            _record_ack(c, row)
            c.execute('DELETE FROM ai_pull_tasks WHERE job_id=?', (job,))
        c.execute('DELETE FROM ai_pull_acknowledgements WHERE created_at<?', (int(time.time()) - 90 * 86400,))
    return {'cancelled_undispatched': len(pending), 'expired_artifacts': len(expired), 'transition_enabled': False}


def drain(*, accepting, expected_generation, actor_id=None):
    if type(accepting) is not bool or type(expected_generation) is not int or expected_generation < 0:
        raise ValueError('Exact admission generation and boolean required')
    with transaction() as c:
        current = c.execute('SELECT generation FROM ai_pull_state WHERE singleton=1').fetchone()[0]
        if current != expected_generation:
            raise FenceBlocked('Stale pull admission generation')
        c.execute('UPDATE ai_pull_state SET accepting=?,generation=generation+1 WHERE singleton=1', (int(accepting),))
        _audit(c, actor_id, 'admission-resume' if accepting else 'admission-drain', 'authority',
               {'previous_generation': current, 'generation': current + 1})
        return inspect_state(c)


def inspect_state(c):
    """Pull-scope diagnostic. Never certify legacy executors or kernel drain."""
    empty = {'verified': True, 'pending': 0, 'transition_enabled': False, 'quiescence_verified': False}
    if not present(c):
        return {**empty, 'configured': False}
    try:
        state = c.execute('SELECT accepting,generation,authority_binding FROM ai_pull_state WHERE singleton=1').fetchone()
        if state is None or state[2] != _authority_binding():
            raise FenceBlocked('Missing pull admission state')
        counts = dict(c.execute('SELECT state,COUNT(*) FROM ai_pull_tasks GROUP BY state'))
        rows = c.execute('SELECT * FROM ai_pull_tasks').fetchall()
        pending = 0
        pending += c.execute('''SELECT COUNT(*) FROM ai_pull_deferred_admissions d
            JOIN ai_compute_jobs j ON j.id=d.job_id LEFT JOIN ai_pull_tasks t ON t.job_id=d.job_id
            WHERE t.job_id IS NULL AND j.status='running' ''').fetchone()[0]
        for row in rows:
            receipt = _receipt(c, row, finished=row['state'] in ('frozen','done'))
            request = _request(c, row)
            if row['state'] in ('frozen','done'):
                proof = decode(row['completion_json'])
                if row['source'] is not None or hashlib.sha256(row['result'] or b'').hexdigest() != proof['result_sha256']:
                    raise FenceBlocked('Frozen pull storage integrity failed')
            if (row['state'] in ('queued','dispatched') or (not row['deferred'] and row['state'] != 'done')
                    or receipt['state'] != 'finished' or receipt['fence_status'] != 'closed'
                    or (request is not None and request['state'] == 'admitted')):
                pending += 1
        return {**empty, 'configured': True, 'pending': pending, 'states': counts,
                'accepting': bool(state[0]), 'generation': state[1]}
    except (ValueError, FenceBlocked, OSError, sqlite3.DatabaseError):
        return {**empty, 'verified': False, 'pending': None, 'configured': True}


def rebind_closed_authority(*, expected_binding, actor_id, reason, confirm=False):
    """Explicit offline planned move; never adopt a running/uncertain operation.

    The operator must stop the old authority before moving the data. This does
    not certify physical remote quiescence, enable admission or transfer leases.
    """
    if (confirm is not True or type(actor_id) is not int or actor_id <= 0
            or not isinstance(expected_binding, str) or not re.fullmatch(r'[a-f0-9]{64}', expected_binding)
            or not isinstance(reason, str) or not 20 <= len(reason) <= 2000):
        raise ValueError('Confirmed planned recovery, exact binding, administrator and reason required')
    if not auth.db_path().is_file():
        raise ValueError('Original authority database required')
    with auth.db() as c:
        c.execute('BEGIN IMMEDIATE')
        state = c.execute('SELECT * FROM ai_pull_state WHERE singleton=1').fetchone()
        if not state or not hmac.compare_digest(state['authority_binding'], expected_binding) or state['accepting']:
            raise FenceBlocked('Exact paused original authority state required')
        if c.execute('SELECT 1 FROM ai_pull_nodes WHERE enabled=1 LIMIT 1').fetchone():
            raise FenceBlocked('Revoke every node before a planned authority move')
        if c.execute("SELECT 1 FROM regime_fence_operations WHERE status!='closed' LIMIT 1").fetchone():
            raise FenceBlocked('All original service operations must be settled before a planned move')
        if c.execute("SELECT 1 FROM ai_compute_jobs WHERE status='running' LIMIT 1").fetchone():
            raise FenceBlocked('No active or uncertain economic worker may be adopted')
        for row in c.execute('SELECT * FROM ai_pull_tasks'):
            if row['state'] not in ('frozen','done'):
                raise FenceBlocked('Uncertain pull execution forbids authority rebinding')
            receipt = _receipt(c, row, finished=True)
            if receipt['state'] != 'finished' or receipt['fence_status'] != 'closed':
                raise FenceBlocked('Original completed receipts required')
        current = _authority_binding()
        c.execute('UPDATE ai_pull_state SET authority_binding=?,generation=generation+1 WHERE singleton=1', (current,))
        _audit(c, actor_id, 'closed-authority-rebind', 'authority',
               {'previous_binding': expected_binding, 'new_binding': current, 'reason': reason,
                'quiescence_verified': False, 'accepting': False})
        return {'rebound': True, 'accepting': False, 'transition_enabled': False, 'quiescence_verified': False}


def main(argv=None):
    import argparse
    parser = argparse.ArgumentParser(description='Private offline pull-authority diagnostics/planned recovery')
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--inspect', action='store_true')
    group.add_argument('--rebind-closed', action='store_true')
    parser.add_argument('--expected-binding')
    parser.add_argument('--actor', type=int)
    parser.add_argument('--reason')
    parser.add_argument('--confirm-closed-rebind', action='store_true')
    args = parser.parse_args(argv)
    try:
        if not auth.db_path().is_file():
            raise ValueError('Original authority database required')
        if args.inspect:
            with sqlite3.connect(auth.db_path().as_uri() + '?mode=ro', uri=True) as c:
                c.row_factory = sqlite3.Row
                state = inspect_state(c)
                row = c.execute('SELECT authority_binding FROM ai_pull_state WHERE singleton=1').fetchone()
                state['stored_authority_binding'] = row[0] if row else None
            print(encode(state))
        else:
            print(encode(rebind_closed_authority(expected_binding=args.expected_binding, actor_id=args.actor,
                         reason=args.reason, confirm=args.confirm_closed_rebind)))
        return 0
    except (ValueError, OSError, sqlite3.DatabaseError, FenceBlocked):
        print('Authority recovery blocked; preserve original state and resolve all held operations')
        return 78


if __name__ == '__main__':
    raise SystemExit(main())


def stage_publication(job):
    """Stage a frozen successful WAV with its original scheduler/economic owner.

    Called inside the live owner's context or the narrow dead-parent recovery
    context below. Never constructs a new inference or accounting identity.
    """
    from . import ai_arranger_runtime as queue, ai_metering_bridge as bridge, ai_publish_outbox as publication
    from .deferred_execution_owner import receipt_for
    audio, meta = recover(job)
    with transaction() as c:
        row = c.execute('SELECT * FROM ai_pull_tasks WHERE job_id=?', (job,)).fetchone()
        intent = c.execute('SELECT * FROM ai_pull_publication_intents WHERE job_id=?', (job,)).fetchone()
        active = c.execute('SELECT active FROM users WHERE id=?', (row['user_id'],)).fetchone()
        if (not intent or not row['deferred'] or row['cancelled'] or not active or not active[0]
                or meta['pull_status'] != 'done' or meta['media_type'] != 'audio/wav'
                or not meta['usage']):
            raise FenceBlocked('Successful measured original publication intent required')
        owner = decode(row['owner_json'])
    inference = intent['inference_id']
    with queue._db() as c:
        entry = c.execute('SELECT * FROM jobs WHERE job_id=?', (inference,)).fetchone()
        if (not entry or entry['project_id'] != intent['project_id'] or entry['operation'] != intent['operation']
                or entry['cancel_requested'] or entry['state'] not in ('running', 'interrupted', 'completed')
                or decode(entry['payload_json']).get('actor_user_id') != row['user_id']):
            raise FenceBlocked('Original uncancelled scheduler publication required')
    import wave
    with wave.open(io.BytesIO(audio), 'rb') as wav:
        wav_meta = {**meta, 'frames': wav.getnframes(), 'sample_rate': wav.getframerate(),
                    'channels': wav.getnchannels(), 'format': 'wav'}
    metadata = {'wav': wav_meta, 'mode': intent['operation'], 'input_source': intent['input_source']}
    with publication._open() as c:
        raw = c.execute('SELECT * FROM publications WHERE job_id=?', (inference,)).fetchone()
        previous = publication._validated_publication(raw) if raw else None
    if previous:
        if (previous['project_id'] != intent['project_id'] or previous['audio_sha256'] != hashlib.sha256(audio).hexdigest()
                or decode(previous['metadata']) != metadata):
            raise FenceBlocked('Existing publication conflicts with frozen output')
        return inference
    receipt = receipt_for(inference)
    if not receipt or receipt['ledger_id'] != job or any(receipt[k] != owner[k] for k in owner):
        raise FenceBlocked('Original publication execution context required')
    bridge.capture(inference, meta['usage'], meta['metering_source'])
    publication.stage(inference, intent['project_id'], audio, metadata)
    return inference


def _recover_publication(job, publish):
    """Recover known output only after the original HTTP/scheduler process died.

    Unknown visibility and a live original parent remain held. Remote execution
    must already have supplied its immutable completion. No worker is launched.
    """
    from . import ai_arranger_runtime as queue, ai_finalization, ai_publish_outbox as publication
    from . import deferred_execution_owner as owners
    with transaction() as c:
        row = c.execute('SELECT * FROM ai_pull_tasks WHERE job_id=?', (job,)).fetchone()
        intent = c.execute('SELECT * FROM ai_pull_publication_intents WHERE job_id=?', (job,)).fetchone()
        if not row or not intent or row['state'] not in ('frozen', 'done'):
            raise PullPending(job)
        _receipt(c, row, finished=True)
        owner = decode(row['owner_json'])
    with queue._db() as c:
        entry = c.execute('SELECT runner_pid,runner_identity FROM jobs WHERE job_id=?', (intent['inference_id'],)).fetchone()
    if not entry or not entry['runner_identity'] or type(entry['runner_pid']) is not int:
        raise FenceBlocked('Original parent death cannot be established')
    identity = queue._process_identity(entry['runner_pid'])
    if identity == '' or identity == entry['runner_identity']:
        raise FenceBlocked('Original parent remains live or unverifiable')
    token = owners._CURRENT.set(owners.Owner(intent['inference_id'], job, **owner))
    try:
        inference = stage_publication(job)
    finally:
        owners._CURRENT.reset(token)
    publication.recover(publish, job_id=inference)
    if not ai_finalization.reconcile(inference):
        raise FenceBlocked('Publication/accounting recovery is not complete')
    with transaction() as c:
        current = c.execute('SELECT * FROM ai_pull_tasks WHERE job_id=?', (job,)).fetchone()
        receipt = _receipt(c, current, finished=True)
        if receipt['state'] != 'finished' or receipt['fence_status'] != 'closed':
            raise FenceBlocked('Recovered economic owner remains open')
        c.execute("UPDATE ai_pull_tasks SET state='done' WHERE job_id=? AND state='frozen'", (job,))
    return {'job_id': job, 'inference_id': inference, 'recovered': True, 'execution_replayed': False}


def publication_owner(inference, project):
    """Recheck original pull ownership at the actual project-write boundary."""
    with auth.db() as c:
        if not present(c):
            return None
    with transaction() as c:
        row = c.execute('''SELECT t.*,i.project_id FROM ai_pull_tasks t
            JOIN ai_pull_publication_intents i ON i.job_id=t.job_id WHERE i.inference_id=?''', (inference,)).fetchone()
        if row is None:
            return None
        _receipt(c, row, finished=True)
        user = c.execute('SELECT active FROM users WHERE id=?', (row['user_id'],)).fetchone()
        if (row['project_id'] != project or row['cancelled'] or not user or not user[0]
                or row['state'] not in ('frozen', 'done')
                or decode(row['completion_json'])['execution_status'] != 'done'):
            raise FenceBlocked('Original active pull publication owner required')
    from . import ai_arranger_runtime as queue
    with queue._db() as c:
        entry = c.execute('SELECT cancel_requested FROM jobs WHERE job_id=?', (inference,)).fetchone()
        if not entry or entry[0]:
            raise FenceBlocked('Cancelled publication remains held')
    return row['user_id']


def recover_publication(job, publish):
    """Serialize this complete recovery saga across processes, without inference."""
    from . import ai_publish_outbox as publication, platform_file_lock as locks
    import stat
    if not isinstance(job, str) or not HEX.fullmatch(job):
        raise ValueError('Exact ledger identifier required')
    path = publication._root() / (job + '.pull-recovery.lock')
    fd = os.open(path, os.O_CREAT | os.O_RDWR | getattr(os, 'O_NOFOLLOW', 0), 0o600)
    with os.fdopen(fd, 'a+b') as lock:
        if not stat.S_ISREG(os.fstat(lock.fileno()).st_mode):
            raise ValueError('Recovery lock must be a regular file')
        locks.private_mode(lock.fileno())
        locks.flock(lock.fileno(), locks.LOCK_EX)
        return _recover_publication(job, publish)
