import pytest
from app import ai_billing
from app.auth import db, init_auth_db

@pytest.fixture(autouse=True)
def isolate(tmp_path,monkeypatch):
    monkeypatch.setenv('MTA_DATA_DIR',str(tmp_path))
    init_auth_db()
    with db() as c:
        c.execute("INSERT INTO users(username,email,password_hash,active,role,created_at,updated_at) VALUES('test','test@example.org','fake',1,'user',1,1)")
    yield

def test_job_lifecycle_and_period_cost():
    with db() as c: uid=c.execute("SELECT id FROM users WHERE username='test'").fetchone()[0]
    ai_billing.set_price('cpu_seconds',1500000,valid_from='2025-10-01')
    job=ai_billing.create_job(uid,'whisper',started_at=1760140800)
    ai_billing.finish_job(job,'done',{'cpu_seconds':2.0,'disk_write_bytes':1024},source='worker',finished_at=1760140810)
    result=ai_billing.report('custom',user_id=uid,start='2025-10-11',end='2025-10-11')
    assert result['total_micro']==3000000
    assert result['job_count']==1 and result['unmetered_jobs']==0
    bill=ai_billing.close_period(uid,'2025-10-11','2025-10-11')
    assert bill['total_micro']==3000000
    ai_billing.set_price('cpu_seconds',9999999,valid_from='2025-10-12')
    assert ai_billing.close_period(uid,'2025-10-11','2025-10-11')['total_micro']==3000000

def test_unmetered_jobs_cannot_bill():
    with db() as c: uid=c.execute("SELECT id FROM users WHERE username='test'").fetchone()[0]
    job=ai_billing.create_job(uid,'ace-step',started_at=1760140800)
    ai_billing.finish_job(job,'done',source='unmetered',finished_at=1760140900)
    with pytest.raises(ValueError,match='unmetered'):
        ai_billing.close_period(uid,'2025-10-11','2025-10-11')

def test_reject_untrusted_negative_duplicate_and_unknown_resources():
    with db() as c: uid=c.execute("SELECT id FROM users WHERE username='test'").fetchone()[0]
    job=ai_billing.create_job(uid,'demucs')
    with pytest.raises(ValueError): ai_billing.finish_job(job,'done',{'gpu_seconds':1})
    with pytest.raises(ValueError): ai_billing.finish_job(job,'done',{'gpu_seconds':-1},source='gpu-agent')
    with pytest.raises(ValueError): ai_billing.finish_job(job,'done',{'other':1},source='worker')
    ai_billing.finish_job(job,'failed',source='unmetered')
    with pytest.raises(ValueError): ai_billing.finish_job(job,'done',source='unmetered')

@pytest.mark.parametrize('period', ['day','week','month','year','custom'])
def test_periods(period):
    kw={'start':'2025-10-10','end':'2025-10-12'} if period=='custom' else {'anchor':'2025-10-11'}
    output=ai_billing.report(period,**kw)
    assert output['start_ts']<output['end_ts']
