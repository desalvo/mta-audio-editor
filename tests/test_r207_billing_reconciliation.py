"""Read-only audit catches cross-user/period billing anomalies."""
import datetime as dt
import pytest
from app import ai_billing
from app.auth import db, init_auth_db


@pytest.fixture(autouse=True)
def setup(tmp_path, monkeypatch):
    monkeypatch.setenv('MTA_DATA_DIR', str(tmp_path))
    init_auth_db()
    with db() as c:
        for name in ('alice', 'bob'):
            c.execute('INSERT INTO users(username,email,password_hash,active,role,created_at,updated_at) '
                      'VALUES(?,?,?,?,?,?,?)', (name, name + '@example.org', 'x', 1, 'user', 1, 1))


def uid(name):
    with db() as c:
        return c.execute('SELECT id FROM users WHERE username=?', (name,)).fetchone()[0]


def ts(iso):
    return int(dt.datetime.fromisoformat(iso).replace(tzinfo=dt.timezone.utc).timestamp())


def test_concurrent_users_isolated():
    for username in ('alice', 'bob'):
        j = ai_billing.create_job(uid(username), 'whisper', started_at=ts('2025-05-05T12:00:00'))
        ai_billing.finish_job(j, 'done', {'cpu_seconds': 3}, source='cgroup',
                              finished_at=ts('2025-05-05T12:00:10'))
    ai_billing.set_price('cpu_seconds', 123, valid_from='2025-01-01')
    for username in ('alice', 'bob'):
        result = ai_billing.reconcile_period(uid(username), '2025-05-01', '2025-05-31')
        assert result['ready'] and result['job_count'] == 1


def test_gpu_price_requires_gpu_agent_not_cpu_source():
    ai_billing.set_price('gpu_seconds', 111, valid_from='2025-01-01')
    j = ai_billing.create_job(uid('alice'), 'demucs', started_at=ts('2025-05-05T12:00:00'))
    ai_billing.finish_job(j, 'done', {'cpu_seconds': 2}, source='cgroup',
                          finished_at=ts('2025-05-05T12:00:10'))
    result = ai_billing.reconcile_period(uid('alice'), '2025-05-01', '2025-05-31')
    assert not result['ready']
    assert any(x['code'] == 'missing_priced_metric' and x['job_id'] == j for x in result['issues'])


def test_boundary_and_failed_job():
    j = ai_billing.create_job(uid('alice'), 'sam', started_at=ts('2025-04-30T23:59:00'))
    ai_billing.finish_job(j, 'failed', {}, source='unmetered',
                          finished_at=ts('2025-05-01T00:01:00'))
    codes = {x['code'] for x in ai_billing.reconcile_period(uid('alice'), '2025-05-01', '2025-05-31')['issues']}
    assert {'boundary_crossing_job', 'non_successful_job', 'unmetered_job'} <= codes


def test_storage_without_samples_fails_preflight(tmp_path, monkeypatch):
    storage = tmp_path / 'storage'
    storage.mkdir()
    monkeypatch.setenv('MTA_AI_USER_STORAGE_ROOT', str(storage))
    ai_billing.set_price('disk_gb_hours', 50, valid_from='2025-01-01')
    assert any(x['code'] == 'storage_coverage_missing' for x in
               ai_billing.reconcile_period(uid('bob'), '2025-05-01', '2025-05-31')['issues'])
