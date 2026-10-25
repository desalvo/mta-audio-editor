"""Admission, private API, deferred economic owner and erasure integration."""
import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor

from fastapi.testclient import TestClient
import pytest

from app import auth, ai_pull_coordinator as central, ai_pull_worker as worker, ai_billing
from test_r208_unified_adapter_billing_e2e import operator as operator, source_audio  # noqa: F401
from test_r210_pull_coordinator import authority as authority, enqueue, economic, outcome, task, DirectClient  # noqa: F401


def actor(uid):
    return auth.get_user(uid)


@pytest.fixture
def api(authority, monkeypatch):
    from app import main
    with auth.db() as c:
        c.execute("INSERT INTO users(username,email,password_hash,role,active,created_at,updated_at) VALUES('pull-admin','pull@example.test','fixture','admin',1,1,1)")
        admin = c.execute("SELECT id FROM users WHERE username='pull-admin'").fetchone()[0]
    identity = [None]
    monkeypatch.setattr(auth, 'session_user', lambda _: identity[0])
    monkeypatch.setattr(main, 'session_user', lambda _: identity[0])
    return TestClient(main.app), identity, admin


def test_full_middleware_worker_token_is_exactly_scoped(authority, api):
    client, identity, admin = api
    credential = authority[1]['credential']
    h = {'Authorization': 'Bearer ' + credential}
    response = client.post('/api/pull-worker/claim', json={'instance': 'a' * 32}, headers=h)
    assert response.status_code == 200 and response.json() == {'task': None}
    for method, path in [('get','/api/admin/pull-workers'),('get','/api/account/pull-executions'),
                         ('get','/api/models/catalog/private'),('post','/api/ai-jobs/execute'),
                         ('post','/api/admin/pull-workers'),('get','/api/pull-worker/claim')]:
        r = getattr(client, method)(path, headers=h)
        assert r.status_code in (401, 403, 404, 405)
    assert client.post('/api/pull-worker/claim', json={'instance': 'a' * 32}).status_code == 401
    assert credential not in client.get('/api/about').text


def test_admin_register_pause_revoke_role_csrf_and_no_key_readback(authority, api):
    client, identity, admin = api
    identity[0] = actor(authority[0])
    assert client.get('/api/admin/pull-workers').status_code == 403
    identity[0] = actor(admin)
    body = {'name': 'new-node', 'kinds': ['whisper']}
    assert client.post('/api/admin/pull-workers', json=body).status_code == 403
    r = client.post('/api/admin/pull-workers', json=body, headers={'X-MTA-Request': '1'})
    assert r.status_code == 200 and r.headers['cache-control'] == 'no-store'
    node, credential = r.json()['node_id'], r.json()['credential']
    listing = client.get('/api/admin/pull-workers')
    assert credential not in listing.text and 'key_hash' not in listing.text
    r = client.patch('/api/admin/pull-workers/' + node, json={'accepting': False}, headers={'X-MTA-Request': '1'})
    assert r.status_code == 200 and r.json()['quiescence_verified'] is False
    assert client.delete('/api/admin/pull-workers/' + node, headers={'X-MTA-Request': '1'}).status_code == 200
    identity[0] = None
    assert client.post('/api/pull-worker/claim', json={'instance': 'a' * 32}, headers={'Authorization': 'Bearer ' + credential}).status_code == 401


def test_owner_result_is_private_settled_and_not_executable(authority, api):
    client, identity, admin = api
    job = enqueue(authority)
    key = authority[1]['credential']
    grant = central.assignment(key, 'a' * 32)
    identity[0] = actor(authority[0])
    assert client.get('/api/account/pull-executions/' + job + '/result').status_code == 409
    central.complete(key, job, grant['instance'], grant['nonce'], outcome())
    r = client.get('/api/account/pull-executions/' + job + '/result')
    assert r.status_code == 200 and r.content == source_audio()
    assert r.headers['cache-control'] == 'no-store' and r.headers['x-content-type-options'] == 'nosniff'
    listing = client.get('/api/account/pull-executions')
    assert grant['nonce'] not in listing.text and key not in listing.text and 'source' not in listing.text
    identity[0] = actor(admin)
    assert client.get('/api/account/pull-executions/' + job + '/result').status_code == 404


def test_actual_middleware_hides_worker_api_in_native_mode(authority, api, monkeypatch):
    from app import main
    monkeypatch.setattr(main, 'NATIVE_SINGLE_USER', True)
    client = api[0]
    assert client.post('/api/pull-worker/claim', headers={'Authorization': 'Bearer ' + authority[1]['credential']}, json={'instance': 'a' * 32}).status_code == 404


def test_pending_error_is_localized_and_never_claims_stop(authority, api, monkeypatch):
    from app import i18n
    for language, text in [('it','arresto'),('en','termination')]:
        token = i18n.current_language.set(language)
        try:
            d = central.PullPending('a' * 32).detail()
            assert text in d['message'] and not d['worker_stopped'] and not d['execution_replayed']
        finally:
            i18n.current_language.reset(token)


def test_retired_queued_owner_never_transfers_source_and_maintenance_closes_only_undispatched(authority):
    job = enqueue(authority)
    with auth.db() as c:
        c.execute('UPDATE users SET active=0 WHERE id=?', (authority[0],))
        central.request_cancel(c, authority[0])
    assert central.assignment(authority[1]['credential'], 'a' * 32) is None
    central.maintenance()
    assert economic(job) == ('cancelled','finished','closed')


def test_actual_erasure_rejects_active_remote_task_before_writing_journal(authority):
    from app import account_erasure, account_lifecycle as life
    job = enqueue(authority)
    with auth.db() as c:
        c.execute("INSERT INTO users(username,email,password_hash,role,active,created_at,updated_at) VALUES('erasure-admin','erase@example.test','fixture','admin',1,1,1)")
        admin = c.execute("SELECT id FROM users WHERE username='erasure-admin'").fetchone()[0]
        c.execute('UPDATE users SET active=0 WHERE id=?', (authority[0],))
    with pytest.raises(central.PullPending):
        account_erasure.erase(authority[0], admin, confirmed=True)
    assert not (life.root() / ('erase-' + str(authority[0]) + '.json')).exists()
    assert economic(job) == ('running','running','open')


def test_completed_erasure_receipt_drops_private_artifacts_and_acknowledges_lost_reply(authority):
    job = enqueue(authority)
    key = authority[1]['credential']
    grant = central.assignment(key, 'a' * 32)
    central.complete(key, job, grant['instance'], grant['nonce'], outcome())
    with auth.db() as c:
        c.execute('BEGIN IMMEDIATE')
        central.record_erasure(c, authority[0])
        c.execute('DELETE FROM ai_pull_tasks WHERE user_id=?', (authority[0],))
    assert central.complete(key, job, grant['instance'], grant['nonce'], outcome())['acknowledged']
    with auth.db() as c:
        raw = json.dumps([dict(r) for r in c.execute('SELECT * FROM ai_pull_acknowledgements')])
        assert job not in raw and grant['nonce'] not in raw and 'user_id' not in raw


@pytest.mark.parametrize('adapter', ['arranger','remix'])
@pytest.mark.parametrize('billing_enabled', [True,False])
@pytest.mark.parametrize('free_only', [False,True])
def test_pull_executor_preserves_original_deferred_owner_until_publication(authority, monkeypatch, adapter, billing_enabled, free_only):
    from app import ai_arranger_runtime as queue, ai_metering_agent, ai_metering_bridge as bridge
    from app import ai_publish_outbox as publication, ai_billing_outbox as billing
    from app.ai_global_execution import current_job
    from app.deferred_execution_owner import execution_scope
    uid, registration, folder = authority
    ai_billing.set_user_billing_enabled(uid,billing_enabled)
    if free_only:
        from app.model_license_policy import configure
        configure('ace-step',{'mode':'free_only','acknowledge_responsibility':True,'evidence_url':'https://example.org/synthetic-fixture',
            'reason':'Synthetic generated media; no third-party weights used','free_access_confirmed':True},uid)
    job = 'pull_deferred_' + adapter
    queue.start('project1', adapter, None, job_id=job, defer_spawn=True,
                payload={'schema_version': 1, 'actor_user_id': uid, 'adapter': adapter})
    ledger = ai_billing.provision_inference_job(job, uid, adapter)
    assert queue._claim(job)
    result = {}
    def execute():
        with execution_scope(job, threading.Event()) as owner:
            context = current_job.set(job)
            try:
                data, meta = ai_metering_agent.execute_registered_worker(uid, 'ace-step', {}, source_wav=source_audio())
                result.update(data=data, meta=meta, receipt=owner.receipt())
                bridge.capture(job, meta['usage'], meta['metering_source'])
                publication.stage(job, 'project1', data, {'mode': adapter})
            finally:
                current_job.reset(context)
    with ThreadPoolExecutor(1) as pool:
        pending = pool.submit(execute)
        deadline = time.monotonic() + 10
        while not pending.done() and time.monotonic() < deadline:
            if worker.run_once(DirectClient(registration['credential']), folder / 'deferred-node'):
                break
            threading.Event().wait(.02)
        pending.result(timeout=10)
    assert result['meta']['job_id'] == ledger
    assert economic(ledger) == ('running','running','open')
    publication.recover(lambda *_: None, job_id=job)
    bridge.register_settlement(job)
    assert billing.deliver(job_id=job) == 1
    assert economic(ledger) == ('done','finished','closed')
    assert task(ledger)['source'] is None
    with auth.db() as c:
        assert c.execute('SELECT billable FROM ai_compute_jobs WHERE id=?',(ledger,)).fetchone()[0] == int(not free_only)
        if free_only:
            assert c.execute('SELECT reason FROM ai_job_billing_exemptions WHERE job_id=?',(ledger,)).fetchone()[0] == 'license:ace-step'
            exists = c.execute("SELECT 1 FROM sqlite_master WHERE name='resource_job_contracts'").fetchone()
            assert not exists or not c.execute('SELECT 1 FROM resource_job_contracts WHERE job_id=?',(ledger,)).fetchone()


def test_commercial_remote_and_path_injection_are_denied_before_admission(authority):
    from pathlib import Path
    from app import model_license_policy
    with pytest.raises(ValueError):
        central.enqueue(authority[0], 'whisper', {'options': {'command': '/bin/true'}})
    path = Path(auth.data_root()) / 'service-regime.json'
    path.write_text('{"regime":"COMMERCIAL","revision":0}')
    from app.regime_operation_fence import initialize
    with auth.db() as c:
        c.execute('BEGIN IMMEDIATE')
        initialize(c, initial_regime='COMMERCIAL')
    with pytest.raises(model_license_policy.LicenseDenied, match='attestation'):
        enqueue(authority)
    with auth.db() as c:
        assert c.execute('SELECT COUNT(*) FROM ai_compute_jobs').fetchone()[0] == 0


@pytest.mark.parametrize('transport', ['audio','json'])
def test_actual_ai_token_submission_uses_pull_without_local_authority_adapter(authority, api, monkeypatch, transport):
    from app import ai_access
    from app.ai_worker_registry import resolve_worker, execution_available
    token = ai_access.issue(authority[0], 'pull API fixture')['token']
    headers = {'Authorization': 'Bearer ' + token, 'X-MTA-AI-Idempotency-Key': 'pull-api-submission-' + transport}
    client = api[0]
    # Source is independently configured on the worker; local resolution on the
    # authority must not be a prerequisite for the network-backed execution.
    monkeypatch.delenv('MTA_AI_WORKER_WHISPER_EXECUTABLE')
    assert resolve_worker('whisper') is None and execution_available('whisper')
    with ThreadPoolExecutor(1) as pool:
        if transport == 'audio':
            pending = pool.submit(client.post, '/api/ai-jobs/execute-audio/whisper', content=source_audio(),
                                  headers={**headers, 'Content-Type': 'audio/wav'})
        else:
            pending = pool.submit(client.post, '/api/ai-jobs/execute', json={'kind': 'whisper', 'plan': {}}, headers=headers)
        deadline = time.monotonic() + 10
        while not pending.done() and time.monotonic() < deadline:
            grant = central.assignment(authority[1]['credential'], 'a' * 32)
            if grant:
                central.complete(authority[1]['credential'], grant['job_id'], grant['instance'], grant['nonce'], outcome())
                break
            threading.Event().wait(.02)
        response = pending.result(timeout=10)
    assert response.status_code == 200, response.text
    with auth.db() as c:
        assert c.execute("SELECT COUNT(*) FROM ai_compute_jobs WHERE status='done'").fetchone()[0] == 1


def test_admin_drain_requires_confirmation_generation_and_durable_audit(authority, api):
    client, identity, admin = api
    identity[0] = actor(admin)
    headers = {'X-MTA-Request': '1'}
    url = '/api/admin/pull-workers/drain'
    body = {'accepting': False, 'expected_generation': 0, 'confirm': True}
    assert client.post(url, json={**body, 'confirm': False}, headers=headers).status_code == 400
    assert client.post(url, json=body, headers=headers).status_code == 200
    assert client.post(url, json=body, headers=headers).status_code == 409
    with auth.db() as c:
        audit = c.execute("SELECT actor_id,action,detail_json FROM ai_pull_operator_audit WHERE action='admission-drain'").fetchall()
        assert len(audit) == 1 and tuple(audit[0])[:2] == (admin, 'admission-drain')
        assert json.loads(audit[0][2]) == {'generation': 1, 'previous_generation': 0}


def test_actual_retired_account_confirmation_erases_pull_payload_and_recovers_lost_node_ack(authority, api, monkeypatch):
    from app import account_lifecycle as life, storage
    monkeypatch.setattr(storage, 'ROOT', authority[2] / 'projects')
    storage.ROOT.mkdir()
    uid = authority[0]
    job = enqueue(authority)
    client = DirectClient(authority[1]['credential'])
    original = client.call
    def lose_ack(action, body, **kwargs):
        result = original(action, body, **kwargs)
        if action == 'complete':
            raise OSError('completion acknowledgement lost')
        return result
    client.call = lose_ack
    node_state = authority[2] / 'real-erasure-node'
    with pytest.raises(OSError):
        worker.run_once(client, node_state)
    life.register(uid)
    life.retire(uid, api[2])
    assert life.confirmation(api[2], uid, {'confirm': True})['done']
    assert auth.get_user(uid) is None
    with auth.db() as c:
        assert c.execute('SELECT COUNT(*) FROM ai_pull_tasks').fetchone()[0] == 0
        assert c.execute('SELECT COUNT(*) FROM ai_compute_jobs WHERE id=?', (job,)).fetchone()[0] == 0
        assert c.execute('SELECT COUNT(*) FROM ai_pull_acknowledgements').fetchone()[0] == 1
    client.call = original
    assert worker.run_once(client, node_state)
    assert json.loads((node_state / 'active.json').read_text()) == {'phase': 'done','binding': client.binding}


@pytest.mark.parametrize('status',['failed','cancelled'])
def test_known_failed_deferred_completion_settles_original_owner_without_publication(authority,status):
    from app import ai_arranger_runtime as queue
    from app.ai_global_execution import current_job
    from app.deferred_execution_owner import execution_scope
    job = 'deferred_terminal_' + status
    queue.start('project1','arranger',None,job_id=job,defer_spawn=True,
                payload={'schema_version':1,'actor_user_id':authority[0],'adapter':'arranger'})
    ledger = ai_billing.provision_inference_job(job,authority[0],'arranger')
    assert queue._claim(job)
    with execution_scope(job,threading.Event()):
        context = current_job.set(job)
        try:
            assert central.enqueue(authority[0],'ace-step',{},source_wav=source_audio()) == ledger
        finally:
            current_job.reset(context)
        grant = central.assignment(authority[1]['credential'],'a'*32)
        terminal = {'status':status,'cpu_seconds':1.25,'media_type':None,'result_b64':''}
        central.complete(authority[1]['credential'],ledger,grant['instance'],grant['nonce'],terminal)
    assert economic(ledger) == (status,'finished','closed')
    assert task(ledger)['state'] == 'done'
    assert central.recover(ledger)[1]['usage'] == {'cpu_seconds':1.25}
