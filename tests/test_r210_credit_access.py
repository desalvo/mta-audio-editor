"""Paid access, nominal credit quotes, capped charges and existing-session safety."""
import pytest
from app import auth,ai_billing,resource_accounts as r,resource_entitlements as e,resource_access as a
from test_r210_subscriptions import account as quota_account,plan,finish  # noqa: F401


@pytest.fixture
def account(request):return request.getfixturevalue('quota_account')


def test_required_access_live_policy_and_admin_exemption(account):
    s=e.set_policy(account,{'access_required':True},1)
    assert not s['policy']['credit_billing'] and s['access']['blocked'] and a.quick_required(account)
    with pytest.raises(ValueError,match='SUBSCRIPTION_REQUIRED'):ai_billing.create_job(account,'whisper')
    with pytest.raises(ValueError,match='active subscription'):r.grant(account,100,'sponsored access',1,'paid-access-credits')
    plan(account)
    assert not a.status(account)['blocked']
    with pytest.raises(ValueError,match='Administrators'):e.set_policy(auth.find_user('admin')['id'],{'access_required':True},1)
    assert not a.status(auth.find_user('admin')['id'])['blocked']


def test_zero_price_plan_keeps_limits_and_credit_overages(account):
    e.set_policy(account,{'access_required':True},1);plan(account)
    assert not a.status(account)['blocked']
    finish(account,10)
    with pytest.raises(ValueError,match='quota exceeded'):ai_billing.create_job(account,'whisper')
    r.grant(account,7,'small credit grant',1,'zero-plan-overage')
    jid=ai_billing.create_job(account,'whisper')
    assert r.checkpoint(account,jid,{'cpu_seconds_estimated':1000}) is False
    ai_billing.finish_job(jid,'done',{'cpu_seconds':1000},source='cgroup')
    assert r.state(account)['credits_micro']==0
    with auth.db() as c:
        row=c.execute('SELECT * FROM resource_job_budgets WHERE job_id=?',(jid,)).fetchone()
        assert row['gross_micro']==10000 and row['waived_micro']==9993
        assert r._used(c,account,0,2**40)['cpu_seconds']==1010


def test_nominal_credit_value_never_revalues_old_money(account):
    plan(account)
    s=a.grant_credits(account,10,100000,'free promotional credits',1,'nominal-grant-key')
    assert s['credits_micro']==1000000 and s['credits']==10
    r.configure({'credit_value_micro':200000})
    assert r.state(account)['credits_micro']==1000000 and r.state(account)['credits']==5
    with pytest.raises(ValueError,match='Credit value changed'):a.grant_credits(account,1,100000,'outdated quote',1,'outdated-quote-key')
    with pytest.raises(ValueError):r.configure({'credit_value_micro':0})
    with pytest.raises(ValueError):a.grant_credits(account,True,200000,'bad amount',1,'bad-amount-key')


def test_later_grant_does_not_increase_admitted_job_ceiling(account):
    plan(account)
    e.set_policy(account,{'credit_billing':True},1);r.grant(account,10,'initial funds',1,'budget-initial-fund')
    jid=ai_billing.create_job(account,'whisper')
    assert not r.checkpoint(account,jid,{'cpu_seconds_estimated':100})
    r.grant(account,1000,'future jobs funds',1,'budget-later-funds')
    ai_billing.finish_job(jid,'done',{'cpu_seconds':100},source='cgroup')
    assert r.state(account)['credits_micro']==1000
    ai_billing.finish_job_idempotent(jid,'done',{'cpu_seconds':100},source='cgroup')
    assert r.state(account)['credits_micro']==1000


def test_defaults_only_fill_unconfigured_tariffs_prospectively(account):
    with auth.db() as c:
        c.execute("DELETE FROM ai_resource_price_history WHERE resource='gpu_seconds'");c.execute("DELETE FROM ai_resource_prices WHERE resource='gpu_seconds'")
    e.set_policy(account,{'access_required':True},1)
    assert ai_billing.prices()['gpu_seconds']==10 and ai_billing.prices()['cpu_seconds']==10
    assert 'gpu_seconds' not in ai_billing.prices(at=1)
    ai_billing.set_price('gpu_seconds',0)
    e.set_policy(account,{'access_required':True},1)
    assert ai_billing.prices()['gpu_seconds']==0


def test_existing_session_redirect_new_work_and_literal_user_search(account,monkeypatch):
    from fastapi.testclient import TestClient
    from app import main
    from test_r210_legal_documents import cookie
    monkeypatch.setattr(main,'NATIVE_SINGLE_USER',False);monkeypatch.setattr(main,'check_basic_auth',lambda request:False)
    monkeypatch.delenv('MTA_ALLOW_INSECURE_NO_AUTH',raising=False)
    client=TestClient(main.app);client.cookies.update(cookie(account));headers={'X-MTA-Request':'1'}
    assert client.get('/api/admin/subscription-users?q=quota').status_code==403
    e.set_policy(account,{'access_required':True},1)
    assert client.get('/',follow_redirects=False).status_code==303
    assert client.get('/account').status_code==200
    assert client.get('/api/account/access').json()['blocked']
    assert client.post('/api/projects',json={},headers=headers).status_code==402
    client.cookies.update(cookie(auth.find_user('admin')['id']))
    for query in ('quota','OTA@EXAMPLE','quota-user'):
        rows=client.get('/api/admin/subscription-users',params={'q':query}).json();assert len(rows)==1 and rows[0]['id']==account
    assert client.get('/api/admin/subscription-users?q=%25').json()==[]
    assert client.put('/api/admin/subscriptions/tariffs',json={'cpu_seconds':1,'gpu_seconds':10,'disk_gb_hours':200000},headers=headers).status_code==200
    plan(account)
    assert client.post('/api/admin/subscriptions/users/'+str(account)+'/credits',json={'credits':2,'credit_value_micro':100000,'reason':'free grant','request_id':'http-grant-request'},headers=headers).status_code==200
    assert client.get('/').status_code==200


def test_tariff_bulk_failure_rolls_back_all_categories(account,monkeypatch):
    from app import resource_routes
    from fastapi import HTTPException
    monkeypatch.setattr(auth,'require_admin',lambda request:{'id':1})
    old=ai_billing.prices()
    original=ai_billing.set_price
    def fail(resource,*args,**kwargs):
        if resource=='gpu_seconds':raise ValueError('simulated closed period')
        return original(resource,*args,**kwargs)
    monkeypatch.setattr(ai_billing,'set_price',fail)
    with pytest.raises(HTTPException):resource_routes.tariffs(None,{'cpu_seconds':100,'gpu_seconds':20,'disk_gb_hours':1})
    assert ai_billing.prices()==old


def test_admission_freezes_tariffs_even_with_same_second_change(account):
    plan(account)
    e.set_policy(account,{'credit_billing':True},1);r.grant(account,1000,'funds',1,'tariff-freeze-funds')
    jid=ai_billing.create_job(account,'whisper')
    ai_billing.set_price('cpu_seconds',9000)
    ai_billing.finish_job(jid,'done',{'cpu_seconds':12},source='cgroup')
    assert r.state(account)['credits_micro']==980


def test_budget_schema_upgrade_and_capped_legacy_running_job(account):
    plan(account)
    e.set_policy(account,{'credit_billing':True},1);r.grant(account,10,'funds',1,'legacy-upgrade-funds')
    jid=ai_billing.create_job(account,'whisper')
    with auth.db() as c:
        c.execute('DROP TABLE resource_job_budgets')
        c.execute('ALTER TABLE resource_config DROP COLUMN credit_value_micro')
    ai_billing.finish_job(jid,'done',{'cpu_seconds':20},source='cgroup')
    assert r.state(account)['credits_micro']==0


def test_child_workers_share_one_queue_ceiling_without_free_second_step(account):
    plan(account)
    from app.ai_global_execution import current_job
    e.set_policy(account,{'credit_billing':True},1);r.grant(account,100,'shared queue funds',1,'shared-queue-wallet')
    token=current_job.set('same-queue-job')
    try:
        first=ai_billing.create_job(account,'whisper');second=ai_billing.create_job(account,'chords')
        ai_billing.finish_job(first,'done',{'cpu_seconds':12},source='cgroup')
        r.grant(account,1000,'next jobs funds',1,'shared-queue-topup')
        ai_billing.finish_job(second,'done',{'cpu_seconds':100},source='cgroup')
        assert r.state(account)['credits_micro']==1000
        with auth.db() as c:
            charges=[row[0] for row in c.execute('SELECT charge_micro FROM resource_job_contracts ORDER BY job_id')]
            assert sorted(charges)==[20,80]
    finally:current_job.reset(token)


def test_unfunded_plan_can_use_available_credits_without_included_allowance(account):
    e.set_policy(account,{'access_required':True},1);plan(account,price_micro=1000)
    r.grant(account,100,'paygo alternative',1,'unfunded-paygo-fund')
    assert not a.status(account)['blocked'] and r.state(account)['funded']
    jid=ai_billing.create_job(account,'whisper')
    assert not r.checkpoint(account,jid,{'cpu_seconds_estimated':100})
    ai_billing.finish_job(jid,'done',{'cpu_seconds':100},source='cgroup')
    assert r.state(account)['credits_micro']==0


def test_authorized_running_overage_not_cancelled_when_tariff_changes(account):
    plan(account);r.grant(account,10,'overage funds',1,'overage-tariff-change')
    jid=ai_billing.create_job(account,'whisper');ai_billing.set_price('cpu_seconds',0)
    assert not r.checkpoint(account,jid,{'cpu_seconds_estimated':100})
    ai_billing.finish_job(jid,'done',{'cpu_seconds':100},source='cgroup')
    assert r.state(account)['credits_micro']==0


def test_no_initial_credits_does_not_authorize_free_quota_overages(account):
    plan(account)
    jid=ai_billing.create_job(account,'whisper')
    assert r.checkpoint(account,jid,{'cpu_seconds_estimated':11})


def test_admitted_queue_can_finish_further_steps_after_wallet_reaches_zero(account):
    plan(account)
    from app.ai_global_execution import current_job
    e.set_policy(account,{'access_required':True},1);r.grant(account,10,'whole job funds',1,'whole-job-credit-cap')
    token=current_job.set('continuing-credit-queue')
    try:
        first=ai_billing.create_job(account,'whisper')
        ai_billing.finish_job(first,'done',{'cpu_seconds':20},source='cgroup')
        assert not a.status(account)['blocked']
        second=ai_billing.create_job(account,'chords')
        assert not r.checkpoint(account,second,{'cpu_seconds_estimated':100})
        ai_billing.finish_job(second,'done',{'cpu_seconds':100},source='cgroup')
        assert r.state(account)['credits_micro']==0
    finally:current_job.reset(token)
    with pytest.raises(ValueError,match='quota exceeded'):ai_billing.create_job(account,'whisper')
