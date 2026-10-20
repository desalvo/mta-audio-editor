"""Explicit estimate policy, sealed per-job provenance and immutable billing."""
import json
import pytest
from app import ai_billing,ai_compute_diagnostics
from app.auth import db,init_auth_db
from app.ai_trusted_estimates import promote,require_evidence,SOURCE


@pytest.fixture
def job(tmp_path,monkeypatch):
    monkeypatch.setenv('MTA_DATA_DIR',str(tmp_path));init_auth_db()
    with db() as con:
        con.execute("INSERT INTO users(username,email,password_hash,active,role,created_at,updated_at) VALUES('estimated','estimate@example.test','unused',1,'user',1,1)")
        uid=con.execute("SELECT id FROM users WHERE username='estimated'").fetchone()[0]
    return uid,ai_billing.create_job(uid,'whisper',started_at=1760140800)


def test_valid_estimates_are_billable_but_remain_labelled(job):
    uid,jid=job
    ai_billing.set_price('cpu_seconds',1000,valid_from='2025-10-01')
    ai_billing.set_price('gpu_seconds',2000,valid_from='2025-10-01')
    ai_compute_diagnostics.store(jid,{'cpu_seconds_estimated':2.5,'gpu_seconds_estimated':3.5})
    usage,source=promote(jid,{},'unmetered')
    assert source==SOURCE and usage=={'cpu_seconds':2.5,'gpu_seconds':3.5}
    ai_billing.finish_job(jid,'done',usage,source=source,finished_at=1760140810)
    report=ai_billing.report('custom',user_id=uid,start='2025-10-11',end='2025-10-11')
    assert report['total_micro']==9500
    bill=ai_billing.close_period(uid,'2025-10-11','2025-10-11')
    assert bill['total_micro']==9500
    with db() as con:
        row=con.execute('SELECT resource_source FROM ai_compute_jobs WHERE id=?',(jid,)).fetchone()
        assert row[0]==SOURCE


def test_unsealed_or_changed_numbers_cannot_be_billed(job):
    _,jid=job
    with pytest.raises(ValueError,match='evidence'):
        ai_billing.finish_job(jid,'done',{'gpu_seconds':999},source=SOURCE)
    ai_compute_diagnostics.store(jid,{'gpu_seconds_estimated':2})
    usage,source=promote(jid,{'cpu_seconds':1},'worker')
    with pytest.raises(ValueError):require_evidence(jid,{**usage,'gpu_seconds':999})
    with pytest.raises(ValueError):require_evidence(jid,{**usage,'gpu_energy_joules':10})
    ai_billing.finish_job(jid,'done',usage,source=source)
    ai_billing.finish_job_idempotent(jid,'done',usage,source=source)
    ai_compute_diagnostics.store(jid,{'gpu_seconds_estimated':100})
    require_evidence(jid,usage)


def test_verified_values_take_precedence(job):
    _,jid=job;ai_compute_diagnostics.store(jid,{'cpu_seconds_estimated':200,'gpu_seconds_estimated':500})
    usage,source=promote(jid,{'cpu_seconds':2,'gpu_seconds':3},'gpu-kernel-verified')
    assert usage=={'cpu_seconds':2,'gpu_seconds':3} and source=='gpu-kernel-verified'


@pytest.mark.parametrize('value',[float('nan'),float('inf'),-1,True,'4',0])
def test_invalid_or_stalled_gpu_never_promoted(job,value):
    _,jid=job
    # Corrupt persistence is also revalidated, not just store() inputs.
    ai_compute_diagnostics.store(jid,{'gpu_seconds_estimated':1})
    with db() as con:con.execute('UPDATE ai_compute_job_diagnostics SET payload=? WHERE job_id=?',(json.dumps({'gpu_seconds_estimated':value}),jid))
    usage,source=promote(jid,{'cpu_seconds':1},'worker')
    assert usage=={'cpu_seconds':1} and source=='worker'


def test_policy_can_be_disabled_and_failed_jobs_cannot_be_promoted(job,monkeypatch):
    _,jid=job;ai_compute_diagnostics.store(jid,{'gpu_seconds_estimated':2})
    monkeypatch.setenv('MTA_TRUST_AI_DIAGNOSTIC_ESTIMATES','false')
    assert promote(jid,{'cpu_seconds':1},'worker')==({'cpu_seconds':1},'worker')
    monkeypatch.setenv('MTA_TRUST_AI_DIAGNOSTIC_ESTIMATES','true')
    ai_billing.finish_job(jid,'failed',source='unmetered')
    with pytest.raises(ValueError,match='Running'):promote(jid,{},'unmetered')


def test_worker_supplied_gpu_cannot_be_laundered_as_estimate(job):
    _,jid=job
    ai_compute_diagnostics.store(jid,{'cpu_seconds_estimated':1})
    with pytest.raises(ValueError,match='Untrusted'):
        promote(jid,{'gpu_seconds':999},'worker')


def test_readiness_requires_collector_or_accepted_evidence(job,monkeypatch):
    from app.ai_billing_readiness import check
    monkeypatch.delenv('MTA_AI_TORCH_PROFILER',raising=False)
    monkeypatch.delenv('MTA_ACE_GPU_PROFILER',raising=False)
    before=check()['components']['gpu_per_job']
    assert before['trusted_estimates'] and not before['accepted_estimate_evidence_available']
    _,jid=job;ai_compute_diagnostics.store(jid,{'gpu_seconds_estimated':2})
    promote(jid,{'cpu_seconds':1},'worker')
    after=check()['components']['gpu_per_job']
    assert after['ready'] and after['accepted_estimate_evidence_available']


def test_account_limits_distinguish_accounted_and_verified(job):
    from app import account_limits
    uid,jid=job
    ai_compute_diagnostics.store(jid,{'gpu_seconds_estimated':3.5})
    usage,source=promote(jid,{'cpu_seconds':2.5},'worker')
    ai_billing.finish_job(jid,'done',usage,source=source)
    result=account_limits.summary(uid,{'used_bytes':0},at=1760140820)
    gpu=result['resources']['gpu']
    assert gpu['accounted_seconds']==3.5 and gpu['trusted_estimated_seconds']==3.5
    assert gpu['verified_seconds'] is None


def test_accepted_consumption_exposed_in_queue_and_report(job, tmp_path, monkeypatch):
    from app.ai_queue_usage import enrich
    from app import ai_usage_reporting, ai_arranger_runtime as queue
    monkeypatch.setattr(queue, '_ROOT', tmp_path/'queue')
    uid,jid=job
    with db() as con:
        con.execute('UPDATE ai_compute_jobs SET queue_job_id=? WHERE id=?',('accepted-job',jid))
    ai_compute_diagnostics.store(jid,{'cpu_seconds_estimated':2.5,'gpu_seconds_estimated':3.5})
    usage,source=promote(jid,{},'unmetered')
    ai_billing.finish_job(jid,'done',usage,source=source,finished_at=1760140810)
    projected=enrich({'job_id':'accepted-job','actor_user_id':uid,'state':'completed'})
    assert projected['cpu_seconds']==2.5 and projected['gpu_seconds']==3.5
    assert projected['resources_accounted'] and projected['gpu_metrics_status']=='accounted'
    report=ai_usage_reporting.snapshot(uid,1760140800,1760140820)
    assert report['usage']['cpu_seconds']==2.5 and report['usage']['gpu_seconds']==3.5
    assert 'gpu_seconds_estimated' not in report['diagnostic']
    # Mutable progress cannot overwrite already sealed consumption.
    ai_compute_diagnostics.store(jid,{'gpu_seconds_estimated':999})
    assert enrich({'job_id':'accepted-job','actor_user_id':uid})['gpu_seconds']==3.5
    # Missing evidence never upgrades the queue to accounted usage.
    with db() as con:con.execute('DELETE FROM ai_trusted_estimate_evidence WHERE job_id=?',(jid,))
    projected=enrich({'job_id':'accepted-job','actor_user_id':uid})
    assert projected.get('gpu_seconds') is None and not projected.get('resources_accounted')


def test_cpu_only_acceptance_does_not_claim_accounted_gpu(job):
    from app.ai_queue_usage import enrich
    uid,jid=job
    with db() as con:con.execute('UPDATE ai_compute_jobs SET queue_job_id=? WHERE id=?',('cpu-only',jid))
    ai_compute_diagnostics.store(jid,{'cpu_seconds_estimated':1.25})
    usage,source=promote(jid,{},'unmetered')
    ai_billing.finish_job(jid,'done',usage,source=source)
    projected=enrich({'job_id':'cpu-only','actor_user_id':uid})
    assert projected['cpu_seconds']==1.25 and projected['resources_accounted']
    assert projected.get('gpu_seconds') is None
    assert projected.get('gpu_metrics_status')!='accounted'
