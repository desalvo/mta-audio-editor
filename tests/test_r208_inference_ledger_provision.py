"""Durable inference billing identity admission, with explicit user opt-in."""
from concurrent.futures import ThreadPoolExecutor
from app.auth import db, init_auth_db
from app import ai_billing
import pytest

@pytest.fixture
def user(tmp_path, monkeypatch):
    monkeypatch.setenv('MTA_DATA_DIR', str(tmp_path))
    init_auth_db()
    with db() as con:
        con.execute("INSERT INTO users(username,email,password_hash,active,role,created_at,updated_at) VALUES('ledger-test','ledger@example.org','x',1,'user',1,1)")
        return con.execute("SELECT id FROM users WHERE username='ledger-test'").fetchone()[0]

def test_opt_out_does_not_create_ledger_job(user):
    assert ai_billing.provision_inference_job('qjob1', user, 'arranger') is None
    with db() as con:
        assert con.execute('SELECT count(*) FROM ai_compute_jobs').fetchone()[0] == 0

def test_opt_in_retries_use_one_identity(user):
    ai_billing.set_user_billing_enabled(user, True)
    ids = [ai_billing.provision_inference_job('qjob2', user, 'remix') for _ in range(4)]
    assert len(set(ids)) == 1
    with db() as con:
        assert con.execute('SELECT count(*) FROM ai_compute_jobs WHERE id=?', (ids[0],)).fetchone()[0] == 1
        assert con.execute('SELECT count(*) FROM ai_job_hardware_snapshots WHERE job_id=?', (ids[0],)).fetchone()[0] == 1

def test_concurrent_provision_is_unique(user):
    ai_billing.set_user_billing_enabled(user, True)
    with ThreadPoolExecutor(max_workers=4) as pool:
        ids = list(pool.map(lambda _: ai_billing.provision_inference_job('qjob3', user, 'arranger'), range(4)))
    assert len(set(ids)) == 1

def test_conflicting_kind_rejected(user):
    ai_billing.set_user_billing_enabled(user, True)
    ai_billing.provision_inference_job('qjob4', user, 'arranger')
    with pytest.raises(ValueError, match='Conflicting'):
        ai_billing.provision_inference_job('qjob4', user, 'remix')

@pytest.mark.parametrize('job_id', ['../bad', '', 'a/b', 'bad space'])
def test_bad_job_identity_rejected(user,job_id):
    with pytest.raises(ValueError, match='Invalid durable'):
        ai_billing.provision_inference_job(job_id,user,'arranger')
