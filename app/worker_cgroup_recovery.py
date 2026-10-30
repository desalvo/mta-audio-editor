"""Local kernel quiescence receipts; never settle money or transfer ownership.

Records are committed before spawn. Recovery pins the original cgroup inode,
kernel filesystem, host/boot/namespace and supervisor creation identity. A
successful stop leaves the original economic claim for separate review.
"""
from contextlib import contextmanager
import ctypes
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import time
import uuid

from . import auth
from .regime_operation_fence import FenceBlocked

TABLES = {'worker_cgroup_scopes', 'worker_cgroup_receipts'}


def _tables(c):
    return {r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}


def _encode(value):
    raw = json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)
    return raw, hashlib.sha256(raw.encode()).hexdigest()


def _decode(raw, digest):
    if hashlib.sha256(raw.encode()).hexdigest() != digest:
        raise FenceBlocked('Worker cgroup receipt integrity failure')
    return json.loads(raw)


def _initialize(c):
    existing = TABLES & _tables(c)
    if existing and existing != TABLES:
        raise FenceBlocked('Incomplete worker cgroup journal')
    if not existing and c.execute('SELECT 1 FROM ai_compute_jobs WHERE worker_scope_count>0 LIMIT 1').fetchone():
        raise FenceBlocked('Worker cgroup journal missing; cannot recreate evidence')
    c.execute('''CREATE TABLE IF NOT EXISTS worker_cgroup_scopes(
      id TEXT PRIMARY KEY,user_id INTEGER NOT NULL REFERENCES users(id),
      job_id TEXT NOT NULL REFERENCES ai_compute_jobs(id),binding_json TEXT NOT NULL,sha256 TEXT NOT NULL)''')
    c.execute('''CREATE TABLE IF NOT EXISTS worker_cgroup_receipts(
      scope_id TEXT PRIMARY KEY REFERENCES worker_cgroup_scopes(id),
      user_id INTEGER NOT NULL REFERENCES users(id),request_id TEXT NOT NULL UNIQUE,
      evidence_json TEXT NOT NULL,sha256 TEXT NOT NULL)''')
    for table, key in (('worker_cgroup_scopes', 'id'), ('worker_cgroup_receipts', 'scope_id')):
        c.execute(f'''CREATE TRIGGER IF NOT EXISTS {table}_immutable_update BEFORE UPDATE ON {table}
          BEGIN SELECT RAISE(ABORT,'Immutable worker cgroup journal'); END''')
        c.execute(f'''CREATE TRIGGER IF NOT EXISTS {table}_immutable_delete BEFORE DELETE ON {table}
          WHEN mta_worker_erasure('{table}',OLD.{key})=0
          BEGIN SELECT RAISE(ABORT,'Immutable worker cgroup journal'); END''')


def _host():
    # Different boots/namespaces cannot reinterpret an old cgroup pathname.
    return {'machine': hashlib.sha256(Path('/etc/machine-id').read_bytes()).hexdigest(),
            'boot': Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
            'namespace': os.stat('/proc/self/ns/cgroup').st_ino}


def _kernel_filesystem(fd):
    libc = ctypes.CDLL(None, use_errno=True)
    libc.fstatfs.argtypes = [ctypes.c_int, ctypes.c_void_p]
    libc.fstatfs.restype = ctypes.c_int
    buffer = ctypes.create_string_buffer(256)
    if libc.fstatfs(fd, buffer) != 0:
        raise OSError(ctypes.get_errno(), 'Cannot verify cgroup filesystem')
    if ctypes.c_long.from_buffer(buffer).value != 0x63677270:
        raise FenceBlocked('Worker recovery requires the actual cgroup v2 filesystem')


@contextmanager
def _group(root, name, *, expected=None):
    root = Path(root)
    if (root != root.resolve(strict=True) or root == Path('/sys/fs/cgroup')
            or not root.is_relative_to('/sys/fs/cgroup') or not re.fullmatch(r'mta-[a-f0-9]{32}', name)):
        raise FenceBlocked('Invalid delegated worker cgroup identity')
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
    rootfd = os.open(root, flags)
    groupfd = None
    try:
        _kernel_filesystem(rootfd)
        groupfd = os.open(name, flags, dir_fd=rootfd)
        _kernel_filesystem(groupfd)
        r, g = os.fstat(rootfd), os.fstat(groupfd)
        identity = {'root_dev': r.st_dev, 'root_ino': r.st_ino,
                    'group_dev': g.st_dev, 'group_ino': g.st_ino}
        if expected is not None and identity != expected:
            raise FenceBlocked('Worker cgroup was replaced; recovery refused')
        yield groupfd, identity
    finally:
        if groupfd is not None:
            os.close(groupfd)
        os.close(rootfd)


def _read(fd, name):
    child = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=fd)
    with os.fdopen(child) as stream:
        raw = stream.read(8193)
    if len(raw) > 8192:
        raise FenceBlocked('Oversized worker cgroup telemetry')
    return raw


def _empty(fd):
    entries = dict(line.split() for line in _read(fd, 'cgroup.events').splitlines())
    if entries.get('populated') not in ('0', '1'):
        raise FenceBlocked('Worker cgroup occupancy unavailable')
    return entries['populated'] == '0'


def _stop(fd):
    if _empty(fd):
        return
    child = os.open('cgroup.kill', os.O_WRONLY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=fd)
    with os.fdopen(child, 'w') as stream:
        stream.write('1')
    deadline = time.monotonic() + 2
    while not _empty(fd):
        if time.monotonic() >= deadline:
            raise FenceBlocked('Recursive worker quiescence remains unverified')
        time.sleep(.02)


def _owner(c, job_id, worker_id, token):
    from .deferred_execution_owner import validate_receipt
    validate_receipt(c, job_id, worker_id, token)
    return c.execute('SELECT user_id FROM ai_compute_jobs WHERE id=?', (job_id,)).fetchone()[0]


def register(group, job_id, credentials):
    from .ai_arranger_runtime import _process_identity
    pid = os.getpid()
    identity = _process_identity(pid)
    if not identity:
        raise FenceBlocked('Verifiable supervisor identity required before worker launch')
    host = _host()
    if not host['boot']:
        raise FenceBlocked('Worker host identity unavailable')
    group = Path(group)
    with _group(group.parent, group.name) as (fd, kernel):
        if not _empty(fd):
            raise FenceBlocked('Worker cgroup must be empty before registration')
        binding = {'id': uuid.uuid4().hex, 'job_id': job_id, 'worker_id': credentials['worker_id'],
                   'token_sha256': hashlib.sha256(credentials['claim_token'].encode()).hexdigest(),
                   'host': host, 'supervisor_pid': pid, 'supervisor_identity': identity,
                   'root': str(group.parent), 'name': group.name, 'kernel': kernel,
                   'registered_at': time.time_ns(), 'financial_loss_protocol': 1}
        raw, digest = _encode(binding)
        with auth.db() as c:
            c.execute('BEGIN IMMEDIATE')
            _initialize(c)
            uid = _owner(c, job_id, credentials['worker_id'], credentials['claim_token'])
            prior=c.execute('SELECT id FROM worker_cgroup_scopes WHERE job_id=?',(job_id,)).fetchall()
            expected=c.execute('SELECT worker_scope_count FROM ai_compute_jobs WHERE id=?',(job_id,)).fetchone()[0]
            if len(prior)!=expected:
                raise FenceBlocked('Worker cgroup history incomplete before launch')
            for scope, in prior:
                _, previous=_scope(c,scope)
                if (previous['supervisor_pid'],previous['supervisor_identity'])!=(pid,identity):
                    raise FenceBlocked('Original supervisor ownership cannot be transferred for another launch')
            c.execute('INSERT INTO worker_cgroup_scopes VALUES(?,?,?,?,?)', (binding['id'], uid, job_id, raw, digest))
            c.execute('UPDATE ai_compute_jobs SET worker_scope_count=worker_scope_count+1 WHERE id=?', (job_id,))
    return binding['id']


def _scope(c, scope_id):
    if not isinstance(scope_id,str) or not re.fullmatch(r'[a-f0-9]{32}',scope_id):
        raise ValueError('Invalid worker scope identifier')
    row = c.execute('SELECT * FROM worker_cgroup_scopes WHERE id=?', (scope_id,)).fetchone()
    if row is None:
        raise FenceBlocked('Unknown worker cgroup scope')
    b = _decode(row['binding_json'], row['sha256'])
    job = c.execute('SELECT user_id FROM ai_compute_jobs WHERE id=?', (row['job_id'],)).fetchone()
    if b['id'] != row['id'] or b['job_id'] != row['job_id'] or job is None or job[0] != row['user_id']:
        raise FenceBlocked('Worker cgroup binding mismatch')
    claim = c.execute('SELECT worker_id,claim_token FROM regime_worker_claims WHERE operation_id=?',
                      ('job:ledger:' + row['job_id'],)).fetchone()
    if (claim is None or claim[0] != b['worker_id']
            or hashlib.sha256(claim[1].encode()).hexdigest() != b['token_sha256']):
        raise FenceBlocked('Worker cgroup original claim changed')
    return row, b


def enter_before_exec(scope_id, group):
    """Serialize late bootstrap admission with cleanup/recovery receipts.

    No child may join after recovery committed populated=0. Holding the same
    ledger write lock across liveness validation AND kernel admission closes
    the gap between Popen and the child's first cgroup.procs write.
    """
    from .ai_arranger_runtime import _process_identity
    with auth.db() as c:
        c.execute('BEGIN IMMEDIATE')
        row, b = _scope(c, scope_id)
        if b.get('method') == 'linux-subreaper-pidfd-1':
            raise FenceBlocked('Independent guardian scope cannot enter a cgroup launcher')
        if _receipt(c, scope_id) or b['host'] != _host():
            raise FenceBlocked('Worker scope already quiesced or belongs to another host')
        if not b['supervisor_identity'] or _process_identity(b['supervisor_pid']) != b['supervisor_identity']:
            raise FenceBlocked('Original supervisor must be alive at kernel admission')
        token=c.execute('SELECT claim_token FROM regime_worker_claims WHERE operation_id=?',
                        ('job:ledger:'+row['job_id'],)).fetchone()[0]
        _owner(c,row['job_id'],b['worker_id'],token)
        if str(Path(group)) != str(Path(b['root'])/b['name']):
            raise FenceBlocked('Bootstrap cgroup differs from registered scope')
        with _group(b['root'],b['name'],expected=b['kernel']) as (fd,_):
            child=os.open('cgroup.procs',os.O_WRONLY|os.O_NOFOLLOW|os.O_CLOEXEC,dir_fd=fd)
            with os.fdopen(child,'w') as stream:stream.write(str(os.getpid()))


def _receipt(c, scope_id):
    r = c.execute('SELECT * FROM worker_cgroup_receipts WHERE scope_id=?', (scope_id,)).fetchone()
    if not r:
        return None
    e = _decode(r['evidence_json'], r['sha256'])
    s = c.execute('SELECT user_id,sha256 FROM worker_cgroup_scopes WHERE id=?', (scope_id,)).fetchone()
    if (s is None or r['user_id'] != s[0] or e['scope_id'] != scope_id
            or e['binding_sha256'] != s[1] or e['populated'] != 0 or e['request_id'] != r['request_id']):
        raise FenceBlocked('Worker quiescence evidence mismatch')
    return e


def _store(c, row, *, actor_id, request_id, method):
    e = {'scope_id': row['id'], 'binding_sha256': row['sha256'], 'populated': 0,
         'actor_id': actor_id, 'request_id': request_id, 'method': method,
         'checked_at': time.time_ns(), 'financial_settlement': False}
    raw, digest = _encode(e)
    c.execute('INSERT INTO worker_cgroup_receipts VALUES(?,?,?,?,?)',
              (row['id'], row['user_id'], request_id, raw, digest))
    return e


def owner_quiescent(scope_id):
    from .ai_arranger_runtime import _process_identity
    with auth.db() as c:
        c.execute('BEGIN IMMEDIATE')
        row, b = _scope(c, scope_id)
        if _receipt(c, scope_id):
            return
        if b.get('method') == 'linux-subreaper-pidfd-1':
            raise FenceBlocked('Independent guardian quiescence evidence required')
        if (b['host'] != _host() or b['supervisor_pid'] != os.getpid()
                or not b['supervisor_identity'] or _process_identity(os.getpid()) != b['supervisor_identity']):
            raise FenceBlocked('Only the original live supervisor may attest cleanup')
        with _group(b['root'], b['name'], expected=b['kernel']) as (fd, _):
            if not _empty(fd):
                raise FenceBlocked('Worker subtree still populated')
            _store(c, row, actor_id=None, request_id='owner:' + scope_id, method='original_supervisor_cleanup')


def _admin(c, actor):
    row = c.execute('SELECT role,active FROM users WHERE id=?', (actor,)).fetchone()
    if row is None or tuple(row) != ('admin', 1):
        raise FenceBlocked('Active administrator required')


def recover(scope_id, actor, request_id):
    if not isinstance(request_id, str) or not re.fullmatch(r'[A-Za-z0-9_-]{16,100}', request_id):
        raise ValueError('Invalid recovery request identifier')
    from .ai_arranger_runtime import _process_identity
    with auth.db() as c:
        c.execute('BEGIN IMMEDIATE')
        _admin(c, actor)
        if not TABLES <= _tables(c):
            raise FenceBlocked('Worker cgroup journal unavailable')
        row, b = _scope(c, scope_id)
        old = _receipt(c, scope_id)
        if old:
            return old  # Exact persisted quiescence; never kill twice.
        if b.get('method') == 'linux-subreaper-pidfd-1':
            raise FenceBlocked('Independent guardian receipt unavailable; original work remains held')
        if c.execute('SELECT 1 FROM worker_cgroup_receipts WHERE request_id=?', (request_id,)).fetchone():
            raise FenceBlocked('Recovery request identifier already used')
        if b['host'] != _host():
            raise FenceBlocked('Recovery requires the original host, boot and cgroup namespace')
        current = _process_identity(b['supervisor_pid'])
        if current == '' or current == b['supervisor_identity']:
            raise FenceBlocked('Original supervisor is live or its death is unverified')
        # The original process is proven absent/replaced. Never signal its PID.
        with _group(b['root'], b['name'], expected=b['kernel']) as (fd, _):
            _stop(fd)
            return _store(c, row, actor_id=actor, request_id=request_id, method='dead_supervisor_kernel_quiescence')


def require_quiescent(c, job_id):
    columns = {r[1] for r in c.execute('PRAGMA table_info(ai_compute_jobs)')}
    if 'worker_scope_count' not in columns:
        if TABLES & _tables(c):
            raise FenceBlocked('Worker scope count unavailable')
        return
    expected = c.execute('SELECT worker_scope_count FROM ai_compute_jobs WHERE id=?', (job_id,)).fetchone()
    if not expected:
        return
    if not expected[0]:
        if 'worker_cgroup_scopes' in _tables(c) and c.execute('SELECT 1 FROM worker_cgroup_scopes WHERE job_id=?', (job_id,)).fetchone():
            raise FenceBlocked('Worker cgroup count mismatch')
        return
    if not TABLES <= _tables(c):
        raise FenceBlocked('Worker cgroup journal unavailable')
    rows = c.execute('SELECT id FROM worker_cgroup_scopes WHERE job_id=?', (job_id,)).fetchall()
    if len(rows) != expected[0]:
        raise FenceBlocked('Worker cgroup history incomplete')
    for row in rows:
        _scope(c, row[0])
        if not _receipt(c, row[0]):
            raise FenceBlocked('Worker cgroup quiescence must be verified before financial finalization')


def report(c, *, limit=200, offset=0):
    if type(limit) is not int or not 1<=limit<=200 or type(offset) is not int or offset<0:
        raise ValueError('Invalid worker journal page')
    try:
        tables = _tables(c)
        if not TABLES & tables:
            if 'worker_scope_count' in {r[1] for r in c.execute('PRAGMA table_info(ai_compute_jobs)')}:
                if c.execute('SELECT 1 FROM ai_compute_jobs WHERE worker_scope_count>0 LIMIT 1').fetchone():
                    raise FenceBlocked('Worker journal missing')
            return {'verified': True, 'scopes': [], 'pending': 0, 'financial_settlement': False}
        if not TABLES <= tables:
            raise FenceBlocked('Partial worker journal')
        from .worker_loss_resolution import history
        losses={r['job_id'] for r in history(c)}
        result = []
        if c.execute('''SELECT 1 FROM ai_compute_jobs j LEFT JOIN worker_cgroup_scopes s ON s.job_id=j.id
          GROUP BY j.id HAVING count(s.id)!=j.worker_scope_count LIMIT 1''').fetchone():
            raise FenceBlocked('Worker cgroup history incomplete')
        if c.execute('SELECT 1 FROM worker_cgroup_receipts r LEFT JOIN worker_cgroup_scopes s ON s.id=r.scope_id WHERE s.id IS NULL LIMIT 1').fetchone():
            raise FenceBlocked('Orphan worker quiescence receipt')
        for scope_id, in c.execute('SELECT id FROM worker_cgroup_scopes ORDER BY rowid DESC'):
            row, b = _scope(c, scope_id)
            e = _receipt(c, scope_id)
            job_state=c.execute('SELECT status FROM ai_compute_jobs WHERE id=?',(row['job_id'],)).fetchone()[0]
            result.append({'scope_id': scope_id, 'job_id': row['job_id'], 'user_id': row['user_id'],
                           'quiescent': e is not None, 'method': e['method'] if e else None,
                           'financial_settlement': row['job_id'] in losses,
                           'financial_state':'operator_loss' if row['job_id'] in losses else 'original_settlement' if job_state!='running' else 'review_required'})
        pending = c.execute('SELECT count(*) FROM worker_cgroup_scopes s LEFT JOIN worker_cgroup_receipts r ON r.scope_id=s.id WHERE r.scope_id IS NULL').fetchone()[0]
        return {'verified': True, 'scopes': result[offset:offset+limit], 'pending': pending,
                'total': len(result), 'offset': offset, 'limit': limit,
                'truncated': offset+limit<len(result), 'financial_settlement': False}
    except (sqlite3.DatabaseError, FenceBlocked, ValueError, TypeError, KeyError):
        return {'verified': False, 'scopes': [], 'pending': None, 'financial_settlement': False}


def authorize_account_erasure(c, uid, actor):
    if not TABLES & _tables(c):
        return
    if not c.in_transaction:
        raise FenceBlocked('Worker journal erasure requires a write transaction')
    scopes = {r[0] for r in c.execute('SELECT id FROM worker_cgroup_scopes WHERE user_id=?', (uid,))}
    if not scopes:
        return
    _admin(c, actor)
    for scope in scopes:
        if not _receipt(c, scope):
            raise FenceBlocked('Worker quiescence required before account erasure')
    owner = c.execute('SELECT role,active FROM users WHERE id=?', (uid,)).fetchone()
    life = c.execute('SELECT state FROM account_lifecycle WHERE user_id=?', (uid,)).fetchone()
    if owner is None or owner[0] == 'admin' or owner[1] or life is None or life[0] not in ('deleted', 'expired', 'erasing'):
        raise FenceBlocked('Approved retired-account erasure required')
    c.create_function('mta_worker_erasure', 2, lambda table, key: int(table in TABLES and key in scopes))
