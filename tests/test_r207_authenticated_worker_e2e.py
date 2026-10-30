"""Real HTTP-token-worker-ledger acceptance without production data or models."""
import io
import json
import stat
import textwrap
import wave

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app import ai_access, ai_billing
from app.ai_billing_routes import router
from app.auth import db


@pytest.fixture
def isolated_api(tmp_path, monkeypatch, synthetic_worker_resolution):
    monkeypatch.setenv('MTA_DATA_DIR', str(tmp_path / 'private-db'))
    monkeypatch.delenv('MTA_AI_CGROUP_PARENT', raising=False)
    monkeypatch.delenv('MTA_AI_UNIFIED_WORKERS_ENABLED', raising=False)
    monkeypatch.setenv('MTA_AI_WORKER_ENABLED', 'true')
    worker = tmp_path / 'acceptance_worker.py'
    worker.write_text(textwrap.dedent('''\
        #!/usr/bin/env python3
        import argparse, wave
        p = argparse.ArgumentParser()
        p.add_argument('--request', required=True)
        p.add_argument('--output', required=True)
        a = p.parse_args()
        with wave.open(a.output, 'wb') as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(44100)
            w.writeframes(b'\\x00\\x00' * 4410)
    '''))
    worker.chmod(worker.stat().st_mode | stat.S_IXUSR)
    monkeypatch.setenv('MTA_AI_WORKER_ACE_STEP_EXECUTABLE', str(worker))
    with db() as connection:
        connection.execute('CREATE TABLE users(id INTEGER PRIMARY KEY, active INTEGER NOT NULL)')
        connection.execute('INSERT INTO users VALUES(1,1)')
        connection.execute('INSERT INTO users VALUES(2,1)')
    token_1 = ai_access.issue(1, 'acceptance')['token']
    token_2 = ai_access.issue(2, 'acceptance')['token']
    app = FastAPI()
    app.include_router(router)
    return TestClient(app), token_1, token_2


def test_authenticated_worker_records_once_and_rejects_duplicate(isolated_api):
    client, token, other_token = isolated_api
    route = '/api/ai-jobs/execute'
    payload = {'kind': 'ace-step', 'plan': {'test': 'fixed-trusted-worker'}}
    assert client.post(route, json=payload).status_code == 401
    key = 'acceptance-unique-001'
    headers = {'Authorization': f'Bearer {token}', 'x-mta-ai-idempotency-key': key}
    response = client.post(route, headers=headers, json=payload)
    assert response.status_code == 200, response.text
    assert response.headers['content-type'].startswith('audio/wav')
    with wave.open(io.BytesIO(response.content), 'rb') as sample:
        assert sample.getnframes() == 4410
    job = response.headers['x-mta-ai-job-id']
    with db() as connection:
        first = dict(connection.execute('SELECT * FROM ai_compute_jobs WHERE id=?', (job,)).fetchone())
    assert first['user_id'] == 1
    assert first['status'] == 'done'
    assert first['resource_source'] == 'worker'
    assert json.loads(first['usage_json'])['cpu_seconds'] >= 0
    assert first['billable'] == 1
    duplicate = client.post(route, headers=headers, json=payload)
    assert duplicate.status_code == 409
    status = client.get(f'/api/ai-jobs/request-status/{key}', headers=headers)
    assert status.status_code == 200 and status.json()['job_id'] == job
    unauthorized = client.get(f'/api/ai-jobs/request-status/{key}', headers={'Authorization': f'Bearer {other_token}'})
    assert unauthorized.status_code == 404
    with db() as connection:
        assert connection.execute('SELECT COUNT(*) FROM ai_compute_jobs').fetchone()[0] == 1


def test_remote_payload_paths_are_rejected(isolated_api):
    client, token, _ = isolated_api
    response = client.post('/api/ai-jobs/execute', headers={'Authorization': f'Bearer {token}'},
                           json={'kind': 'ace-step', 'plan': {'command': '/bin/sh'}})
    assert response.status_code == 400
    with db() as connection:
        assert connection.execute("SELECT COUNT(*) FROM sqlite_master WHERE name='ai_compute_jobs'").fetchone()[0] == 0


def test_worker_failure_is_not_billable(isolated_api, tmp_path, monkeypatch):
    client, token, _ = isolated_api
    worker = tmp_path / 'broken_worker.py'
    worker.write_text('#!/usr/bin/env python3\nraise SystemExit(7)\n')
    worker.chmod(worker.stat().st_mode | stat.S_IXUSR)
    monkeypatch.setenv('MTA_AI_WORKER_ACE_STEP_EXECUTABLE', str(worker))
    response = client.post('/api/ai-jobs/execute',
                           headers={'Authorization': f'Bearer {token}'},
                           json={'kind': 'ace-step', 'plan': {'test': 'failure'}})
    assert response.status_code == 503
    with db() as connection:
        jobs = [dict(r) for r in connection.execute('SELECT status,resource_source FROM ai_compute_jobs')]
    assert len(jobs) == 1 and jobs[0]['status'] == 'failed'
    assert ai_billing.report('month', user_id=1)['total_micro'] == 0


def test_gpu_slot_lifecycle_on_success(isolated_api, monkeypatch):
    monkeypatch.setenv('MTA_AI_GPU_SLOT_TRACKING_ENABLED','true')
    monkeypatch.setenv('MTA_AI_GPU_SLOT_KINDS','ace-step')
    client, token, _ = isolated_api
    response = client.post('/api/ai-jobs/execute', headers={'Authorization':f'Bearer {token}'},
                           json={'kind':'ace-step','plan':{'test':'slot-success'}})
    assert response.status_code == 200, response.text
    with db() as c:
        lease = c.execute('SELECT state,acquired_ms,released_ms FROM ai_gpu_slot_leases').fetchone()
        assert lease['state'] == 'released' and lease['released_ms'] >= lease['acquired_ms']
        usage = json.loads(c.execute('SELECT usage_json FROM ai_compute_jobs').fetchone()[0])
        assert 'gpu_seconds' not in usage


def test_gpu_slot_lifecycle_on_failure(isolated_api, tmp_path, monkeypatch):
    monkeypatch.setenv('MTA_AI_GPU_SLOT_TRACKING_ENABLED','true')
    monkeypatch.setenv('MTA_AI_GPU_SLOT_KINDS','ace-step')
    worker = tmp_path / 'failing_gpu_worker.py'
    worker.write_text('#!/usr/bin/env python3\nraise SystemExit(1)\n')
    worker.chmod(worker.stat().st_mode | stat.S_IXUSR)
    monkeypatch.setenv('MTA_AI_WORKER_ACE_STEP_EXECUTABLE', str(worker))
    client, token, _ = isolated_api
    response = client.post('/api/ai-jobs/execute', headers={'Authorization':f'Bearer {token}'},
                           json={'kind':'ace-step','plan':{'test':'slot-failure'}})
    assert response.status_code == 503
    with db() as c:
        assert c.execute('SELECT state FROM ai_gpu_slot_leases').fetchone()[0] == 'aborted'
        assert c.execute('SELECT status FROM ai_compute_jobs').fetchone()[0] == 'failed'
