import pytest
from app import ai_billing
from app.auth import db, init_auth_db

@pytest.fixture(autouse=True)
def isolated(tmp_path,monkeypatch):
    monkeypatch.setenv('MTA_DATA_DIR',str(tmp_path))
    init_auth_db()
    with db() as c:
        c.execute("INSERT INTO users(username,email,password_hash,active,role,created_at,updated_at) VALUES('tariff','t@example.org','fake',1,'user',1,1)")

def test_tariff_effective_ranges_and_open_end():
    ai_billing.set_price('cpu_seconds',1000000,valid_from='2025-01-01')
    ai_billing.set_price('cpu_seconds',2000000,valid_from='2025-07-01')
    entries=ai_billing.tariff_history('cpu_seconds')
    assert len(entries)==2
    assert entries[0]['valid_until']==entries[1]['valid_from']
    assert entries[1]['valid_until'] is None
    assert ai_billing.prices(entries[0]['valid_from']+86400)['cpu_seconds']==1000000
    assert ai_billing.prices(entries[1]['valid_from']+86400)['cpu_seconds']==2000000

def test_historical_job_uses_price_on_start():
    with db() as c: uid=c.execute("SELECT id FROM users WHERE username='tariff'").fetchone()[0]
    ai_billing.set_price('gpu_seconds',2000000,valid_from='2025-01-01')
    ai_billing.set_price('gpu_seconds',6000000,valid_from='2025-06-01')
    a=ai_billing.create_job(uid,'ace',started_at=1735776000)
    ai_billing.finish_job(a,'done',{'gpu_seconds':2},source='gpu-agent',finished_at=1735776100)
    b=ai_billing.create_job(uid,'ace',started_at=1751414400)
    ai_billing.finish_job(b,'done',{'gpu_seconds':2},source='gpu-agent',finished_at=1751414500)
    assert ai_billing.report('custom',start='2025-01-01',end='2025-12-31')['total_micro']==16000000

def test_invalid_ranges_and_overlaps():
    ai_billing.set_price('disk_gb_hours',100,valid_from='2025-01-01',valid_until='2025-02-01')
    with pytest.raises(ValueError,match='Overlapping'):
        ai_billing.set_price('disk_gb_hours',200,valid_from='2025-01-15')
    with pytest.raises(ValueError):
        ai_billing.set_price('disk_gb_hours',200,valid_from='2025-03-01',valid_until='2025-02-01')
