"""Original ownership and immutable independent Linux guardian receipts.

Shares the existing scope count, journal and retirement protocol with cgroups.
Quiescence never bills usage, publishes output, transfers a claim or replays work.
"""
import hashlib
import os
import subprocess
import time

from . import auth, worker_cgroup_recovery as journal
from .regime_operation_fence import FenceBlocked
from .service_admission import control

METHOD = 'linux-subreaper-pidfd-1'


def register(scope, guardian_pid, owner):
    from .ai_arranger_runtime import _process_identity
    supervisor = os.getpid()
    identity = _process_identity(supervisor)
    guard_identity = _process_identity(guardian_pid)
    if not identity or not guard_identity:
        raise FenceBlocked('Original supervisor and guardian identities required')
    binding = {'id': scope, 'job_id': owner['job_id'], 'worker_id': owner['worker_id'],
        'token_sha256': hashlib.sha256(owner['claim_token'].encode()).hexdigest(),
        'host': journal._host(), 'supervisor_pid': supervisor, 'supervisor_identity': identity,
        'guardian_pid': guardian_pid, 'guardian_identity': guard_identity,
        'registered_at': time.time_ns(), 'financial_loss_protocol': 1, 'method': METHOD}
    raw, digest = journal._encode(binding)
    with control(), auth.db() as c:
        c.execute('BEGIN IMMEDIATE')
        journal._initialize(c)
        uid = journal._owner(c, owner['job_id'], owner['worker_id'], owner['claim_token'])
        rows = c.execute('SELECT id FROM worker_cgroup_scopes WHERE job_id=?', (owner['job_id'],)).fetchall()
        expected = c.execute('SELECT worker_scope_count FROM ai_compute_jobs WHERE id=?', (owner['job_id'],)).fetchone()[0]
        if len(rows) != expected:
            raise FenceBlocked('Original worker scope history incomplete')
        for previous, in rows:
            _, old = journal._scope(c, previous)
            if (old['supervisor_pid'], old['supervisor_identity']) != (supervisor, identity):
                raise FenceBlocked('Original supervisor cannot be replaced for another execution')
            if journal._receipt(c, previous) is None:
                raise FenceBlocked('Prior worker tree must be quiescent before another launch')
        kind = c.execute('SELECT kind FROM ai_compute_jobs WHERE id=?', (owner['job_id'],)).fetchone()[0]
        if kind in {'ace-step', 'arranger', 'remix'}:
            binding['financial_loss_protocol'] = 0
            binding['external_execution'] = 'ace-service-not-contained-by-process-tree'
            raw, digest = journal._encode(binding)
        c.execute('INSERT INTO worker_cgroup_scopes VALUES(?,?,?,?,?)', (scope, uid, owner['job_id'], raw, digest))
        c.execute('UPDATE ai_compute_jobs SET worker_scope_count=worker_scope_count+1 WHERE id=?', (owner['job_id'],))


def _guardian(c, scope):
    from .ai_arranger_runtime import _process_identity
    row, binding = journal._scope(c, scope)
    if (binding.get('method') != METHOD or binding['host'] != journal._host()
            or binding['guardian_pid'] != os.getpid()
            or _process_identity(os.getpid()) != binding['guardian_identity']):
        raise FenceBlocked('Only the original Linux guardian may record its tree')
    return row, binding


def launch(scope, config):
    from .ai_arranger_runtime import _process_identity
    with control(), auth.db() as c:
        c.execute('BEGIN IMMEDIATE')
        _, binding = _guardian(c, scope)
        if journal._receipt(c, scope) is not None:
            raise FenceBlocked('Quiescent worker scope cannot execute again')
        if _process_identity(binding['supervisor_pid']) != binding['supervisor_identity']:
            raise FenceBlocked('Original worker supervisor is not live')
        return subprocess.Popen(config['argv'], cwd=config['cwd'], env=config['env'],
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            start_new_session=True, close_fds=True)


def quiescent(scope, *, reason):
    with control(), auth.db() as c:
        c.execute('BEGIN IMMEDIATE')
        if not journal.TABLES <= journal._tables(c):
            return
        if not c.execute('SELECT 1 FROM worker_cgroup_scopes WHERE id=?', (scope,)).fetchone():
            return
        row, _ = _guardian(c, scope)
        if journal._receipt(c, scope) is None:
            journal._store(c, row, actor_id=None, request_id='guardian:' + scope,
                           method=METHOD + ':' + reason)
