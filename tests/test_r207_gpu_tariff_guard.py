"""Prevent CPU-only measurements from silently becoming a GPU bill."""
import datetime as dt
import pytest
from app.auth import db, init_auth_db
from app import ai_billing

@pytest.fixture(autouse=True)
def setup(tmp_path, monkeypatch):
    monkeypatch.setenv('MTA_DATA_DIR', str(tmp_path))
    init_auth_db()
    with db() as c:
        c.execute("INSERT INTO users(username,email,password_hash,active,role,created_at,updated_at) VALUES('gpuclient','gpu@example.org','test',1,'user',1,1)")

def stamp(s):
    return int(dt.datetime.fromisoformat(s).replace(tzinfo=dt.timezone.utc).timestamp())

def uid():
    with db() as c:
        return c.execute("SELECT id FROM users WHERE username='gpuclient'").fetchone()[0]

def test_gpu_pricing_requires_process_specific_measurement():
    ai_billing.set_price('gpu_seconds', 100, valid_from='2025-01-01')
    job = ai_billing.create_job(uid(), 'ace-step', started_at=stamp('2025-05-10T12:00:00'))
    ai_billing.finish_job(job, 'done', {'cpu_seconds': 12}, source='cgroup', finished_at=stamp('2025-05-10T12:01:00'))
    with pytest.raises(ValueError, match='GPU tariff requires'):
        ai_billing.close_period(uid(), '2025-05-01', '2025-05-31')

def test_without_gpu_price_cpu_metering_can_be_billed():
    ai_billing.set_price('cpu_seconds', 100, valid_from='2025-01-01')
    job = ai_billing.create_job(uid(), 'ace-step', started_at=stamp('2025-05-10T12:00:00'))
    ai_billing.finish_job(job, 'done', {'cpu_seconds': 12}, source='cgroup', finished_at=stamp('2025-05-10T12:01:00'))
    closed = ai_billing.close_period(uid(), '2025-05-01', '2025-05-31')
    assert closed['total_micro'] == 1200

def test_gpu_agent_can_close_with_verified_usage():
    ai_billing.set_price('gpu_seconds', 100, valid_from='2025-01-01')
    job = ai_billing.create_job(uid(), 'ace-step', started_at=stamp('2025-05-10T12:00:00'))
    ai_billing.finish_job(job, 'done', {'gpu_seconds': 12, 'cpu_seconds': 3}, source='gpu-agent', finished_at=stamp('2025-05-10T12:01:00'))
    closed = ai_billing.close_period(uid(), '2025-05-01', '2025-05-31')
    assert closed['total_micro'] == 1200
