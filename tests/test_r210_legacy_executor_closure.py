"""Actual ownership migration and bounded legacy/native subprocess acceptance."""
import json
import os
from pathlib import Path
import threading
import time
from types import SimpleNamespace
import wave

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app import ai_gateway, ai_worker_protocol as legacy, native_ai_routing, native_ai_account
from test_r210_queue_identity_stem_metering import env as env  # noqa: F401


@pytest.mark.parametrize('entry', ['external', 'project', 'routing', 'arranger'])
@pytest.mark.parametrize('flag', ['', 'false', '1'])
def test_server_cannot_use_native_credentials_or_legacy_worker(monkeypatch, entry, flag):
    monkeypatch.setenv('MTA_NATIVE_SINGLE_USER', flag)
    monkeypatch.setenv('MTA_ALLOW_INSECURE_NO_AUTH', 'true')
    monkeypatch.setattr(legacy, 'configured_worker', lambda: pytest.fail('Worker resolved before native identity'))
    monkeypatch.setattr(native_ai_routing, '_read', lambda: pytest.fail('Native credentials read by server'))
    monkeypatch.setattr(native_ai_account, 'credentials', lambda: pytest.fail('Native credentials read by server'))
    def source(*args): pytest.fail('Source read by server')
    with pytest.raises(ValueError, match='native application'):
        if entry == 'external': legacy.run_external_worker({})
        elif entry == 'project': legacy.run_worker_with_project_audio({}, None, source)
        elif entry == 'routing': native_ai_routing.infer('whisper', Path('/missing.wav'))
        else: native_ai_account.execute_arranger({}, None, source)


@pytest.mark.parametrize('entry', ['external', 'project'])
def test_native_legacy_policy_denial_precedes_worker_and_source(monkeypatch, entry):
    from app import model_license_policy as rights
    monkeypatch.setenv('MTA_NATIVE_SINGLE_USER', 'true')
    monkeypatch.setattr(rights, 'overrides', lambda: {'ace-step': {'mode': 'disabled'}})
    monkeypatch.setattr(legacy, 'configured_worker', lambda: pytest.fail('Denied model resolved'))
    with pytest.raises(rights.LicenseDenied):
        if entry == 'external': legacy.run_external_worker({})
        else: legacy.run_worker_with_project_audio({}, None, lambda *a: pytest.fail('Denied source read'))


@pytest.mark.parametrize('method,path', [
    ('POST', 'release_task'), ('POST', 'v1/init'), ('POST', 'v1/generate'),
    ('POST', 'v1/audio'), ('POST', 'v1/models'), ('POST', 'query_result'), ('GET', 'v1/audio')])
def test_nc_gateway_rejects_unowned_work_and_result_reads_before_transport(monkeypatch, method, path):
    from app import service_regime
    monkeypatch.setattr(service_regime, 'current_regime', lambda: service_regime.Regime.NON_COMMERCIAL)
    app = FastAPI(); app.include_router(ai_gateway.router)
    monkeypatch.setattr(ai_gateway.ai_access, 'authenticate', lambda _: {'id': 1, 'user_id': 2})
    monkeypatch.setattr(ai_gateway.ai_access, 'usage', lambda *a: pytest.fail('Proxy attempted work'))
    monkeypatch.setattr(httpx, 'AsyncClient', lambda *a, **k: pytest.fail('Unowned upstream transport'))
    with TestClient(app) as client:
        response = client.request(method, '/api/ai-gateway/' + path,
            headers={'Authorization': 'Bearer private-test-token'}, json={'task_id': 'foreign-upstream-task'})
    assert response.status_code == 409, response.text
    assert response.headers['cache-control'] == 'private, no-store'
    assert response.json()['detail']['reason'] == 'accounted_ai_endpoint_required'
    assert 'foreign-upstream-task' not in response.text and 'private-test-token' not in response.text


@pytest.mark.parametrize('transport', ['json', 'wav'])
def test_actual_accounted_api_still_runs_once_replays_and_keeps_foreign_user_out(env, tmp_path, monkeypatch, transport):
    from app import auth, ai_billing, ai_access, ai_billing_routes, ai_metering_agent
    from app import ai_worker_registry
    marker = tmp_path / 'executions'
    worker = tmp_path / 'owned.py'
    worker.write_text('''import argparse, pathlib, wave, time
p=argparse.ArgumentParser();p.add_argument('--request');p.add_argument('--output');a=p.parse_args()
with open(''' + repr(str(marker)) + ''','a') as f:f.write('executed\\n')
end=time.monotonic()+.08
while time.monotonic()<end:sum(range(1000))
with wave.open(a.output,'wb') as w:
 w.setnchannels(1);w.setsampwidth(2);w.setframerate(44100);w.writeframes(b'\\0\\0'*441)
''')
    worker.chmod(0o700)
    monkeypatch.setattr(ai_worker_registry, 'resolve_worker', lambda kind: worker)
    monkeypatch.setattr(ai_metering_agent, '_descendants', lambda pid: set())
    monkeypatch.delenv('MTA_AI_CGROUP_PARENT', raising=False)
    monkeypatch.setenv('MTA_AI_RESULT_CACHE_DIR', str(tmp_path / 'cache'))
    ai_billing.set_user_billing_enabled(env, True)
    ai_billing.set_price('cpu_seconds', 1000000, valid_from=1)
    first = ai_access.issue(env, 'Original owner')['token']
    with auth.db() as c:
        c.execute("INSERT INTO users(username,email,password_hash,role,active,email_confirmed,created_at,updated_at) VALUES('foreign','foreign@example.test','unused','user',1,1,1,1)")
        other = c.execute("SELECT id FROM users WHERE username='foreign'").fetchone()[0]
    foreign = ai_access.issue(other, 'Other owner')['token']
    app = FastAPI(); app.include_router(ai_billing_routes.router)
    key = 'original-accounted-request-12345'
    headers = {'Authorization': 'Bearer ' + first, 'X-MTA-AI-Idempotency-Key': key}
    def execute(client):
        if transport == 'json':
            return client.post('/api/ai-jobs/execute', headers=headers, json={'kind': 'ace-step', 'plan': {}})
        import io
        source = io.BytesIO()
        with wave.open(source, 'wb') as w:
            w.setnchannels(1); w.setsampwidth(2); w.setframerate(44100); w.writeframes(b'\0\0' * 441)
        return client.post('/api/ai-jobs/execute-audio/ace-step',
            headers={**headers, 'Content-Type': 'audio/wav'}, content=source.getvalue())
    with TestClient(app) as client:
        response = execute(client)
        assert response.status_code == 200, response.text
        jid = response.headers['x-mta-ai-job-id']
        replay = client.get('/api/ai-jobs/request-result/' + key, headers=headers)
        assert replay.status_code == 200 and replay.content == response.content
        assert client.get('/api/ai-jobs/request-result/' + key,
            headers={'Authorization': 'Bearer ' + foreign}).status_code == 404
        duplicate = execute(client)
        assert duplicate.status_code == 409
    assert marker.read_text().splitlines() == ['executed']
    with auth.db() as c:
        row = c.execute('SELECT user_id,status,resource_source,usage_json,queue_job_id FROM ai_compute_jobs WHERE id=?', (jid,)).fetchone()
        assert row['user_id'] == env and row['status'] == 'done' and row['queue_job_id']
        assert row['resource_source'] == 'worker' and json.loads(row['usage_json'])['cpu_seconds'] > 0
        assert c.execute('SELECT state FROM regime_worker_claims WHERE operation_id=?', ('job:ledger:' + jid,)).fetchone()[0] == 'finished'


@pytest.mark.parametrize('boundary', ['timeout', 'cancel'])
def test_native_project_worker_ignoring_sigterm_is_killed_and_reaped(tmp_path, monkeypatch, boundary):
    monkeypatch.setenv('MTA_NATIVE_SINGLE_USER', 'true')
    monkeypatch.delenv('MTA_AI_CGROUP_PARENT', raising=False)
    source = tmp_path / 'source.wav'
    with wave.open(str(source), 'wb') as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(44100); w.writeframes(b'\0\0' * 441)
    marker = tmp_path / 'pid'
    worker = tmp_path / 'stubborn.py'
    worker.write_text('import signal,time,os,pathlib\nsignal.signal(signal.SIGTERM,signal.SIG_IGN)\n'
        + 'pathlib.Path(' + repr(str(marker)) + ').write_text(str(os.getpid()))\nwhile True:time.sleep(.02)\n')
    worker.chmod(0o700)
    monkeypatch.setattr(legacy, 'configured_worker', lambda: worker)
    from app import ai_execution_limits
    monkeypatch.setattr(ai_execution_limits, 'inference_timeout', lambda *a: 1)
    event = threading.Event()
    def cancel_after_start():
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline and not marker.exists(): time.sleep(.01)
        if boundary == 'cancel': event.set()
    trigger = threading.Thread(target=cancel_after_start); trigger.start()
    started = time.monotonic()
    try:
        with pytest.raises(legacy.WorkerUnavailable, match='cancelled|timed out'):
            legacy.run_worker_with_project_audio({'scope': 'project'},
                SimpleNamespace(id='p', tracks=[SimpleNamespace(id='t', filename='source.wav')]),
                lambda *a: source, cancel_event=event)
    finally: trigger.join(6)
    assert time.monotonic() - started < 5 and marker.is_file()
    pid = int(marker.read_text())
    with pytest.raises(ProcessLookupError): os.kill(pid, 0)
    with pytest.raises(ChildProcessError): os.waitpid(pid, os.WNOHANG)


def test_native_project_worker_receives_original_policy_and_actual_cpu(tmp_path, monkeypatch):
    from app import ai_metering_agent
    monkeypatch.setenv('MTA_NATIVE_SINGLE_USER', 'true')
    monkeypatch.delenv('MTA_AI_CGROUP_PARENT', raising=False)
    monkeypatch.setattr(ai_metering_agent, '_descendants', lambda pid: set())
    source = tmp_path / 'source.wav'
    with wave.open(str(source), 'wb') as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(44100); w.writeframes(b'\0\0' * 441)
    worker = tmp_path / 'native.py'
    worker.write_text('''import argparse,json,os,pathlib,time,shutil
p=argparse.ArgumentParser();p.add_argument('--request');p.add_argument('--output');a=p.parse_args()
envelope=json.loads(os.environ['MTA_AI_ADMITTED_POLICY'])
assert envelope['kind']=='ace-step' and envelope['decision']['model_id']=='ace-step'
request=json.loads(pathlib.Path(a.request).read_text())
end=time.monotonic()+.08
while time.monotonic()<end:sum(range(1000))
shutil.copyfile(request['source_audio'][0]['filename'],a.output)
''')
    worker.chmod(0o700); monkeypatch.setattr(legacy, 'configured_worker', lambda: worker)
    payload, metadata = legacy.run_worker_with_project_audio({'scope': 'project'},
        SimpleNamespace(id='p', tracks=[SimpleNamespace(id='t', filename='source.wav')]), lambda *a: source)
    assert payload == source.read_bytes()
    assert metadata['_trusted_worker_source'] == 'worker' and metadata['_trusted_worker_usage']['cpu_seconds'] > 0


def test_native_studio_no_wait4_fallback_stops_its_own_session(tmp_path, monkeypatch):
    from app import studio_compute, ai_worker_registry
    monkeypatch.setenv('MTA_NATIVE_SINGLE_USER', 'true')
    monkeypatch.delattr(os, 'wait4')
    marker = tmp_path / 'studio-pid'
    worker = tmp_path / 'studio.py'
    worker.write_text('import pathlib,os,time\npathlib.Path(' + repr(str(marker))
        + ').write_text(str(os.getpid()))\nwhile True:time.sleep(.02)\n')
    monkeypatch.setattr(ai_worker_registry, 'resolve_worker', lambda *a: worker)
    monkeypatch.setattr(ai_worker_registry, 'worker_python', lambda *a: __import__('sys').executable)
    started = time.monotonic()
    with pytest.raises(RuntimeError, match='timed out'):
        studio_compute._compute(0, 'vocal-harmony', {}, timeout=.2)
    assert time.monotonic() - started < 3 and marker.is_file()
    pid = int(marker.read_text())
    with pytest.raises(ProcessLookupError): os.kill(pid, 0)
