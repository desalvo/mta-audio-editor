"""Frozen output recovery after actual parent death, never new inference."""
import os
import threading
import traceback
import pytest
from app import ai_pull_coordinator as central, ai_arranger_runtime as queue, ai_billing, auth
from app import ai_publish_outbox as publication, ai_billing_outbox as billing
from app.ai_global_execution import current_job
from app.deferred_execution_owner import execution_scope
from app.regime_operation_fence import FenceBlocked
from test_r210_pull_coordinator import authority as authority, task, economic, outcome  # noqa: F401
from test_r208_unified_adapter_billing_e2e import operator as operator  # noqa: F401


@pytest.fixture(params=['arranger', 'remix'])
def frozen(authority, request):
    uid, node, _ = authority
    inference = 'pull_publication_parent'
    operation = request.param
    queue.start('aaaaaaaaaaaa', operation, None, job_id=inference, defer_spawn=True,
                payload={'schema_version': 1, 'actor_user_id': uid, 'adapter': operation})
    ledger = ai_billing.provision_inference_job(inference, uid, operation)
    pid = os.fork()
    if pid == 0:
        try:
            assert queue._claim(inference)
            with execution_scope(inference, threading.Event()):
                token = current_job.set(inference)
                try:
                    assert central.enqueue(uid, 'ace-step', {'input_source': 'master'}) == ledger
                finally:
                    current_job.reset(token)
                grant = central.assignment(node['credential'], 'a' * 32)
                central.complete(node['credential'], ledger, grant['instance'], grant['nonce'], outcome())
            os._exit(0)
        except BaseException:
            traceback.print_exc()
            os._exit(1)
    _, status = os.waitpid(pid, 0)
    assert os.waitstatus_to_exitcode(status) == 0
    assert economic(ledger) == ('running', 'running', 'open')
    return inference, ledger


def test_dead_parent_recovers_once(frozen):
    inference, ledger = frozen
    published = []
    assert central.recover_publication(ledger, lambda *args: published.append(args))['recovered']
    assert len(published) == 1
    central.recover_publication(ledger, lambda *_: pytest.fail('Published twice'))
    assert economic(ledger) == ('done', 'finished', 'closed')
    assert task(ledger)['state'] == 'done'
    assert queue.get(inference)['state'] == 'completed'
    assert billing.inspect(inference)['state'] == 'delivered'


@pytest.mark.parametrize('phase', ['before_publish', 'before_settlement', 'after_charge'])
def test_crash_boundaries(frozen, monkeypatch, phase):
    inference, ledger = frozen
    calls = []
    def publish(*args):
        if phase == 'before_publish':
            raise RuntimeError('interrupted')
        calls.append(args[0])
    original = billing.deliver
    def fail(*args, **kwargs):
        if phase == 'before_settlement':
            raise RuntimeError('interrupted')
        return original(*args, **kwargs, on_applied=lambda _: (_ for _ in ()).throw(RuntimeError('ack interrupted')))
    if phase != 'before_publish':
        monkeypatch.setattr(billing, 'deliver', fail)
    with pytest.raises(RuntimeError):
        central.recover_publication(ledger, publish)
    monkeypatch.setattr(billing, 'deliver', original)
    central.recover_publication(ledger, lambda *args: calls.append(args[0]))
    assert calls == [inference]
    assert economic(ledger) == ('done', 'finished', 'closed')


@pytest.mark.parametrize('change', ['alive', 'hidden', 'cancelled', 'retired', 'epoch', 'claim', 'project', 'actor', 'media', 'unmeasured'])
def test_ineligible_recovery_stays_held(frozen, monkeypatch, change):
    inference, ledger = frozen
    if change in ('alive', 'hidden'):
        with queue._db() as c:
            identity = c.execute('SELECT runner_identity FROM jobs WHERE job_id=?', (inference,)).fetchone()[0]
        monkeypatch.setattr(queue, '_process_identity', lambda _: identity if change == 'alive' else '')
    elif change in ('cancelled', 'project', 'actor'):
        with queue._db() as c:
            if change == 'cancelled':
                c.execute('UPDATE jobs SET cancel_requested=1 WHERE job_id=?', (inference,))
            elif change == 'project':
                c.execute("UPDATE jobs SET project_id='other' WHERE job_id=?", (inference,))
            else:
                c.execute("UPDATE jobs SET payload_json='{}' WHERE job_id=?", (inference,))
    elif change in ('retired', 'epoch', 'claim'):
        with auth.db() as c:
            if change == 'retired':
                c.execute('UPDATE users SET active=0')
            elif change == 'epoch':
                c.execute('UPDATE regime_fence_state SET revision=revision+1')
            else:
                c.execute("UPDATE regime_worker_claims SET claim_token='changed'")
    else:
        original = central.recover
        def wrong(*args):
            audio, meta = original(*args)
            meta['media_type' if change == 'media' else 'usage'] = 'application/zip' if change == 'media' else {}
            return audio, meta
        monkeypatch.setattr(central, 'recover', wrong)
    with pytest.raises((FenceBlocked, ValueError)):
        central.recover_publication(ledger, lambda *_: pytest.fail('Ineligible publication'))
    assert economic(ledger)[0] == 'running'
    assert publication.status(inference) is None


def test_conflicting_stage_is_not_overwritten(frozen):
    inference, ledger = frozen
    with pytest.raises(RuntimeError):
        central.recover_publication(ledger, lambda *_: (_ for _ in ()).throw(RuntimeError('stopped')))
    with publication._open() as c:
        c.execute("UPDATE publications SET project_id='other' WHERE job_id=?", (inference,))
    with pytest.raises(FenceBlocked):
        central.recover_publication(ledger, lambda *_: pytest.fail('Wrong project'))
    assert economic(ledger)[0] == 'running'


def test_actual_generation_factory_accepts_pull_cpu_source(frozen, monkeypatch):
    from app import main, ai_server_execution, ai_durable_remote_executor, deferred_execution_owner as owners
    from test_r208_unified_adapter_billing_e2e import source_audio
    inference, ledger = frozen
    with queue._db() as c:
        operation = c.execute('SELECT operation FROM jobs WHERE job_id=?', (inference,)).fetchone()[0]
    monkeypatch.setattr(main, 'load_project', lambda _: object())
    monkeypatch.setattr(main, 'arranger_plan', lambda *_: {'input_source': 'master'})
    monkeypatch.setattr(main, 'prepare_remix_plan', lambda *_: {'input_source': 'master'})
    monkeypatch.setattr(ai_durable_remote_executor, 'render_source', lambda p, x, a, dest: dest.write_bytes(source_audio()))
    monkeypatch.setattr(ai_server_execution, 'enabled', lambda _: True)
    monkeypatch.setattr(ai_server_execution, 'infer', lambda *a, **kw: central.recover(ledger))
    published = []
    monkeypatch.setattr(main, '_publish_durable_generated_audio', lambda *args: published.append(args))
    owner = central.decode(task(ledger)['owner_json'])
    token = owners._CURRENT.set(owners.Owner(inference, ledger, **owner))
    try:
        main._durable_generation_executor('aaaaaaaaaaaa', {'schema_version': 1, 'adapter': operation, 'request': {}}, inference)(None, threading.Event())
    finally:
        owners._CURRENT.reset(token)
    assert len(published) == 1 and published[0][3]['wav']['metering_source'] == 'remote-worker'
    central.recover_publication(ledger, lambda *_: pytest.fail('Published twice'))
    assert economic(ledger) == ('done', 'finished', 'closed')


def test_parallel_recovery_is_idempotent(frozen):
    from concurrent.futures import ThreadPoolExecutor
    inference, ledger = frozen
    published = []
    with ThreadPoolExecutor(3) as pool:
        results = list(pool.map(lambda _: central.recover_publication(ledger, lambda *a: published.append(a[0])), range(3)))
    assert all(r['recovered'] for r in results)
    assert published == [inference]
    assert economic(ledger) == ('done', 'finished', 'closed')


def test_write_boundary_rechecks_retirement_cancel_and_project(frozen):
    inference, ledger = frozen
    assert central.publication_owner(inference, 'aaaaaaaaaaaa') == task(ledger)['user_id']
    with pytest.raises(FenceBlocked):
        central.publication_owner(inference, 'wrong')
    with queue._db() as c:
        c.execute('UPDATE jobs SET cancel_requested=1 WHERE job_id=?', (inference,))
    with pytest.raises(FenceBlocked):
        central.publication_owner(inference, 'aaaaaaaaaaaa')


def test_admin_recovery_api_requires_session_role_csrf_confirmation(frozen, monkeypatch):
    from fastapi.testclient import TestClient
    from app import main
    inference, ledger = frozen
    with auth.db() as c:
        c.execute("INSERT INTO users(username,email,password_hash,role,active,created_at,updated_at) VALUES('recovery-admin','r@example.test','fixture','admin',1,1,1)")
        admin = c.execute("SELECT id FROM users WHERE username='recovery-admin'").fetchone()[0]
    identity = [None]
    monkeypatch.setattr(auth, 'session_user', lambda _: identity[0])
    monkeypatch.setattr(main, 'session_user', lambda _: identity[0])
    client = TestClient(main.app)
    path = '/api/admin/pull-executions/' + ledger + '/recover-publication'
    assert client.post(path, json={'confirm_recover': True}).status_code in (401, 403)
    identity[0] = auth.get_user(task(ledger)['user_id'])
    assert client.post(path, json={'confirm_recover': True}, headers={'X-MTA-Request': '1'}).status_code == 403
    identity[0] = auth.get_user(admin)
    assert client.post(path, json={'confirm_recover': True}).status_code == 403
    assert client.post(path, json={'confirm_recover': False}, headers={'X-MTA-Request': '1'}).status_code == 400
    published = []
    monkeypatch.setattr(main, '_publish_durable_generated_audio', lambda *a: published.append(a[0]))
    r = client.post(path, json={'confirm_recover': True}, headers={'X-MTA-Request': '1'})
    assert r.status_code == 200 and r.json()['execution_replayed'] is False
    assert r.headers['cache-control'] == 'no-store' and published == [inference]
    with auth.db() as c:
        assert c.execute("SELECT actor_id FROM ai_pull_operator_audit WHERE action='publication-recovery'").fetchone()[0] == admin


@pytest.mark.parametrize('owner_changed', [False, True])
def test_real_project_write_and_reopen(frozen, tmp_path, monkeypatch, owner_changed):
    from app import main, storage
    from app.models import Project
    inference, ledger = frozen
    uid = task(ledger)['user_id']
    monkeypatch.setattr(storage, 'ROOT', tmp_path / 'projects')
    monkeypatch.setattr(storage, 'SHARED_MEDIA_ROOT', tmp_path / 'shared')
    monkeypatch.setattr(storage, 'SHARED_AUDIO_ROOT', tmp_path / 'shared/audio')
    monkeypatch.setattr(storage, 'SHARED_INDEX_PATH', tmp_path / 'shared/index.json')
    project = Project(id='aaaaaaaaaaaa', title='Recover', owner_user_id=uid + 1 if owner_changed else uid, project_kind_version=1)
    storage.save_project(project)
    if owner_changed:
        with pytest.raises(ValueError, match='owner changed'):
            central.recover_publication(ledger, main._publish_durable_generated_audio)
        assert not storage.load_project('aaaaaaaaaaaa').tracks
        assert economic(ledger)[0] == 'running'
    else:
        central.recover_publication(ledger, main._publish_durable_generated_audio)
        reopened = storage.load_project('aaaaaaaaaaaa')
        assert len(reopened.tracks) == 1
        assert storage.audio_path('aaaaaaaaaaaa', reopened.tracks[0].filename).is_file()
        central.recover_publication(ledger, main._publish_durable_generated_audio)
        assert len(storage.load_project('aaaaaaaaaaaa').tracks) == 1


def test_concurrent_worker_state_creation_keeps_strict_permissions(authority, monkeypatch):
    from pathlib import Path
    from app import ai_pull_worker as worker
    from test_r210_pull_coordinator import DirectClient
    state = authority[2] / 'racing-state'
    state.mkdir(mode=0o700)
    original = Path.exists
    monkeypatch.setattr(Path, 'exists', lambda p: False if p == state else original(p))
    assert worker.run_once(DirectClient(authority[1]['credential']), state) is False
    state.chmod(0o755)
    with pytest.raises(ValueError, match='owner-only'):
        worker.run_once(DirectClient(authority[1]['credential']), state)
