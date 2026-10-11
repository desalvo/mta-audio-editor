"""Automatic period closures and immutable tariff rules."""
import datetime as dt
import pytest
from app import ai_billing
from app.auth import db, init_auth_db

@pytest.fixture(autouse=True)
def sample_user(tmp_path,monkeypatch):
    monkeypatch.setenv('MTA_DATA_DIR',str(tmp_path))
    init_auth_db()
    with db() as c:
        c.execute("INSERT INTO users(username,email,password_hash,active,role,created_at,updated_at) VALUES('bill','billing@example.org','fake',1,'user',1,1)")

def uid():
    with db() as c:
        return c.execute("SELECT id FROM users WHERE username='bill'").fetchone()[0]

def stamp(s):
    return int(dt.datetime.fromisoformat(s).replace(tzinfo=dt.timezone.utc).timestamp())

def test_auto_monthly_close_is_repeatable():
    ai_billing.configure_schedule(uid(),'month')
    ai_billing.set_price('cpu_seconds',1000000,valid_from='2025-01-01')
    jid=ai_billing.create_job(uid(),'whisper',started_at=stamp('2025-05-05T12:00:00'))
    ai_billing.finish_job(jid,'done',{'cpu_seconds':3},source='worker',finished_at=stamp('2025-05-05T12:01:00'))
    first=ai_billing.run_scheduled_closures(at=stamp('2025-06-02T12:00:00'))
    second=ai_billing.run_scheduled_closures(at=stamp('2025-06-02T12:00:00'))
    assert first[0]['total_micro']==3000000
    assert second[0]['already_closed']
    assert len(ai_billing.bills(uid()))==1

def test_cannot_close_running_jobs():
    ai_billing.create_job(uid(),'ace-step',started_at=stamp('2025-05-05T12:00:00'))
    with pytest.raises(ValueError,match='unfinished'):
        ai_billing.close_period(uid(),'2025-05-01','2025-05-31')

def test_locked_invoice_prevents_backdated_repricing():
    ai_billing.set_price('gpu_seconds',100000,valid_from='2025-01-01')
    jid=ai_billing.create_job(uid(),'ace-step',started_at=stamp('2025-05-05T12:00:00'))
    ai_billing.finish_job(jid,'done',{'gpu_seconds':2},source='gpu-agent',finished_at=stamp('2025-05-05T12:01:00'))
    assert ai_billing.close_period(uid(),'2025-05-01','2025-05-31')['total_micro']==200000
    with pytest.raises(ValueError,match='immutable'):
        ai_billing.set_price('gpu_seconds',200000,valid_from='2025-05-01')
