"""Active contract edits preserve periods, usage and admitted job budgets."""
import pytest
from app import auth,resource_accounts as r,resource_contracts as contracts,ai_billing
from test_r210_subscriptions import account as account,plan,finish  # noqa: F401


def amendment(state,**overrides):
    limits={**state['limits'],**overrides}
    return {'limits':limits,'free_increases':{k:True for k in limits},'reason':'Operator contract change','request_id':'amendment-request-123'}


def test_free_increase_and_decrease_keep_period_and_consumption(account):
    before=plan(account);finish(account,4)
    body=amendment(before,cpu_seconds=20,gpu_seconds=5,storage_bytes=512*1024**2)
    after=contracts.amend(account,body,1)
    assert after['period']['start']==before['period']['start'] and after['period']['end']==before['period']['end']
    assert after['used']['cpu_seconds']==4 and after['limits']==body['limits']
    assert after['included_compute']=={'cpu_seconds':20,'gpu_seconds':5}
    assert contracts.amend(account,body,1)['used']==after['used']


def test_increase_requires_explicit_free_choice_and_credits_if_paid(account):
    before=plan(account);body=amendment(before,cpu_seconds=20);body['free_increases']={}
    with pytest.raises(ValueError,match='free or paid'):contracts.amend(account,body,1)
    body['free_increases']={'cpu_seconds':False};r.configure({'credits_enabled':False})
    with pytest.raises(ValueError,match='Enable subscription credits'):contracts.amend(account,body,1)
    assert r.state(account)['limits']==before['limits']


def test_paid_compute_extension_keeps_included_threshold_and_charges_overages(account):
    before=plan(account);body=amendment(before,cpu_seconds=20);body['free_increases']['cpu_seconds']=False
    after=contracts.amend(account,body,1)
    assert after['limits']['cpu_seconds']==20 and after['included_compute']['cpu_seconds']==10
    r.grant(account,1000,'test credits',1,'extension-credit-grant')
    finish(account,15)
    assert r.state(account)['credits_micro']==950


def test_running_job_keeps_admitted_threshold_on_quota_reduction(account):
    before=plan(account);r.grant(account,1000,'test credits',1,'running-credit-grant')
    jid=ai_billing.create_job(account,'whisper')
    contracts.amend(account,amendment(before,cpu_seconds=2),1)
    ai_billing.finish_job(jid,'done',{'cpu_seconds':8,'gpu_seconds':0},source='gpu-agent')
    assert r.state(account)['credits_micro']==1000
    next_job=ai_billing.create_job(account,'whisper')
    ai_billing.finish_job(next_job,'done',{'cpu_seconds':2,'gpu_seconds':0},source='gpu-agent')
    assert r.state(account)['credits_micro']==980


def test_termination_prorates_elapsed_time_and_is_idempotent(account,monkeypatch):
    clock=[1802822400];monkeypatch.setattr(r.time,'time',lambda:clock[0])
    before=plan(account,price_micro=8_640_000)
    ai_billing.set_user_billing_enabled(account,True)
    clock[0]+=3600
    data={'reason':'Operator ends subscription','request_id':'terminate-request-123'}
    result=contracts.terminate(account,data,1)
    assert result['final_fee_micro']==360_000
    assert contracts.terminate(account,data,1)==result
    assert r.state(account)['subscription'] is None
    with auth.db() as c:
        assert c.execute('SELECT amount_micro FROM resource_plan_charges WHERE user_id=?',(account,)).fetchone()[0]==360_000
        assert not c.execute('SELECT 1 FROM resource_next_plans WHERE user_id=?',(account,)).fetchone()
    assert before['period']['end']==result['original_end']


def test_disabled_user_billing_means_zero_final_fee_and_paid_difference_recorded(account,monkeypatch):
    clock=[1802822400];monkeypatch.setattr(r.time,'time',lambda:clock[0])
    plan(account,price_micro=8_640_000)
    with auth.db() as c:c.execute("UPDATE resource_plan_charges SET status='paid' WHERE user_id=?",(account,))
    clock[0]+=3600
    result=contracts.terminate(account,{'reason':'Refund required','request_id':'terminate-refund-123'},1)
    assert result['final_fee_micro']==0 and result['refund_due_micro']==8_640_000


def test_retry_cannot_change_free_increase_to_paid(account):
    before=plan(account);body=amendment(before,cpu_seconds=20)
    contracts.amend(account,body,1)
    body['free_increases']['cpu_seconds']=False
    with pytest.raises(ValueError,match='Conflicting amendment retry'):
        contracts.amend(account,body,1)
    assert r.state(account)['included_compute']['cpu_seconds']==20


def test_unrelated_edits_preserve_existing_free_storage_extension(account):
    before=plan(account);gib=1024**3
    first=amendment(before,storage_bytes=4*gib)
    after=contracts.amend(account,first,1)
    assert after['storage_extension']['free_bytes']==3*gib
    second=amendment(after,cpu_seconds=20);second['request_id']='second-cpu-edit-123'
    after=contracts.amend(account,second,1)
    assert after['storage_extension']['free_bytes']==3*gib
    assert after['storage_extension']['paid_bytes']==0
    third=amendment(after,storage_bytes=5*gib);third['request_id']='third-paid-disk-123'
    third['free_increases']['storage_bytes']=False
    after=contracts.amend(account,third,1)
    assert after['storage_extension']['free_bytes']==3*gib
    assert after['storage_extension']['paid_bytes']==gib
