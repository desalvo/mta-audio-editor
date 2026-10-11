"""Billing certification against disposable SQLite databases only."""
import datetime as dt

import pytest

from app import ai_billing
from app.auth import db, init_auth_db


def ts(s):
    return int(dt.datetime.fromisoformat(s).replace(tzinfo=dt.timezone.utc).timestamp())


@pytest.fixture
def account(tmp_path, monkeypatch):
    monkeypatch.setenv('MTA_DATA_DIR', str(tmp_path))
    monkeypatch.delenv('MTA_AI_USER_STORAGE_ROOT', raising=False)
    init_auth_db()
    with db() as connection:
        connection.execute("INSERT INTO users(username,email,password_hash,active,role,created_at,updated_at) "
                           "VALUES('test','test@example.org','stub',1,'user',1,1)")
        return connection.execute("SELECT id FROM users WHERE username='test'").fetchone()[0]


def test_diagnostic_kept_for_audit_but_never_charged(account):
    ai_billing.set_price('cpu_seconds', 1_000_000, valid_from='2025-01-01')
    diagnostic = ai_billing.create_job(account, 'smoke', started_at=ts('2025-05-02T12:00:00'), diagnostic=True)
    ai_billing.finish_job(diagnostic, 'done', {'cpu_seconds': 100}, source='cgroup', finished_at=ts('2025-05-02T12:01:00'))
    billable = ai_billing.create_job(account, 'whisper', started_at=ts('2025-05-02T13:00:00'))
    ai_billing.finish_job(billable, 'done', {'cpu_seconds': 2}, source='cgroup', finished_at=ts('2025-05-02T13:01:00'))
    preview = ai_billing.report('month', user_id=account, anchor='2025-05-01')
    assert preview['diagnostic_jobs'] == 1
    assert preview['total_micro'] == 2_000_000
    closure = ai_billing.close_period(account, '2025-05-01', '2025-05-31')
    assert closure['total_micro'] == 2_000_000
    assert ai_billing.close_period(account, '2025-05-01', '2025-05-31')['already_closed']


def test_diagnostic_failure_does_not_block_closure(account):
    diagnostic = ai_billing.create_job(account, 'smoke', started_at=ts('2025-05-02T12:00:00'), diagnostic=True)
    ai_billing.finish_job(diagnostic, 'failed', finished_at=ts('2025-05-02T12:01:00'))
    assert ai_billing.reconcile_period(account, '2025-05-01', '2025-05-31')['ready']
    assert ai_billing.close_period(account, '2025-05-01', '2025-05-31')['total_micro'] == 0
