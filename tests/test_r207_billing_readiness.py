import pytest
from app import ai_billing
from app.ai_billing_readiness import check
from app.auth import db, init_auth_db


@pytest.fixture(autouse=True)
def setup_db(monkeypatch, tmp_path):
    monkeypatch.setenv('MTA_DATA_DIR', str(tmp_path))
    monkeypatch.delenv('MTA_AI_CGROUP_PARENT', raising=False)
    monkeypatch.delenv('MTA_AI_USER_STORAGE_ROOT', raising=False)
    init_auth_db()
    with db() as c:
        c.execute("INSERT INTO users(username,email,password_hash,active,role,created_at,updated_at) VALUES('audit','audit@example.org','x',1,'user',1,1)")


def test_cpu_readiness_requires_delegated_job_group():
    out = check()
    assert not out['ready_for_paid_resources']
    assert any(i['component'] == 'cpu_process_tree' for i in out['issues'])


def test_gpu_price_requires_real_process_sensor():
    ai_billing.set_price('gpu_seconds', 2, valid_from='2020-01-01')
    out = check()
    assert out['components']['gpu_per_job']['paid_tariff_active'] is True
    assert out['components']['gpu_per_job']['ready'] is False
    assert any(i['component'] == 'gpu_per_job' for i in out['issues'])


def test_paid_storage_cannot_use_unset_root():
    ai_billing.set_price('disk_gb_hours', 9, valid_from='2020-01-01')
    out = check()
    assert not out['components']['persistent_storage']['ready']


def test_readiness_does_not_accept_host_gpu_statistics(monkeypatch):
    monkeypatch.setenv('MTA_GPU_UTILIZATION', '100')
    monkeypatch.setenv('MTA_AI_METERING_KEY', 'fake')
    assert not check()['components']['gpu_per_job']['ready']
