"""Remote CPU attestation settlement must reach the real billing ledger."""
import json
import pytest
from app import ai_arranger_runtime as queue, ai_billing, ai_billing_outbox, ai_metering_bridge


@pytest.fixture
def remote_account(tmp_path, monkeypatch):
    monkeypatch.setattr(queue, '_ROOT', tmp_path / 'scheduler')
    monkeypatch.setenv('MTA_AI_BILLING_DB', str(tmp_path / 'billing.sqlite3'))
    # ai_billing.db determines the storage root via its own environment.
    with queue._db() as connection:
        connection.execute("INSERT INTO jobs(job_id,project_id,operation,state,rank,created_at,phase,message,payload_json) VALUES(?,?,?,?,?,?,?,?,?)", (
            'remotetest','project','arranger','queued',1,0,'queued','test',json.dumps({'schema_version':1,'actor_user_id':55,'adapter':'arranger'})))
    return 'remotetest'


def test_remote_cpu_acceptance_and_outbox(remote_account, monkeypatch):
    job=remote_account
    monkeypatch.setattr(ai_billing,'user_billing_enabled', lambda user: True)
    monkeypatch.setattr(ai_billing,'provision_inference_job', lambda *args: 'ledger5')
    monkeypatch.setattr(ai_billing_outbox, 'register_verified', lambda *args,**kwargs: ai_billing_outbox.register(args[0],args[1],args[3],args[4],source=kwargs['source']))
    assert ai_metering_bridge.capture(job, {'cpu_seconds':2.5}, 'remote-worker')
    assert ai_metering_bridge.register_settlement(job)
    assert ai_billing_outbox.inspect(job)['state']=='pending'
    with ai_billing_outbox._db() as con:
        evidence = json.loads(con.execute('SELECT intent_json FROM deliveries WHERE job_id=?',(job,)).fetchone()[0])
    assert evidence['source']=='remote-worker' and evidence['usage']=={'cpu_seconds':2.5}
    assert ai_metering_bridge.register_settlement(job)
    with pytest.raises(ValueError,match='Conflicting'):
        ai_billing_outbox.register(job,'ledger5','done', {'cpu_seconds':5},source='remote-worker')


def test_remote_gpu_is_rejected_by_all_layers(remote_account):
    with pytest.raises(ValueError,match='GPU'):
        ai_metering_bridge.capture(remote_account, {'gpu_seconds':1}, 'remote-worker')
    with pytest.raises(ValueError,match='GPU'):
        ai_billing_outbox.register(remote_account, 'ledger5','done',{'gpu_seconds':1},source='remote-worker')
    with pytest.raises(ValueError,match='GPU'):
        ai_billing.finish_job_idempotent('ledger5','done',{'gpu_seconds':1},source='remote-worker')


def test_real_remote_cpu_ledger_delivery_and_replay(tmp_path, monkeypatch):
    """End-to-end: durable evidence -> provision -> outbox -> persisted ledger."""
    from app.auth import db, init_auth_db
    monkeypatch.setattr(queue, '_ROOT', tmp_path / 'jobs')
    monkeypatch.setenv('MTA_DATA_DIR', str(tmp_path / 'auth'))
    init_auth_db()
    with db() as con:
        con.execute("INSERT INTO users(username,email,password_hash,active,role,created_at,updated_at) VALUES('billing55','billing55@example.org','fake',1,'user',1,1)")
        uid = con.execute("SELECT id FROM users WHERE username='billing55'").fetchone()[0]
    ai_billing.set_user_billing_enabled(uid, True)
    ai_billing.set_price('cpu_seconds', 1000000, valid_from='2025-01-01')
    with queue._db() as con:
        con.execute("INSERT INTO jobs(job_id,project_id,operation,state,rank,created_at,phase,message,payload_json) VALUES(?,?,?,?,?,?,?,?,?)",(
            'remote_e2e', 'project', 'arranger', 'queued', 1, 0, 'queued', 'test', json.dumps({'schema_version':1,'actor_user_id':uid,'adapter':'arranger'})))
    assert ai_metering_bridge.capture('remote_e2e', {'cpu_seconds':3.25}, 'remote-worker')
    assert ai_metering_bridge.register_settlement('remote_e2e')
    assert ai_billing_outbox.inspect('remote_e2e')['state'] == 'pending'
    assert ai_billing_outbox.deliver(job_id='remote_e2e') == 1
    assert ai_billing_outbox.deliver(job_id='remote_e2e') == 0
    assert ai_metering_bridge.register_settlement('remote_e2e')
    assert ai_billing_outbox.inspect('remote_e2e')['state'] == 'delivered'
    ledger_id = ai_billing.existing_inference_ledger_job('remote_e2e', uid, 'arranger')
    with db() as con:
        entry = con.execute('SELECT status,resource_source,usage_json FROM ai_compute_jobs WHERE id=?',(ledger_id,)).fetchone()
    assert entry['status'] == 'done'
    assert entry['resource_source'] == 'remote-worker'
    assert json.loads(entry['usage_json'])['cpu_seconds'] == 3.25
