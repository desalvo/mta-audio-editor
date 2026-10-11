"""CPU charges require explicit per-job CPU observations."""
import pytest
import datetime as dt
from app import ai_billing
from app.auth import db, init_auth_db

@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    monkeypatch.setenv('MTA_DATA_DIR', str(tmp_path))
    init_auth_db()
    with db() as c:
        c.execute("INSERT INTO users(username,email,password_hash,active,role,created_at,updated_at) "
                  "VALUES('cpu-guard','cpu-guard@example.org','fake',1,'user',1,1)")


def test_cpu_tariff_rejects_gpu_only_job():
    with db() as c:
        uid = c.execute("SELECT id FROM users WHERE username='cpu-guard'").fetchone()[0]
    ai_billing.set_price('cpu_seconds', 100, valid_from='2026-01-01')
    job = ai_billing.create_job(uid, 'ace-step', started_at=int(dt.datetime(2026, 1, 1, 12, tzinfo=dt.timezone.utc).timestamp()))
    ai_billing.finish_job(job, 'done', {'gpu_seconds': 1.0}, source='gpu-agent', finished_at=int(dt.datetime(2026, 1, 1, 13, tzinfo=dt.timezone.utc).timestamp()))
    with pytest.raises(ValueError, match='CPU tariff requires verified'):
        ai_billing.close_period(uid, '2026-01-01', '2026-01-02')


def test_cpu_tariff_accepts_explicit_cpu_zero():
    with db() as c:
        uid = c.execute("SELECT id FROM users WHERE username='cpu-guard'").fetchone()[0]
    ai_billing.set_price('cpu_seconds', 100, valid_from='2026-01-01')
    job = ai_billing.create_job(uid, 'metadata', started_at=int(dt.datetime(2026, 1, 1, 12, tzinfo=dt.timezone.utc).timestamp()))
    ai_billing.finish_job(job, 'done', {'cpu_seconds': 0.0}, source='cgroup', finished_at=int(dt.datetime(2026, 1, 1, 13, tzinfo=dt.timezone.utc).timestamp()))
    result = ai_billing.close_period(uid, '2026-01-01', '2026-01-02')
    assert result['total_micro'] == 0
