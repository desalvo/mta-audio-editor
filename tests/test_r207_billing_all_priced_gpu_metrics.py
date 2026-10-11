"""Billing may not trust client-assigned job categories or partial GPU metrics."""
import pytest
from app import ai_billing
from app.auth import db, init_auth_db

@pytest.fixture(autouse=True)
def account(tmp_path, monkeypatch):
    monkeypatch.setenv('MTA_DATA_DIR', str(tmp_path))
    monkeypatch.delenv('MTA_AI_USER_STORAGE_ROOT', raising=False)
    init_auth_db()
    with db() as c:
        c.execute("INSERT INTO users(username,email,password_hash,active,role,created_at,updated_at) "
                  "VALUES('gpucheck','gpucheck@example.org','dummy',1,'user',1,1)")

def uid():
    with db() as c:
        return c.execute("SELECT id FROM users WHERE username='gpucheck'").fetchone()[0]

def test_client_named_cpu_only_job_cannot_evade_gpu_tariff():
    ai_billing.set_price('gpu_seconds', 100, valid_from='2025-01-01')
    job = ai_billing.create_job(uid(), 'metadata', started_at=1760140800)
    ai_billing.finish_job(job, 'done', {'cpu_seconds': 1}, source='worker', finished_at=1760140810)
    with pytest.raises(ValueError, match='GPU tariff'):
        ai_billing.close_period(uid(), '2025-10-11', '2025-10-11')

def test_energy_tariff_does_not_require_energy_measurements():
    ai_billing.set_price('gpu_seconds', 100, valid_from='2025-01-01')
    ai_billing.set_price('gpu_energy_joules', 200, valid_from='2025-01-01')
    job = ai_billing.create_job(uid(), 'ace-step', started_at=1760140800)
    ai_billing.finish_job(job, 'done', {'gpu_seconds': 2}, source='gpu-agent', finished_at=1760140810)
    assert ai_billing.close_period(uid(), '2025-10-11', '2025-10-11')['total_micro'] == 200

def test_explicit_zero_is_valid_gpu_measurement():
    ai_billing.set_price('gpu_seconds', 100, valid_from='2025-01-01')
    ai_billing.set_price('gpu_energy_joules', 200, valid_from='2025-01-01')
    job = ai_billing.create_job(uid(), 'metadata', started_at=1760140800)
    ai_billing.finish_job(job, 'done', {'gpu_seconds': 0, 'gpu_energy_joules': 0}, source='gpu-agent', finished_at=1760140810)
    assert ai_billing.close_period(uid(), '2025-10-11', '2025-10-11')['total_micro'] == 0
