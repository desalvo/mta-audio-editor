"""Real scheduler/subprocess -> immutable owner receipt -> publication -> ledger."""
import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import pytest
from app import ai_arranger_runtime as queue,ai_billing,ai_metering_agent
from app import ai_metering_bridge as bridge,ai_billing_outbox as billing,ai_publish_outbox as publication
from app import ai_finalization,auth
from app.ai_global_execution import current_job
from app.deferred_execution_owner import execution_scope
from app.regime_operation_fence import FenceBlocked
from test_r208_unified_adapter_billing_e2e import operator as operator,source_audio  # noqa: F401


@pytest.fixture(params=['arranger','remix'])
def setup(operator,tmp_path,monkeypatch,request):
    monkeypatch.setattr(queue,'_ROOT',tmp_path/'queue')
    worker=tmp_path/'ace_worker.py'
    worker.write_text('''import argparse,wave
p=argparse.ArgumentParser();p.add_argument('--request');p.add_argument('--output');a=p.parse_args()
with wave.open(a.output,'wb') as f:
 f.setnchannels(1);f.setsampwidth(2);f.setframerate(44100);f.writeframes(b'\\0\\0'*256)
''')
    worker.chmod(0o700);monkeypatch.setenv('MTA_AI_WORKER_ACE_STEP_EXECUTABLE',str(worker))
    job='owner_e2e_123'
    operation=request.param
    queue.start('project1',operation,None,job_id=job,defer_spawn=True,payload={'schema_version':1,'actor_user_id':operator,'adapter':operation})
    ledger=ai_billing.provision_inference_job(job,operator,operation)
    return operator,job,ledger


def generate(uid,job):
    data,meta=ai_metering_agent.execute_registered_worker(uid,'ace-step',{},source_wav=source_audio())
    bridge.capture(job,meta['usage'],meta['metering_source'])
    return data


def test_real_scheduler_deferred_completion_has_one_owner_and_charge(setup):
    uid,job,ledger=setup;published=[]
    def run(progress,stop):
        audio=generate(uid,job)
        receipt=publication.stage(job,'project1',audio,{'mode':'arranger'})
        assert 'owner_json' not in receipt
        publication.recover(lambda *args:published.append(args[0]),job_id=job)
    assert queue.activate(job,run)
    deadline=time.monotonic()+15
    while time.monotonic()<deadline:
        state=queue.get(job)
        if state['state'] in ('completed','failed','interrupted'):break
        threading.Event().wait(.03)
    assert state['state']=='completed',state
    assert published==[job] and billing.inspect(job)['state']=='delivered'
    with auth.db() as c:
        assert c.execute('SELECT status FROM ai_compute_jobs WHERE id=?',(ledger,)).fetchone()[0]=='done'
        assert c.execute('SELECT state FROM regime_worker_claims WHERE operation_id=?',('job:ledger:'+ledger,)).fetchone()[0]=='finished'
    assert ai_finalization.readiness(job)['ready']


def staged_execution(setup,*,publish_now):
    uid,job,ledger=setup
    assert queue._claim(job)
    with execution_scope(job,threading.Event()) as owner:
        context=current_job.set(job)
        try:audio=generate(uid,job)
        finally:current_job.reset(context)
        publication.stage(job,'project1',audio,{'mode':'arranger'})
        if publish_now:publication.recover(lambda *_:None,job_id=job)
        receipt=owner.receipt()
    with queue._db() as c:c.execute("UPDATE jobs SET state='interrupted' WHERE job_id=?",(job,))
    return job,ledger,receipt


@pytest.mark.parametrize('publish_now',[False,True])
def test_crash_after_metering_or_publication_recovers_without_reexecution(setup,monkeypatch,publish_now):
    job,ledger,receipt=staged_execution(setup,publish_now=publish_now)
    # No execution context remains after the simulated supervisor crash.
    if not publish_now:publication.recover(lambda *_:None,job_id=job)
    assert ai_finalization.reconcile(job)
    assert ai_finalization.reconcile(job)
    assert queue.get(job)['state']=='completed'
    with billing._db() as c:
        intent=json.loads(c.execute('SELECT intent_json FROM deliveries').fetchone()[0])
        assert intent['worker_id']==receipt['worker_id'] and intent['claim_token']==receipt['claim_token']
    assert 'claim_token' not in json.dumps(billing.inspect(job))
    with pytest.raises(FenceBlocked):
        with execution_scope(job,threading.Event()):pytest.fail('completed inference ran again')
    with auth.db() as c:assert c.execute('SELECT count(*) FROM ai_compute_jobs WHERE id=?',(ledger,)).fetchone()[0]==1


def test_ledger_commit_before_ack_retries_with_original_owner(setup):
    job,ledger,_=staged_execution(setup,publish_now=True)
    bridge.register_settlement(job)
    with pytest.raises(RuntimeError):billing.deliver(job_id=job,on_applied=lambda _:(_ for _ in ()).throw(RuntimeError('crash before ack')))
    assert billing.inspect(job)['state']=='pending'
    with ThreadPoolExecutor(max_workers=3) as pool:
        results=list(pool.map(lambda _:billing.deliver(job_id=job),range(3)))
    assert sum(results)==1 and ai_finalization.reconcile(job)
    with auth.db() as c:assert c.execute('SELECT status FROM ai_compute_jobs WHERE id=?',(ledger,)).fetchone()[0]=='done'


def test_claimed_inference_rejects_missing_or_forged_owner(setup):
    uid,job,ledger=setup
    assert queue._claim(job)
    with execution_scope(job,threading.Event()):
        with pytest.raises((ValueError,FenceBlocked)):
            billing.register_verified(job,ledger,uid,'done',{'cpu_seconds':1},source='worker')
        with pytest.raises(FenceBlocked):
            billing.register_verified(job,ledger,uid,'done',{'cpu_seconds':1},source='worker',worker_id='forged',claim_token='forged')
    with pytest.raises(FenceBlocked):bridge.capture(job,{'cpu_seconds':1},'worker')
    with pytest.raises(FenceBlocked):publication.stage(job,'project1',source_audio(),{})
    assert billing.inspect(job) is None


def test_unknown_or_changed_owner_blocks_publication_and_settlement(setup):
    job,ledger,_=staged_execution(setup,publish_now=False)
    with auth.db() as c:c.execute('UPDATE regime_worker_claims SET claim_token=? WHERE operation_id=?',('changed','job:ledger:'+ledger))
    with pytest.raises(FenceBlocked):publication.recover(lambda *_:pytest.fail('published with wrong owner'),job_id=job)
    with pytest.raises(FenceBlocked):bridge.register_settlement(job)
    with auth.db() as c:assert c.execute('SELECT status FROM ai_compute_jobs WHERE id=?',(ledger,)).fetchone()[0]=='running'


def test_lost_heartbeat_cancels_and_prevents_new_evidence_or_staging(setup,monkeypatch):
    from app import deferred_execution_owner as owners,regime_worker_claims
    uid,job,ledger=setup
    monkeypatch.setattr(owners,'HEARTBEAT_INTERVAL',.01)
    monkeypatch.setattr(regime_worker_claims,'heartbeat',lambda *a,**kw:(_ for _ in ()).throw(RuntimeError('database unavailable')))
    assert queue._claim(job)
    stop=threading.Event()
    with pytest.raises(FenceBlocked,match='heartbeat failed'):
        with execution_scope(job,stop):
            assert stop.wait(2)
            with pytest.raises(FenceBlocked):bridge.capture(job,{'cpu_seconds':1},'worker')
            with pytest.raises(FenceBlocked):publication.stage(job,'project1',source_audio(),{})
            with pytest.raises(FenceBlocked):owners.credentials_for(ledger)
    assert billing.inspect(job) is None
    with auth.db() as c:
        assert c.execute('SELECT state FROM regime_worker_claims WHERE operation_id=?',('job:ledger:'+ledger,)).fetchone()[0]=='running'


def test_removed_publication_owner_cannot_downgrade_to_legacy(setup):
    job,_,_=staged_execution(setup,publish_now=False)
    with publication._open() as c:c.execute('UPDATE publications SET owner_json=NULL WHERE job_id=?',(job,))
    with pytest.raises(FenceBlocked):publication.recover(lambda *_:pytest.fail('ownerless publication'),job_id=job)
