import datetime as dt
import pytest
from app.auth import init_auth_db, db
from app import ai_billing
from app.ai_storage_sampler import sample_all


@pytest.fixture
def user(tmp_path, monkeypatch):
    monkeypatch.setenv('MTA_DATA_DIR', str(tmp_path / 'database'))
    init_auth_db()
    with db() as c:
        c.execute("INSERT INTO users(username,email,password_hash,active,role,created_at,updated_at) VALUES('sampled','sampled@example.org','fake',1,'user',1,1)")
        return c.execute("SELECT id FROM users WHERE username='sampled'").fetchone()[0]


def stamp(x):
    return int(dt.datetime.fromisoformat(x).replace(tzinfo=dt.timezone.utc).timestamp())


def test_samples_only_assigned_user_directory(user, tmp_path):
    base=tmp_path/'storage'; base.mkdir()
    owned=base/str(user); owned.mkdir()
    (owned/'persistent.flac').write_bytes(b'a'*50)
    (owned/'tmp').mkdir(); (owned/'tmp'/'scratch.wav').write_bytes(b'b'*1000)
    (base/'unassigned').mkdir(); (base/'unassigned'/'private.dat').write_bytes(b'x'*400)
    assert sample_all(root=base, sampled_at=stamp('2026-10-10T00:00:00'))['samples']>=1
    with db() as c:
        row=c.execute('SELECT bytes_used FROM ai_persistent_storage_samples WHERE user_id=?',(user,)).fetchone()
    assert row[0]==50


def test_missing_user_dir_is_zero(user,tmp_path):
    base=tmp_path/'storage';base.mkdir()
    sample_all(root=base)
    with db() as c:
        assert c.execute('SELECT bytes_used FROM ai_persistent_storage_samples WHERE user_id=?',(user,)).fetchone()[0]==0


def test_rejects_symlinks(user,tmp_path):
    base=tmp_path/'storage';base.mkdir()
    (base/str(user)).symlink_to(tmp_path,target_is_directory=True)
    with pytest.raises(ValueError,match='Symlinked'):
        sample_all(root=base)


def test_no_storage_charges_across_unobserved_multi_day_gap(user,tmp_path):
    ai_billing.record_persistent_storage(user,1024**3,sampled_at=stamp('2026-10-01T00:00:00'))
    ai_billing.record_persistent_storage(user,1024**3,sampled_at=stamp('2026-10-05T00:00:00'))
    assert ai_billing.report('custom',user_id=user,start='2026-10-02',end='2026-10-03')['total_micro']==0
