import pytest
from app import auth,worker_loss_resolution as losses,ai_metering_agent
from test_r208_unified_adapter_billing_e2e import operator as operator  # noqa: F401
from test_r210_deferred_owner_e2e import setup as setup,staged_execution  # noqa: F401


def test_original_verified_result_is_recovered_instead_of_written_off(setup,monkeypatch):
    job,ledger,_=staged_execution(setup,publish_now=False)
    with auth.db() as c:
        c.execute("INSERT INTO users(username,email,password_hash,role,active,created_at,updated_at) VALUES('recovery-admin','recovery@example.test','x','admin',1,1,1)")
        admin=c.execute("SELECT id FROM users WHERE username='recovery-admin'").fetchone()[0]
    monkeypatch.setattr(ai_metering_agent,'execute_registered_worker',lambda *a,**kw:pytest.fail('Inference replayed'))
    published=[]
    result=losses.recover_frozen(ledger,admin,lambda jid,*_:published.append(jid))
    assert result['original_result_recovered'] and result['inference_replayed'] is False
    assert published==[job]
    assert losses.recover_frozen(ledger,admin,lambda *a:pytest.fail('Duplicate publication'))['original_result_recovered']
    with auth.db() as c:
        assert c.execute('SELECT status FROM ai_compute_jobs WHERE id=?',(ledger,)).fetchone()[0]=='done'
        assert losses.history(c)==[]


def test_admin_cannot_republish_private_audio_after_project_owner_changed(setup,monkeypatch):
    from types import SimpleNamespace
    from app import main
    from fastapi.testclient import TestClient
    job,ledger,_=staged_execution(setup,publish_now=False)
    with auth.db() as c:
        c.execute("INSERT INTO users(username,email,password_hash,role,active,created_at,updated_at) VALUES('publication-admin','publication@example.test','x','admin',1,1,1)")
        admin=c.execute("SELECT id FROM users WHERE username='publication-admin'").fetchone()[0]
    monkeypatch.setattr(auth,'session_user',lambda request:auth.get_user(admin))
    monkeypatch.setattr(main,'session_user',lambda request:auth.get_user(admin))
    monkeypatch.setattr(main,'load_project',lambda _:SimpleNamespace(owner_user_id=admin))
    monkeypatch.setattr(main,'audio_path',lambda *a:pytest.fail('Foreign-owner audio path accessed'))
    client=TestClient(main.app)
    response=client.post('/api/admin/service-regime/worker-losses/'+ledger+'/recover-frozen',json={'confirm_recover':True},headers={'X-MTA-Request':'1'})
    assert response.status_code==422
    from app import ai_publish_outbox as publication
    assert publication.status(job)['state']=='pending'
    with auth.db() as c:assert c.execute('SELECT status FROM ai_compute_jobs WHERE id=?',(ledger,)).fetchone()[0]=='running'
