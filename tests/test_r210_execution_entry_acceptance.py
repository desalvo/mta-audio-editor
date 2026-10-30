"""Original owner at every dispatch and exact CPU on actual cancellation."""
import io
import json
import os
import sys
import threading
import time
import wave
from concurrent.futures import ThreadPoolExecutor

import pytest

from app import ai_access, ai_global_execution as execution
from app import ai_arranger_runtime as queue, ai_metering_agent as agent, auth
from test_r210_queue_identity_stem_metering import env as env  # noqa: F401

KINDS = sorted({
    'ace-step', 'arranger', 'remix', 'whisper', 'demucs', 'singer-separation',
    'backing-vocals', 'drumsep', 'sam-audio', 'chords-ml', 'markers',
    'audio-to-midi', 'audio-to-midi-basic-pitch', 'audio-to-midi-yourmt3',
    'audio-to-midi-mr-mt3', 'audio-to-midi-transkun', 'vocal-harmony', 'vocal-synthesis',
})


@pytest.fixture
def registered(env, tmp_path, monkeypatch, synthetic_worker_resolution):
    """Real generated process for ownership/metering; no model identity claim."""
    from app import ai_worker_registry, studio_catalog
    worker = tmp_path / 'owned_worker.py'
    marker = tmp_path / 'executions.jsonl'
    worker.write_text('''import argparse,json,os,pathlib,time,wave
p=argparse.ArgumentParser();p.add_argument('--request');p.add_argument('--output');a=p.parse_args()
request=json.loads(pathlib.Path(a.request).read_text())
policy=json.loads(os.environ['MTA_AI_ADMITTED_POLICY'])
assert policy['kind']==request['kind']
with open(''' + repr(str(marker)) + ''','a') as f:f.write(json.dumps({'kind':request['kind'],'policy':policy['decision']['model_id'],'pid':os.getpid()})+'\\n')
end=time.monotonic()+.06
while time.monotonic()<end:sum(range(1000))
with wave.open(a.output,'wb') as w:
 w.setnchannels(1);w.setsampwidth(2);w.setframerate(44100);w.writeframes(b'\\0\\0'*441)
''')
    worker.chmod(0o700)
    monkeypatch.setattr(studio_catalog, 'root', lambda: tmp_path / 'models')
    monkeypatch.setenv('MTA_AI_WORKER_ENABLED', 'true')
    monkeypatch.delenv('MTA_AI_CGROUP_PARENT', raising=False)
    monkeypatch.setenv('MTA_AI_RESULT_CACHE_DIR', str(tmp_path / 'cache'))
    for kind in KINDS:
        monkeypatch.setenv('MTA_AI_WORKER_' + kind.upper().replace('-', '_') + '_EXECUTABLE', str(worker))
        monkeypatch.setenv('MTA_AI_WORKER_' + kind.upper().replace('-', '_') + '_PYTHON', sys.executable)
    assert set(KINDS) == set(ai_worker_registry.registered_kinds())
    return worker, marker


def audio():
    out = io.BytesIO()
    with wave.open(out, 'wb') as handle:
        handle.setnchannels(1); handle.setsampwidth(2); handle.setframerate(44100)
        handle.writeframes(b'\0\0' * 441)
    return out.getvalue()


def test_internal_registered_entry_requires_actual_scheduler_owner(env, monkeypatch):
    monkeypatch.setattr('app.ai_worker_registry.resolve_worker',
                        lambda _: pytest.fail('Unowned worker resolved'))
    with pytest.raises(ValueError, match='Authenticated active'):
        agent._execute_registered_worker(env, 'markers', {})
    with auth.db() as con:
        assert con.execute('SELECT count(*) FROM ai_compute_jobs').fetchone()[0] == 0


def test_revoked_token_cannot_dispatch_from_an_original_running_queue(env, monkeypatch):
    token = ai_access.issue(env, 'revoked while waiting')
    ai_access.revoke(token['id'])
    def forbidden(_):
        raise AssertionError('Revoked token resolved a worker')
    monkeypatch.setattr('app.ai_worker_registry.resolve_worker', forbidden)
    with pytest.raises(ValueError, match='execution identity'):
        execution.execute(env, 'markers', lambda _: agent._execute_registered_worker(
            env, 'markers', {}, token_id=token['id']))
    with auth.db() as con:
        assert con.execute('SELECT count(*) FROM ai_compute_jobs').fetchone()[0] == 0


def test_actual_cancelled_child_preserves_reaped_cpu_and_no_artifact(tmp_path):
    marker = tmp_path / 'pid'
    program = ('from pathlib import Path\nimport os,time\n'
               'Path(' + repr(str(marker)) + ').write_text(str(os.getpid()))\n'
               'deadline=time.monotonic()+.15\n'
               'while time.monotonic()<deadline:sum(range(1000))\n'
               'Path("ready").touch()\nwhile True:sum(range(1000))\n')
    with pytest.raises(RuntimeError, match='cancelled during execution') as caught:
        agent.run_metered_process([sys.executable, '-c', program], cwd=str(tmp_path),
                                  cancel_check=lambda: (tmp_path / 'ready').exists())
    measurement = caught.value.measurement
    assert measurement.exit_code != 0 and measurement.usage['cpu_seconds'] > 0
    assert measurement.pid == int(marker.read_text())
    with pytest.raises(ProcessLookupError): os.kill(measurement.pid, 0)
    with pytest.raises(ChildProcessError): os.waitpid(measurement.pid, os.WNOHANG)


def api():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.ai_billing_routes import router
    app = FastAPI(); app.include_router(router)
    return TestClient(app)


@pytest.mark.parametrize('kind', KINDS)
def test_every_builtin_kind_actual_api_process_owner_meter_and_replay(env, registered, tmp_path, monkeypatch, kind):
    from app import model_license_policy as rights
    plan = {'kind': kind}
    if kind == 'backing-vocals': plan['model'] = 'mvsep-mega53'
    if kind == 'drumsep': plan['model'] = 'dsp'
    if kind == 'chords-ml': plan['engine'] = 'profile-fast'
    if kind == 'audio-to-midi-transkun':
        from test_r210_managed_execution_identity import install_at
        install_at(tmp_path / 'models', monkeypatch)
        plan['options'] = {'asset_id': 'identity-piano'}
    if kind == 'audio-to-midi-mr-mt3':
        rights.configure('mr-mt3-assets', {'mode': 'free_only', 'acknowledge_responsibility': True,
            'evidence_url': 'https://example.test/synthetic', 'reason': 'Synthetic worker contract fixture only',
            'free_access_confirmed': True, 'authorization_basis': 'written_permission',
            'confirm_risk_twice': True}, env)
    decision = rights.evaluate(kind, plan)
    token = ai_access.issue(env, 'original caller')
    with auth.db() as con:
        con.execute("INSERT INTO users(username,email,password_hash,role,active,email_confirmed,created_at,updated_at) VALUES('foreign','foreign@example.test','unused','user',1,1,1,1)")
        other = con.execute("SELECT id FROM users WHERE username='foreign'").fetchone()[0]
    foreign = ai_access.issue(other, 'other caller')
    key = 'entry-acceptance-' + kind
    headers = {'Authorization': 'Bearer ' + token['token'], 'X-MTA-AI-Idempotency-Key': key}
    with api() as client:
        response = client.post('/api/ai-jobs/execute', json={'kind': kind, 'plan': plan}, headers=headers)
        assert response.status_code == 200, response.text
        jid = response.headers['x-mta-ai-job-id']
        replay = client.get('/api/ai-jobs/request-result/' + key, headers=headers)
        assert replay.status_code == 200 and replay.content == response.content
        assert client.get('/api/ai-jobs/resources/' + jid,
            headers={'Authorization': 'Bearer ' + foreign['token']}).status_code == 404
        duplicate = client.post('/api/ai-jobs/execute', json={'kind': kind, 'plan': plan}, headers=headers)
        assert duplicate.status_code == 409
    rows = [json.loads(line) for line in registered[1].read_text().splitlines()]
    assert len(rows) == 1 and rows[0]['kind'] == kind
    with auth.db() as con:
        row = con.execute('SELECT * FROM ai_compute_jobs WHERE id=?', (jid,)).fetchone()
        assert row['user_id'] == env and row['token_id'] == token['id'] and row['kind'] == kind
        assert row['status'] == 'done' and row['resource_source'] == 'worker'
        assert json.loads(row['usage_json'])['cpu_seconds'] > 0
        assert row['billable'] == int(decision.billable)
        assert con.execute('SELECT state FROM regime_worker_claims WHERE operation_id=?',
                           ('job:ledger:' + jid,)).fetchone()[0] == 'finished'
        assert con.execute('SELECT status FROM regime_fence_operations WHERE operation_id=?',
                           ('job:ledger:' + jid,)).fetchone()[0] == 'closed'
        license_row = con.execute('SELECT policy_json FROM ai_job_license_snapshots WHERE job_id=?', (jid,)).fetchone()
        assert json.loads(license_row[0])['policy_sha256'] == decision.policy_sha256
    assert queue.get(row['queue_job_id'])['actor_user_id'] == env
    assert queue.get(row['queue_job_id'])['state'] == 'completed'


@pytest.mark.parametrize('change', ['revoke', 'foreign', 'inactive'])
def test_actual_api_queue_wait_rechecks_original_credential_before_dispatch(env, registered, change):
    hold = threading.Event(); entered = threading.Event()
    token = ai_access.issue(env, 'waiting caller')
    def block(_):
        entered.set(); assert hold.wait(10)
    try:
        with ThreadPoolExecutor(2) as pool, api() as client:
            first = pool.submit(execution.execute, env, 'markers', block)
            assert entered.wait(5)
            second = pool.submit(client.post, '/api/ai-jobs/execute',
                json={'kind': 'markers', 'plan': {}}, headers={'Authorization': 'Bearer ' + token['token']})
            deadline = time.monotonic() + 5
            while len(queue.list_jobs()) < 2 and time.monotonic() < deadline: time.sleep(.01)
            assert len(queue.list_jobs()) == 2
            with auth.db() as con:
                if change == 'revoke':
                    con.execute('UPDATE ai_access_tokens SET revoked_at=1 WHERE id=?', (token['id'],))
                elif change == 'foreign':
                    con.execute("INSERT INTO users(username,email,password_hash,role,active,email_confirmed,created_at,updated_at) VALUES('foreign','foreign@example.test','unused','user',1,1,1,1)")
                    foreign = con.execute("SELECT id FROM users WHERE username='foreign'").fetchone()[0]
                    con.execute('UPDATE ai_access_tokens SET user_id=? WHERE id=?', (foreign, token['id']))
                else:
                    con.execute('UPDATE users SET active=0 WHERE id=?', (env,))
            hold.set(); first.result(5)
            response = second.result(10)
            assert response.status_code == 400, response.text
            assert 'Active AI execution identity required' in response.text
    finally: hold.set()
    assert not registered[1].exists()
    with auth.db() as con:
        assert con.execute('SELECT count(*) FROM ai_compute_jobs').fetchone()[0] == 0


@pytest.mark.parametrize('key', ['source_score', 'source_audio', 'input_path', 'output_path', 'command', 'executable', 'cwd', 'shell'])
def test_json_entry_rejects_nested_worker_control_before_queue(env, registered, key):
    token = ai_access.issue(env, 'invalid plan')
    with api() as client:
        response = client.post('/api/ai-jobs/execute', headers={'Authorization': 'Bearer ' + token['token']},
            json={'kind': 'markers', 'plan': {'options': {'deeper': [{key: '/private/not-readable'}]}}})
    assert response.status_code == 400 and '/private/not-readable' not in response.text
    assert queue.list_jobs() == [] and not registered[1].exists()


def test_malformed_wav_never_creates_a_ledger_or_claim(env, registered):
    with pytest.raises(ValueError, match='WAV'):
        agent.execute_registered_worker(env, 'markers', {}, source_wav=b'not a private WAV')
    assert not registered[1].exists()
    with auth.db() as con:
        assert con.execute('SELECT count(*) FROM ai_compute_jobs').fetchone()[0] == 0


def test_unverifiable_process_tree_keeps_original_claim_without_publication(env, registered, monkeypatch):
    from dataclasses import replace
    original = agent.run_supervised_process
    def unverified(*args, **kwargs):
        return replace(original(*args, **kwargs), isolated=False, tree_complete=False)
    monkeypatch.setattr(agent, 'run_supervised_process', unverified)
    with pytest.raises(agent.WorkerUncertain, match='original owner retained'):
        agent.execute_registered_worker(env, 'markers', {})
    assert len(registered[1].read_text().splitlines()) == 1
    with auth.db() as con:
        row = con.execute('SELECT id,status,finished_at,usage_json FROM ai_compute_jobs').fetchone()
        assert row['status'] == 'running' and row['finished_at'] is None and json.loads(row['usage_json']) == {}
        assert con.execute('SELECT state FROM regime_worker_claims WHERE operation_id=?',
                           ('job:ledger:' + row['id'],)).fetchone()[0] == 'running'
        assert con.execute('SELECT status FROM regime_fence_operations WHERE operation_id=?',
                           ('job:ledger:' + row['id'],)).fetchone()[0] == 'open'


def test_running_token_revocation_stops_actual_process_and_retains_measured_cpu(env, registered):
    worker, marker = registered
    worker.write_text('import pathlib,os,time\npathlib.Path(' + repr(str(marker))
        + ').write_text(str(os.getpid()))\nwhile True:sum(range(1000))\n')
    token = ai_access.issue(env, 'running caller')
    with ThreadPoolExecutor(1) as pool:
        work = pool.submit(agent.execute_registered_worker, env, 'markers', {}, token_id=token['id'])
        deadline = time.monotonic() + 5
        while not marker.exists() and time.monotonic() < deadline: time.sleep(.01)
        assert marker.exists()
        ai_access.revoke(token['id'])
        with pytest.raises(agent.WorkerInterrupted): work.result(7)
    pid = int(marker.read_text())
    with pytest.raises(ProcessLookupError): os.kill(pid, 0)
    with auth.db() as con:
        row = con.execute('SELECT id,status,resource_source,usage_json FROM ai_compute_jobs').fetchone()
        assert row['status'] == 'cancelled' and row['resource_source'] == 'worker'
        assert json.loads(row['usage_json'])['cpu_seconds'] > 0
        assert con.execute('SELECT state FROM regime_worker_claims WHERE operation_id=?',
                           ('job:ledger:' + row['id'],)).fetchone()[0] == 'finished'


@pytest.mark.parametrize('transport', ['json', 'wav'])
@pytest.mark.parametrize('uncertainty', ['tree', 'sensor'])
def test_pending_evidence_api_is_private_retains_identity_and_never_reexecutes(env, registered, monkeypatch, transport, uncertainty):
    token = ai_access.issue(env, 'uncertain worker')
    if uncertainty == 'tree':
        from dataclasses import replace
        original = agent.run_supervised_process
        monkeypatch.setattr(agent, 'run_supervised_process', lambda *a, **kw: replace(original(*a, **kw), isolated=False, tree_complete=False))
    else:
        run = agent.run_supervised_process
        def broken_probe(argv, **kwargs):
            run(argv, **kwargs)
            raise agent.WorkerUncertain('Original guardian result channel lost')
        monkeypatch.setattr(agent, 'run_supervised_process', broken_probe)
    key = 'pending-evidence-' + transport + '-' + uncertainty
    headers = {'Authorization': 'Bearer ' + token['token'], 'X-MTA-AI-Idempotency-Key': key}
    with api() as client:
        def submit():
            if transport == 'json':
                return client.post('/api/ai-jobs/execute', headers=headers, json={'kind': 'markers', 'plan': {}})
            return client.post('/api/ai-jobs/execute-audio/markers',
                headers={**headers, 'Content-Type': 'audio/wav'}, content=audio())
        response = submit()
        assert response.status_code == 409, response.text
        detail = response.json()['detail']
        assert detail['reason'] == 'worker_evidence_pending' and detail['retry_execution'] is False
        jid = detail['job_id']
        assert jid and response.headers['cache-control'] == 'private, no-store'
        current = client.get('/api/ai-jobs/request-status/' + key, headers=headers).json()
        assert current['state'] == 'admitted'
        assert submit().status_code == 409
        resources = client.get('/api/ai-jobs/resources/' + jid, headers=headers).json()
        assert resources['status'] == 'running' and resources['resource_quality'] == 'unverified'
    rows = [json.loads(line) for line in registered[1].read_text().splitlines()]
    assert len(rows) == 1
    with pytest.raises(ProcessLookupError): os.kill(rows[0]['pid'], 0)
    with auth.db() as con:
        row = con.execute('SELECT status,finished_at,usage_json FROM ai_compute_jobs WHERE id=?', (jid,)).fetchone()
        assert tuple(row) == ('running', None, '{}')
        assert con.execute('SELECT state FROM regime_worker_claims WHERE operation_id=?',
                           ('job:ledger:' + jid,)).fetchone()[0] == 'running'
        from app.regime_operation_fence import inspect
        assert inspect(con)['open_by_kind']['job'] == 1


def test_operator_extension_cannot_bypass_the_same_owner_metering_contract(env, registered, tmp_path, monkeypatch):
    from app import model_license_policy as rights
    config = tmp_path / 'engines.json'
    config.write_text(json.dumps([{'kind': 'fixture-engine', 'executable': str(registered[0]), 'python': sys.executable}]))
    monkeypatch.setenv('MTA_AI_ENGINE_REGISTRY_FILE', str(config))
    with pytest.raises(rights.LicenseDenied): agent.execute_registered_worker(env, 'fixture-engine', {})
    assert not registered[1].exists()
    rights.configure('fixture-engine', {'mode': 'free_only', 'acknowledge_responsibility': True,
        'evidence_url': 'https://example.test/synthetic', 'reason': 'Synthetic operator extension fixture only',
        'free_access_confirmed': True, 'authorization_basis': 'written_permission',
        'confirm_risk_twice': True}, env)
    _, meta = agent.execute_registered_worker(env, 'fixture-engine', {})
    assert meta['usage']['cpu_seconds'] > 0 and meta['billable'] is False
    with auth.db() as con:
        row = con.execute('SELECT user_id,kind,status,billable FROM ai_compute_jobs WHERE id=?', (meta['job_id'],)).fetchone()
        assert tuple(row) == (env, 'fixture-engine', 'done', 0)


@pytest.mark.parametrize('transport', ['json', 'wav'])
def test_running_revocation_returns_private_api_cancellation_instead_of_server_error(env, registered, transport):
    worker, marker = registered
    worker.write_text('import pathlib,os\npathlib.Path(' + repr(str(marker))
        + ').write_text(str(os.getpid()))\nwhile True:sum(range(1000))\n')
    token = ai_access.issue(env, 'revocation response')
    headers = {'Authorization': 'Bearer ' + token['token'],
               'X-MTA-AI-Idempotency-Key': 'revocation-api-' + transport}
    with api() as client, ThreadPoolExecutor(1) as pool:
        if transport == 'json':
            work = pool.submit(client.post, '/api/ai-jobs/execute', headers=headers,
                               json={'kind': 'markers', 'plan': {}})
        else:
            work = pool.submit(client.post, '/api/ai-jobs/execute-audio/markers',
                headers={**headers, 'Content-Type': 'audio/wav'}, content=audio())
        deadline = time.monotonic() + 5
        while not marker.exists() and time.monotonic() < deadline: time.sleep(.01)
        assert marker.exists(); ai_access.revoke(token['id'])
        response = work.result(7)
    assert response.status_code == 409, response.text
    assert response.json()['detail'] == {'reason': 'worker_cancelled', 'retry_execution': False}
    assert response.headers['cache-control'] == 'private, no-store'
    from app.ai_request_dedup import request_status
    assert request_status(env, 'revocation-api-' + transport)['state'] == 'cancelled'
    with pytest.raises(ProcessLookupError): os.kill(int(marker.read_text()), 0)


@pytest.mark.parametrize('transport', ['json', 'wav'])
def test_cancel_between_ledger_admission_and_popen_has_typed_private_response(env, registered, monkeypatch, transport):
    from app import ai_worker_registry, ai_request_dedup as dedup
    token = ai_access.issue(env, 'prelaunch cancellation')
    key = 'prelaunch-cancellation-' + transport
    python = ai_worker_registry.worker_python
    def cancel_before_claim(kind):
        dedup.cancel_admitted(env, key)
        return python(kind)
    monkeypatch.setattr(ai_worker_registry, 'worker_python', cancel_before_claim)
    headers = {'Authorization': 'Bearer ' + token['token'], 'X-MTA-AI-Idempotency-Key': key}
    with api() as client:
        if transport == 'json':
            response = client.post('/api/ai-jobs/execute', headers=headers, json={'kind': 'markers', 'plan': {}})
        else:
            response = client.post('/api/ai-jobs/execute-audio/markers',
                headers={**headers, 'Content-Type': 'audio/wav'}, content=audio())
    assert response.status_code == 409 and response.json()['detail']['reason'] == 'worker_cancelled'
    assert response.headers['cache-control'] == 'private, no-store'
    assert not registered[1].exists() and dedup.request_status(env, key)['state'] == 'cancelled'
    with auth.db() as con:
        row = con.execute('SELECT status,usage_json,resource_source FROM ai_compute_jobs').fetchone()
        assert tuple(row) == ('cancelled', '{}', 'unmetered')
