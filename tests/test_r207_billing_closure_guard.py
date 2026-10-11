"""Fail-closed resource accounting: only user-owned, complete intervals."""
import datetime as dt
import pytest
from app import ai_billing
from app.auth import db, init_auth_db

@pytest.fixture(autouse=True)
def account(tmp_path, monkeypatch):
    monkeypatch.setenv('MTA_DATA_DIR', str(tmp_path))
    init_auth_db()
    with db() as c:
        c.execute("INSERT INTO users(username,email,password_hash,active,role,created_at,updated_at) VALUES('guard','guard@example.org','test',1,'user',1,1)")

def user():
    with db() as c:
        return c.execute("SELECT id FROM users WHERE username='guard'").fetchone()[0]

def t(iso):
    return int(dt.datetime.fromisoformat(iso).replace(tzinfo=dt.timezone.utc).timestamp())

def test_rejects_billing_overlapping_closed_periods():
    ai_billing.close_period(user(), '2025-05-01', '2025-05-15')
    with pytest.raises(ValueError, match='Overlapping'):
        ai_billing.close_period(user(), '2025-05-10', '2025-05-31')

def test_rejects_running_job_started_before_period():
    ai_billing.create_job(user(), 'whisper', started_at=t('2025-04-30T23:59:00'))
    with pytest.raises(ValueError, match='crossing'):
        ai_billing.close_period(user(), '2025-05-01', '2025-05-31')

def test_rejects_gap_in_metered_storage(tmp_path, monkeypatch):
    storage = tmp_path / 'storage'
    storage.mkdir()
    monkeypatch.setenv('MTA_AI_USER_STORAGE_ROOT', str(storage))
    ai_billing.record_persistent_storage(user(), 1024, sampled_at=t('2025-05-01T00:00:00'))
    with pytest.raises(ValueError, match='Incomplete persistent storage'):
        ai_billing.close_period(user(), '2025-05-01', '2025-05-01')
