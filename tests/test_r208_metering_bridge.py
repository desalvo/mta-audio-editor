import pytest
from app import ai_arranger_runtime as queue, ai_metering_bridge as bridge

@pytest.fixture
def job(tmp_path, monkeypatch):
    monkeypatch.setattr(queue, '_ROOT', tmp_path)
    with queue._db() as con:
        con.execute("INSERT INTO jobs(job_id,project_id,operation,state,rank,created_at,phase,message,payload_json) VALUES(?,?,?,?,?,?,?,?,?)", ('meterjob','project','arranger','queued',1,0,'queued','ok','{"schema_version":1,"actor_user_id":7}'))
    return 'meterjob'

def test_metering_immutable(job):
    assert bridge.capture(job, {'cpu_seconds': 2.5}, 'worker')
    assert not bridge.capture(job, {'cpu_seconds': 2.5}, 'worker')
    with pytest.raises(ValueError, match='Conflicting'):
        bridge.capture(job, {'cpu_seconds': 3}, 'worker')

def test_gpu_not_attributed_to_worker(job):
    with pytest.raises(ValueError, match='GPU accounting'):
        bridge.capture(job, {'gpu_seconds': 4}, 'worker')

def test_missing_metering_refused(job, monkeypatch):
    monkeypatch.setattr(bridge.ai_billing, 'user_billing_enabled', lambda uid: True)
    with pytest.raises(ValueError, match='Measured consumption'):
        bridge.register_settlement(job)

def test_opt_out_no_settlement(job, monkeypatch):
    monkeypatch.setattr(bridge.ai_billing, 'user_billing_enabled', lambda uid: False)
    assert not bridge.register_settlement(job)

def test_verified_handoff(job, monkeypatch):
    bridge.capture(job, {'cpu_seconds': 4}, 'worker')
    monkeypatch.setattr(bridge.ai_billing, 'user_billing_enabled', lambda uid: True)
    monkeypatch.setattr(bridge.ai_billing, 'provision_inference_job', lambda *args: 'ledger01')
    saved = []
    monkeypatch.setattr(bridge.ai_billing_outbox, 'register_verified', lambda *a, **kw: saved.append((a,kw)))
    assert bridge.register_settlement(job)
    assert saved[0][0][:3] == (job, 'ledger01', 7)
    assert saved[0][1]['source'] == 'worker'


def test_billing_required_prevents_recovery_without_receipt(job, monkeypatch):
    from app import ai_finalization
    monkeypatch.setattr(bridge.ai_billing, 'user_billing_enabled', lambda uid: True)
    monkeypatch.setattr(ai_finalization.ai_publish_outbox, 'status', lambda jid: {'state':'published'})
    assert not ai_finalization.readiness(job)['ready']
    assert not queue.reconcile_published_audio(job)

def test_optout_remains_recoverable(job, monkeypatch):
    from app import ai_finalization
    monkeypatch.setattr(bridge.ai_billing, 'user_billing_enabled', lambda uid: False)
    monkeypatch.setattr(ai_finalization.ai_publish_outbox, 'status', lambda jid: {'state':'published'})
    assert ai_finalization.readiness(job)['ready']
