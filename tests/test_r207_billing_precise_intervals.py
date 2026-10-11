"""Regression tests: no charge for failed workers, and exact tariff boundaries."""
import datetime as dt
import pytest
from app import ai_billing
from app.auth import db, init_auth_db


def ts(value):
    return int(dt.datetime.fromisoformat(value).replace(tzinfo=dt.timezone.utc).timestamp())


@pytest.fixture
def account(tmp_path, monkeypatch):
    monkeypatch.setenv('MTA_DATA_DIR', str(tmp_path))
    init_auth_db()
    with db() as c:
        c.execute("INSERT INTO users(username,email,password_hash,active,role,created_at,updated_at) VALUES('account','account@example.org','fake',1,'user',1,1)")
        return c.execute("SELECT id FROM users WHERE username='account'").fetchone()[0]


def test_failed_job_diagnostics_do_not_count_as_cost(account):
    ai_billing.set_price('cpu_seconds',10000,valid_from='2026-01-01')
    job=ai_billing.create_job(account,'test',started_at=ts('2026-10-10T03:00:00'))
    ai_billing.finish_job(job,'failed',{'cpu_seconds':500},source='cgroup',finished_at=ts('2026-10-10T03:01:00'))
    report=ai_billing.report('day',user_id=account,anchor='2026-10-10')
    assert report['total_micro']==0
    with pytest.raises(ValueError,match='unfinished, failed or unmetered'):
        ai_billing.close_period(account,'2026-10-10','2026-10-10')


def test_storage_rate_change_within_day(account):
    gib=1024**3
    ai_billing.record_persistent_storage(account,gib,sampled_at=ts('2026-10-10T00:00:00'))
    ai_billing.record_persistent_storage(account,gib,sampled_at=ts('2026-10-11T00:00:00'))
    ai_billing.set_price('disk_gb_hours',100,valid_from='2026-10-01T00:00:00Z',valid_until='2026-10-10T12:00:00Z')
    ai_billing.set_price('disk_gb_hours',200,valid_from='2026-10-10T12:00:00Z')
    report=ai_billing.report('day',user_id=account,anchor='2026-10-10')
    assert report['total_micro']==12*100+12*200
    assert report['rows'][0]['resources']['disk_gb_hours']==24
