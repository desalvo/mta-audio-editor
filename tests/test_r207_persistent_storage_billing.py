import datetime as dt
import pytest
from app import ai_billing
from app.auth import db, init_auth_db

@pytest.fixture
def user(tmp_path, monkeypatch):
    monkeypatch.setenv('MTA_DATA_DIR', str(tmp_path / 'db'))
    init_auth_db()
    with db() as c:
        c.execute("INSERT INTO users(username,email,password_hash,active,role,created_at,updated_at) VALUES('store','store@example.org','fake',1,'user',1,1)")
        uid=c.execute("SELECT id FROM users WHERE username='store'").fetchone()[0]
    return uid

def stamp(value):
    return int(dt.datetime.fromisoformat(value).replace(tzinfo=dt.timezone.utc).timestamp())

def test_persistent_only_and_zero_after_delete(user, tmp_path):
    root=tmp_path/'user-storage'; root.mkdir()
    (root/'track.flac').write_bytes(b'a'*2048)
    (root/'tmp').mkdir(); (root/'tmp'/'transient.wav').write_bytes(b'x'*10000)
    (root/'.cache').mkdir(); (root/'.cache'/'model.bin').write_bytes(b'x'*8000)
    (root/'unfinished.part').write_bytes(b'x'*9000)
    assert ai_billing.measure_persistent_directory(user,root,sampled_at=stamp('2026-10-10T00:00:00'))==2048
    (root/'track.flac').unlink()
    assert ai_billing.measure_persistent_directory(user,root,sampled_at=stamp('2026-10-11T00:00:00'))==0
    ai_billing.set_price('disk_gb_hours',1000000,valid_from='2026-10-01')
    output=ai_billing.report('custom',user_id=user,start='2026-10-10',end='2026-10-10')
    assert output['rows'][0]['resources']['disk_gb_hours']==round(2048/1024**3*24,10)
    assert output['total_micro']>0

def test_worker_temporary_io_is_not_billed(user):
    ai_billing.set_price('disk_write_bytes',10,valid_from='2025-01-01')
    job=ai_billing.create_job(user,'test',started_at=stamp('2026-10-10T00:00:00'))
    ai_billing.finish_job(job,'done',{'disk_write_bytes':10000000,'cpu_seconds':0},source='worker',finished_at=stamp('2026-10-10T00:01:00'))
    report=ai_billing.report('custom',user_id=user,start='2026-10-10',end='2026-10-10')
    assert report['total_micro']==0

def test_no_storage_sample_no_charge(user):
    ai_billing.set_price('disk_gb_hours',1000000,valid_from='2025-01-01')
    assert ai_billing.report('custom',user_id=user,start='2026-10-10',end='2026-10-10')['total_micro']==0

def test_no_arbitrary_host_directory_scans(user,tmp_path):
    root=tmp_path/'user';root.mkdir()
    (root/'external').symlink_to(tmp_path,target_is_directory=True)
    assert ai_billing.measure_persistent_directory(user,root)==0
