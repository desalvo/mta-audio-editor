"""Actual authority ledger and subprocess; no models or external servers."""
from concurrent.futures import ThreadPoolExecutor
import base64
import hashlib
import json
import sqlite3
import threading
import time

import pytest

from app import ai_pull_coordinator as central, ai_pull_worker as worker, auth, ai_billing
from app.regime_operation_fence import FenceBlocked
from test_r208_unified_adapter_billing_e2e import operator as operator, source_audio  # noqa: F401


@pytest.fixture
def authority(operator, tmp_path, monkeypatch):
    monkeypatch.setenv('MTA_AI_EXECUTION_MODE', 'pull')
    from app import ai_arranger_runtime as queue
    monkeypatch.setattr(queue, '_ROOT', tmp_path / 'queue')
    script = tmp_path / 'fixed_worker.py'
    script.write_text('''import argparse,wave,pathlib
p=argparse.ArgumentParser();p.add_argument('--request');p.add_argument('--output');a=p.parse_args()
with wave.open(a.output,'wb') as f:
 f.setnchannels(1);f.setsampwidth(2);f.setframerate(44100);f.writeframes(b'\\0\\0'*256)
''')
    script.chmod(0o700)
    script.write_text('from pathlib import Path\nwith Path(' + repr(str(tmp_path / 'execution-count')) + ').open("ab") as c:c.write(b"1")\n' + script.read_text())
    monkeypatch.setenv('MTA_AI_WORKER_WHISPER_EXECUTABLE', str(script))
    monkeypatch.setenv('MTA_AI_WORKER_ACE_STEP_EXECUTABLE', str(script))
    registration = central.register('fixture-node', ['whisper', 'ace-step'])
    return operator, registration, tmp_path


class DirectClient:
    def __init__(self, credential):
        self.credential = credential
        self.binding = hashlib.sha256(credential.encode()).hexdigest()

    def call(self, action, body, *, job=None):
        if action == 'claim':
            return {'task': central.assignment(self.credential, **body)}
        if action == 'heartbeat':
            return central.heartbeat(self.credential, job, **body)
        return central.complete(self.credential, job, **body)


def enqueue(authority, **options):
    return central.enqueue(authority[0], 'whisper', {}, source_wav=source_audio(), **options)


def task(job):
    with auth.db() as c:
        return dict(c.execute('SELECT * FROM ai_pull_tasks WHERE job_id=?', (job,)).fetchone())


def economic(job):
    with auth.db() as c:
        return (c.execute('SELECT status FROM ai_compute_jobs WHERE id=?', (job,)).fetchone()[0],
                c.execute('SELECT state FROM regime_worker_claims WHERE operation_id=?', ('job:ledger:' + job,)).fetchone()[0],
                c.execute('SELECT status FROM regime_fence_operations WHERE operation_id=?', ('job:ledger:' + job,)).fetchone()[0])


def outcome():
    return {'status': 'done', 'cpu_seconds': 1.25, 'media_type': 'audio/wav',
            'result_b64': base64.b64encode(source_audio()).decode()}


def test_actual_executor_waits_for_worker_and_settles_real_ledger_once(authority, monkeypatch):
    from app.ai_metering_agent import execute_registered_worker
    uid, node, folder = authority
    client = DirectClient(node['credential'])
    with ThreadPoolExecutor(1) as pool:
        pending = pool.submit(execute_registered_worker, uid, 'whisper', {}, source_wav=source_audio())
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            if worker.run_once(client, folder / 'worker-state'):
                break
            threading.Event().wait(.02)
        payload, meta = pending.result(timeout=10)
    assert payload == source_audio() and meta['metering_source'] == 'remote-worker'
    assert set(meta['usage']) == {'cpu_seconds'}
    assert economic(meta['job_id']) == ('done', 'finished', 'closed')
    assert task(meta['job_id'])['source'] is None
    assert json.loads((folder / 'worker-state/active.json').read_text()) == {'binding': client.binding, 'phase': 'done'}
    assert central.recover(meta['job_id'])[1]['usage'] == meta['usage']
    assert ai_billing.job_hardware_snapshot(meta['job_id'])['origin'] == 'unknown'


def test_atomic_capacity_rejection_leaves_no_ledger_fence_or_license_or_claim(authority, monkeypatch):
    monkeypatch.setattr(central, 'MAX_STORED', 1)
    with pytest.raises(ValueError, match='capacity'):
        enqueue(authority)
    with auth.db() as c:
        assert c.execute('SELECT COUNT(*) FROM ai_compute_jobs').fetchone()[0] == 0
        tables = {r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        assert 'regime_fence_operations' not in tables or c.execute('SELECT COUNT(*) FROM regime_fence_operations').fetchone()[0] == 0
        assert c.execute("SELECT name FROM sqlite_master WHERE name='ai_pull_tasks'").fetchone()
        assert c.execute('SELECT COUNT(*) FROM ai_pull_tasks').fetchone()[0] == 0


def test_two_independent_connections_never_assign_same_operation(authority):
    job = enqueue(authority)
    other = central.register('second-node', ['whisper'])
    pairs = [(authority[1]['credential'], 'a' * 32), (other['credential'], 'b' * 32)]
    with ThreadPoolExecutor(2) as pool:
        results = list(pool.map(lambda pair: central.assignment(*pair), pairs))
    assert sum(r is not None for r in results) == 1
    assert next(r for r in results if r)['job_id'] == job
    assert economic(job) == ('running', 'running', 'open')


def test_claim_lost_response_recovers_same_attempt_but_not_new_instance(authority):
    enqueue(authority)
    key = authority[1]['credential']
    first = central.assignment(key, 'a' * 32)
    assert central.assignment(key, 'a' * 32) == first
    with pytest.raises(FenceBlocked):
        central.assignment(key, 'b' * 32)


@pytest.mark.parametrize('change', ['epoch', 'claim', 'policy'])
def test_stale_epoch_receipt_and_policy_never_dispatch(authority, change):
    job = enqueue(authority)
    with auth.db() as c:
        if change == 'epoch':
            c.execute('UPDATE regime_fence_state SET revision=revision+1')
        elif change == 'claim':
            c.execute('UPDATE regime_worker_claims SET revision=revision+1')
        else:
            from app.model_license_policy import configure
            configure('whisper', {'mode': 'disabled', 'acknowledge_responsibility': True, 'evidence_url': 'https://example.org/review', 'reason': 'Revoked operator fixture permission', 'free_access_confirmed': False, 'authorization_basis': 'written_permission', 'confirm_risk_twice': True}, 1)
    with pytest.raises((FenceBlocked, ValueError)):
        central.assignment(authority[1]['credential'], 'a' * 32)
    assert task(job)['state'] == 'queued'


def test_frozen_result_survives_accounting_failure_without_inference_replay(authority, monkeypatch):
    job = enqueue(authority)
    key = authority[1]['credential']
    grant = central.assignment(key, 'a' * 32)
    original = ai_billing.finish_job_idempotent
    monkeypatch.setattr(ai_billing, 'finish_job_idempotent', lambda *a, **kw: (_ for _ in ()).throw(RuntimeError('authority stopped before accounting')))
    with pytest.raises(RuntimeError, match='before accounting'):
        central.complete(key, job, grant['instance'], grant['nonce'], outcome())
    assert task(job)['state'] == 'frozen'
    assert economic(job) == ('running', 'running', 'open')
    monkeypatch.setattr(ai_billing, 'finish_job_idempotent', original)
    assert central.recover(job)[0] == source_audio()
    assert central.complete(key, job, grant['instance'], grant['nonce'], outcome())['acknowledged']
    assert economic(job) == ('done', 'finished', 'closed')


@pytest.mark.parametrize('field,value', [('cpu_seconds', True), ('cpu_seconds', -1), ('cpu_seconds', float('nan')),
                                        ('media_type', 'text/plain'), ('result_b64', 'bad!')])
def test_invalid_completion_cannot_mutate_economic_state(authority, field, value):
    job = enqueue(authority)
    key = authority[1]['credential']
    grant = central.assignment(key, 'a' * 32)
    with pytest.raises((ValueError, TypeError)):
        central.complete(key, job, grant['instance'], grant['nonce'], {**outcome(), field: value})
    assert economic(job) == ('running', 'running', 'open')
    assert task(job)['completion_json'] is None


def test_forged_assignment_and_frozen_sql_overwrite_are_rejected(authority):
    job = enqueue(authority)
    key = authority[1]['credential']
    grant = central.assignment(key, 'a' * 32)
    with pytest.raises(FenceBlocked):
        central.complete(key, job, grant['instance'], 'forged', outcome())
    central.complete(key, job, grant['instance'], grant['nonce'], outcome())
    with auth.db() as c:
        with pytest.raises(sqlite3.IntegrityError):
            c.execute("UPDATE ai_pull_tasks SET completion_json='{}'")
        with pytest.raises(sqlite3.IntegrityError):
            c.execute("UPDATE ai_pull_tasks SET result=?", (b'forged',))
    with pytest.raises(FenceBlocked):
        central.complete(key, job, grant['instance'], grant['nonce'], {**outcome(), 'cpu_seconds': 2})


def test_pause_resume_revoke_do_not_claim_worker_quiescence(authority):
    job = enqueue(authority)
    node, key = authority[1]['node_id'], authority[1]['credential']
    central.control(node, accepting=False)
    assert not central.available()['whisper']
    assert central.assignment(key, 'a' * 32) is None
    central.control(node, accepting=True)
    grant = central.assignment(key, 'a' * 32)
    paused = central.control(node, accepting=False)
    assert paused['active'] == 1 and paused['quiescence_verified'] is False
    assert central.heartbeat(key, job, grant['instance'], grant['nonce']) == {'cancelled': False}
    central.control(node, revoke=True)
    assert central.authenticate(key) is None
    with pytest.raises(PermissionError):
        central.complete(key, job, grant['instance'], grant['nonce'], outcome())
    assert economic(job) == ('running', 'running', 'open')


def test_queued_cancel_settles_no_cpu_and_never_grants_source(authority):
    job = enqueue(authority)
    central.cancel(job)
    assert economic(job) == ('cancelled', 'finished', 'closed')
    assert central.recover(job)[1]['usage'] == {}
    assert central.assignment(authority[1]['credential'], 'a' * 32) is None


def test_running_cancel_remains_held_until_authenticated_completion(authority):
    job = enqueue(authority)
    key = authority[1]['credential']
    grant = central.assignment(key, 'a' * 32)
    central.cancel(job)
    assert economic(job) == ('running', 'running', 'open')
    assert central.heartbeat(key, job, grant['instance'], grant['nonce']) == {'cancelled': True}
    central.complete(key, job, grant['instance'], grant['nonce'], outcome())
    assert economic(job) == ('cancelled', 'finished', 'closed')


def test_prune_preserves_unknown_execution_and_opaque_acknowledges_closed_result(authority, monkeypatch):
    job = enqueue(authority)
    key = authority[1]['credential']
    grant = central.assignment(key, 'a' * 32)
    central.complete(key, job, grant['instance'], grant['nonce'], outcome())
    monkeypatch.setattr(central.time, 'time', lambda: 2**40)
    assert central.maintenance()['expired_artifacts'] == 1
    with auth.db() as c:
        assert c.execute('SELECT COUNT(*) FROM ai_pull_tasks').fetchone()[0] == 0
        raw = json.dumps([dict(r) for r in c.execute('SELECT * FROM ai_pull_acknowledgements')])
        assert job not in raw and grant['nonce'] not in raw
    assert central.complete(key, job, grant['instance'], grant['nonce'], outcome())['acknowledged']


def test_authority_drain_rejects_new_admission_but_finishes_existing_queue(authority):
    job = enqueue(authority)
    state = central.drain(accepting=False, expected_generation=0)
    assert not state['accepting'] and state['pending'] == 1 and not state['quiescence_verified']
    with pytest.raises(FenceBlocked, match='draining'):
        enqueue(authority)
    key = authority[1]['credential']
    grant = central.assignment(key, 'a' * 32)
    central.complete(key, job, grant['instance'], grant['nonce'], outcome())
    with auth.db() as c:
        assert central.inspect_state(c)['pending'] == 0
    with pytest.raises(FenceBlocked, match='Stale'):
        central.drain(accepting=True, expected_generation=0)
    assert central.drain(accepting=True, expected_generation=1)['accepting']


def test_current_epoch_corruption_blocks_pull_readiness(authority):
    enqueue(authority)
    with auth.db() as c:
        c.execute('UPDATE regime_worker_claims SET revision=revision+1')
        result = central.inspect_state(c)
        assert not result['verified'] and result['pending'] is None and result['transition_enabled'] is False


def test_copied_authority_database_cannot_become_second_active_coordinator(authority, monkeypatch):
    import shutil
    enqueue(authority)
    original = auth.data_root()
    clone = authority[2] / 'cloned-authority'
    shutil.copytree(original, clone)
    monkeypatch.setattr(auth, 'DATA_ROOT', clone)
    with pytest.raises(FenceBlocked, match='host/storage changed'):
        central.assignment(authority[1]['credential'], 'a' * 32)
    with auth.db() as c:
        assert not central.inspect_state(c)['verified']
        assert c.execute("SELECT COUNT(*) FROM ai_pull_tasks WHERE state='dispatched'").fetchone()[0] == 0


def test_planned_offline_rebind_requires_closed_work_revoked_nodes_and_operator(authority, monkeypatch):
    import shutil
    job = enqueue(authority)
    with auth.db() as c:
        binding = c.execute('SELECT authority_binding FROM ai_pull_state').fetchone()[0]
        c.execute("INSERT INTO users(username,email,password_hash,role,active,created_at,updated_at) VALUES('move-admin','move@example.test','fixture','admin',1,1,1)")
        admin = c.execute("SELECT id FROM users WHERE username='move-admin'").fetchone()[0]
    args = {'expected_binding':binding,'actor_id':admin,'reason':'Planned offline authority move after completed accounting','confirm':True}
    with pytest.raises(FenceBlocked):
        central.rebind_closed_authority(**args)
    central.drain(accepting=False, expected_generation=0)
    with pytest.raises(FenceBlocked):
        central.rebind_closed_authority(**args)
    grant = central.assignment(authority[1]['credential'], 'a' * 32)
    central.complete(authority[1]['credential'], job, grant['instance'], grant['nonce'], outcome())
    central.control(authority[1]['node_id'], revoke=True)
    clone = authority[2] / 'planned-move'
    shutil.copytree(auth.data_root(), clone)
    monkeypatch.setattr(auth, 'DATA_ROOT', clone)
    with pytest.raises(PermissionError):
        central.rebind_closed_authority(**{**args,'actor_id':authority[0]})
    assert central.rebind_closed_authority(**args)['accepting'] is False
    with auth.db() as c:
        state = central.inspect_state(c)
        assert state['verified'] and state['pending'] == 0 and not state['accepting']
        assert c.execute("SELECT COUNT(*) FROM ai_pull_operator_audit WHERE action='closed-authority-rebind'").fetchone()[0] == 1
    assert central.authenticate(authority[1]['credential']) is None


def test_deferred_generation_admission_is_atomic_with_authority_drain(authority):
    job = ai_billing.provision_inference_job('admitted_before_drain',authority[0],'arranger')
    central.drain(accepting=False,expected_generation=0)
    with auth.db() as c:
        assert central.inspect_state(c)['pending'] == 1
    with pytest.raises(FenceBlocked,match='draining'):
        ai_billing.provision_inference_job('rejected_during_drain',authority[0],'arranger')
    with auth.db() as c:
        assert c.execute('SELECT COUNT(*) FROM ai_compute_jobs').fetchone()[0] == 1
        assert c.execute('SELECT COUNT(*) FROM ai_pull_deferred_admissions').fetchone()[0] == 1
    assert job
