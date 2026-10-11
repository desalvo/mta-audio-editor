"""GPU usage may only originate from the separately authenticated sensor."""
import pytest
from app import ai_billing
from app.auth import db, init_auth_db

@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    monkeypatch.setenv("MTA_DATA_DIR", str(tmp_path))
    init_auth_db()
    with db() as c:
        c.execute("INSERT INTO users(username,email,password_hash,active,role,created_at,updated_at) VALUES('gpu-test','gpu@example.org','fake',1,'user',1,1)")

def _job():
    with db() as c:
        uid = c.execute("SELECT id FROM users WHERE username='gpu-test'").fetchone()[0]
    return ai_billing.create_job(uid, 'ace-step')

@pytest.mark.parametrize('source', ['worker', 'cgroup'])
def test_cpu_meter_cannot_claim_gpu_usage(source):
    job = _job()
    with pytest.raises(ValueError, match='trusted gpu-agent'):
        ai_billing.finish_job(job, 'done', {'cpu_seconds': 1.0, 'gpu_seconds': 2.0}, source=source)
    ai_billing.finish_job(job, 'failed')

def test_gpu_agent_requires_gpu_sample():
    job = _job()
    with pytest.raises(ValueError, match='explicit GPU measurement'):
        ai_billing.finish_job(job, 'done', {'cpu_seconds': 1.0}, source='gpu-agent')
    ai_billing.finish_job(job, 'failed')

def test_valid_gpu_agent_sample_is_recorded():
    job = _job()
    ai_billing.finish_job(job, 'done', {'cpu_seconds': 1.0, 'gpu_seconds': 2.0}, source='gpu-agent')
    with db() as c:
        row = c.execute('SELECT resource_source,usage_json FROM ai_compute_jobs WHERE id=?', (job,)).fetchone()
    assert row['resource_source'] == 'gpu-agent'
    assert 'gpu_seconds' in row['usage_json']
