"""Assigned quota pricing, free grants, trial conversion and per-user billing modes."""
import pytest
from app import resource_accounts as r,resource_entitlements as e,ai_billing,auth
from test_r210_subscriptions import account as quota_account,finish,plan  # noqa: F401


@pytest.fixture
def account(request):
    return request.getfixturevalue('quota_account')


@pytest.fixture
def clock(monkeypatch):
    value=[1802822400]
    monkeypatch.setattr(r.time,'time',lambda:value[0])
    return value


def test_paid_quota_prices_empty_capacity_only_for_assignment(account,clock):
    plan(account);r.grant(account,10000,'capacity funding',1,'quota-pricing-funds')
    e.set_storage(account,3*e.GIB,actor=1,reason='Paid quota increase')
    assert r.state(account)['credits_micro']==10000
    clock[0]+=3600
    state=r.state(account)
    assert state['credits_micro']==9800 and state['used']['storage_bytes']==0
    assert state['storage_extension']['paid_bytes']==2*e.GIB
    # Lower capacity: prior hours remain charged, future hours cost zero.
    e.set_storage(account,e.GIB,actor=account,owner=True,key='reduce-capacity-key')
    clock[0]+=7200
    assert r.state(account)['credits_micro']==9800
    report=e.storage_report(account,clock[0]-10800,clock[0])
    assert report['cost_micro']==200 and report['gb_hours']==2 and report['duration_seconds']==3600
    assert e.storage_report(account,clock[0]-9000,clock[0]-7200)['cost_micro']==100


def test_free_admin_capacity_stops_charges_without_resetting_period(account,clock):
    start=plan(account)['period']['start'];r.grant(account,10000,'funding',1,'free-capacity-funds')
    e.set_storage(account,2*e.GIB,actor=1,reason='Paid capacity')
    clock[0]+=3600
    e.set_storage(account,4*e.GIB,actor=1,free=True,reason='Sponsored storage')
    clock[0]+=7200
    state=r.state(account)
    assert state['period']['start']==start and state['credits_micro']==9900
    assert state['storage_extension']['free_bytes']==3*e.GIB and state['storage_extension']['paid_bytes']==0
    report=e.storage_report(account,start,clock[0]);assert report['cost_micro']==100
    assert any(x['free_bytes']==3*e.GIB and x['cost_micro']==0 for x in report['segments'])
    with pytest.raises(ValueError,match='Only administrators'):e.set_storage(account,5*e.GIB,actor=account,owner=True,free=True)


def test_tariff_boundaries_future_and_idempotent_storage_debit(account,clock):
    start=clock[0];plan(account);r.grant(account,10000,'funding',1,'tariff-capacity-funds')
    e.set_storage(account,2*e.GIB,actor=1,reason='Paid capacity')
    clock[0]+=1800;ai_billing.set_price('disk_gb_hours',200,valid_from=clock[0]);clock[0]+=1800
    assert r.state(account)['credits_micro']==9850
    assert r.state(account)['credits_micro']==9850
    with auth.db() as c:
        segments=e.storage_segments(c,account,start,clock[0]+3600)
        assert sum(x['cost_micro'] for x in segments)==150
        quantities,costs=ai_billing._priced_storage_usage(c,start,clock[0]+3600,account)
    assert sum(costs.values())==150 and sum(quantities.values())==0
    # A historical quota view must not refund already accrued storage credits.
    r.state(account,at=start+1)
    assert r.state(account)['credits_micro']==9850


def test_trial_inherits_week_and_renews_once_on_selected_plan(account,clock):
    r.configure({'enabled':True,'self_service':True,'credits_enabled':True})
    cfg=r.config();monthly=next(p for p in cfg['plans'] if p['code']=='month');monthly['price_micro']=1234
    r.configure({'plans':[monthly]})
    r.subscribe(account,'trial',0,next_plan='month',next_price=1234)
    r.grant(account,5000,'trial renewal funds',1,'trial-renewal-funds');s=r.state(account)
    week=next(p for p in cfg['plans'] if p['code']=='week')
    assert s['subscription']=='trial' and s['limits']['cpu_seconds']==week['cpu_seconds']
    assert s['limits']['storage_bytes']==week['storage_bytes'] and s['credits_micro']==5000
    assert s['period']['end']-s['period']['start']==7*86400 and not s['trial_available']
    clock[0]+=7*86400
    s=r.state(account);assert s['subscription']=='month' and s['credits_micro']==5000
    assert r.state(account)['credits_micro']==5000
    assert s['period']['start']==clock[0]
    r.cancel_renewal(account);clock[0]=s['period']['end']
    with pytest.raises(ValueError,match='already used'):r.subscribe(account,'trial',0)


def test_trial_bad_next_quote_rolls_back_and_default_is_week(account,clock):
    r.configure({'enabled':True,'self_service':True,'credits_enabled':True})
    with pytest.raises(ValueError,match='price'):r.subscribe(account,'trial',0,next_plan='month',next_price=999)
    assert r.state(account)['trial_available'] and r.state(account)['subscription'] is None
    s=r.subscribe(account,'trial',0)
    assert s['next_plan']['plan']=='week'
    cfg=r.config();p=next(p for p in cfg['plans'] if p['code']=='week');p['price_micro']=10000;r.configure({'plans':[p]})
    # The first renewal honors the price disclosed when selecting the trial.
    clock[0]+=7*86400
    assert r.state(account)['funded'] and r.state(account)['credits_micro']==0


def test_trial_cancel_and_change_next_plan_preserve_current_quotas(account,clock):
    r.configure({'enabled':True,'self_service':True,'credits_enabled':True});s=r.subscribe(account,'trial',0)
    start=s['period']['start'];clock[0]+=1
    e.next_plan(account,'year',0)
    assert r.state(account)['subscription']=='trial' and r.state(account)['period']['start']==start
    assert r.state(account)['next_plan']['plan']=='year'
    r.cancel_renewal(account);clock[0]=start+7*86400
    assert r.state(account)['subscription'] is None
    jid=finish(account,1)
    with auth.db() as c:assert e.policy(c,account)['subscriptions_allowed']
    assert jid


def test_unfunded_trial_renewal_waits_for_credits(account,clock):
    r.configure({'enabled':True,'self_service':True,'credits_enabled':True});cfg=r.config()
    p=next(p for p in cfg['plans'] if p['code']=='week');p['price_micro']=100;r.configure({'plans':[p]})
    r.subscribe(account,'trial',0);clock[0]+=7*86400
    assert r.state(account)['funded']
    finish(account,1)
    r.grant(account,100,'renewal funding',1,'paused-renewal-funds')
    assert r.state(account)['funded'] and r.state(account)['credits_micro']==100


def test_admin_disables_self_service_default_is_allowed(account,clock):
    r.configure({'enabled':True,'self_service':True,'credits_enabled':True})
    assert r.state(account)['policy']['subscriptions_allowed']
    e.set_policy(account,{'subscriptions_allowed':False},1)
    with pytest.raises(ValueError,match='not enabled'):r.subscribe(account,'trial',0)
    # Administrators can still assign a promotional plan.
    assert r.assign(account,{'plan':'week','promo':'Admin granted'},1)['subscription']=='week'


def test_free_manual_quotas_and_disabled_subscription_billing(account,clock):
    r.assign(account,{'cpu_seconds':100,'gpu_seconds':100},1)
    with pytest.raises(ValueError,match='active subscription'):r.grant(account,1000,'prepaid funds',1,'paygo-funds-key')
    finish(account,2,3);clock[0]+=1
    e.set_policy(account,{'subscriptions_allowed':False,'credit_billing':True},1)
    jid=finish(account,2,3)
    assert r.state(account)['credits_micro']==0 and not r.state(account)['credits_enabled']
    with auth.db() as c:
        row=dict(c.execute('SELECT * FROM ai_compute_jobs WHERE id=?',(jid,)).fetchone())
        assert ai_billing._rates_for_jobs(c,[row])[jid]['cpu_seconds']==0
    assert r.state(account)['used']['cpu_seconds']>=2


def test_paygo_without_membership_is_unavailable_but_usage_is_counted(account,clock):
    e.set_policy(account,{'credit_billing':True},1)
    with pytest.raises(ValueError,match='active subscription'):r.grant(account,100,'prepaid funds',1,'paygo-no-membership')
    finish(account,11)
    assert not r.state(account)['policy']['credit_billing']
    assert r.state(account)['used']['cpu_seconds']==11 and r.state(account)['credits_micro']==0


def test_occupied_storage_without_subscription_cannot_spend_credits(account,clock):
    start=clock[0];ai_billing.record_persistent_storage(account,e.GIB,sampled_at=start)
    clock[0]+=1800;e.set_policy(account,{'credit_billing':True},1)
    clock[0]+=1800;ai_billing.record_persistent_storage(account,e.GIB,sampled_at=clock[0])
    assert r.state(account)['credits_micro']==0
    with auth.db() as c:assert sum(x['cost_micro'] for x in e.credit_storage_segments(c,account,start,clock[0]))==0


def test_paid_quota_spans_lazy_renewals_and_cancel_stops_charge(account,clock):
    start=clock[0];plan(account);r.grant(account,100000,'multi-day storage',1,'storage-multi-days')
    e.set_storage(account,2*e.GIB,actor=1,reason='Extra quota')
    clock[0]+=2*86400+3600
    assert r.state(account)['credits_micro']==100000-4900
    r.cancel_renewal(account);clock[0]=start+4*86400
    assert r.state(account)['credits_micro']==100000-7200
    assert r.state(account)['subscription'] is None


def test_concurrent_trial_activation_cannot_reuse_trial(account,clock):
    from concurrent.futures import ThreadPoolExecutor
    r.configure({'enabled':True,'self_service':True,'credits_enabled':True})
    def activate(_):
        try:r.subscribe(account,'trial',0);return True
        except ValueError:return False
    with ThreadPoolExecutor(max_workers=2) as pool:assert sum(pool.map(activate,range(2)))==1
    with auth.db() as c:assert c.execute('SELECT count(*) FROM resource_trial_uses WHERE user_id=?',(account,)).fetchone()[0]==1


def test_new_routes_enforce_roles_and_validate_payloads(account,monkeypatch,clock):
    from fastapi.testclient import TestClient
    from app import main
    from test_r210_legal_documents import cookie
    monkeypatch.setattr(main,'NATIVE_SINGLE_USER',False);monkeypatch.setattr(main,'check_basic_auth',lambda request:False)
    monkeypatch.delenv('MTA_ALLOW_INSECURE_NO_AUTH',raising=False)
    client=TestClient(main.app);client.cookies.update(cookie(account));headers={'X-MTA-Request':'1'}
    assert client.patch('/api/admin/subscriptions/users/'+str(account)+'/policy',json={'credit_billing':True},headers=headers).status_code==403
    assert client.get('/api/account/subscription/storage-report?start=1&end='+str(clock[0])).status_code==200
    assert client.get('/api/account/subscription/storage-report?start=3&end=1').status_code==422
    assert client.put('/api/account/subscription/storage',json={'quota_bytes':10,'request_id':'valid-test-key','max_rate_micro':100,'free':True},headers=headers).status_code==422
    client.cookies.update(cookie(auth.find_user('admin')['id']))
    url='/api/admin/subscriptions/users/'+str(account)+'/policy'
    assert client.patch(url,json={'credit_billing':True}).status_code==403
    assert client.patch(url,json={'credit_billing':True},headers=headers).status_code==200
    assert client.get('/api/admin/subscriptions/users/'+str(account)+'/storage-report?start=1&end='+str(clock[0])).status_code==200


def test_plan_cards_and_storage_report_render_in_both_languages():
    import subprocess
    from pathlib import Path
    source=(Path(__file__).parents[1]/'app/static/subscriptions.js').read_text().replace('const personal=document.querySelector','window.ResourceViews={planCards,storageReport};const personal=document.querySelector')
    script="""const vm=require('vm'),assert=require('assert');const ctx={document:{querySelector(){return null}},window:{MtaLocale:{language:'en'},addEventListener(){}}};vm.createContext(ctx);vm.runInContext(process.argv[1],ctx);for(const lang of ['en','it']){ctx.window.MtaLocale.language=lang;const markup=ctx.window.ResourceViews.planCards({trial_available:true,plans:[{code:'trial',cpu_seconds:35*3600,gpu_seconds:35*3600,storage_bytes:5*1024**3,price_micro:0},{code:'week',cpu_seconds:35*3600,gpu_seconds:35*3600,storage_bytes:5*1024**3,price_micro:1234}]});assert(markup.includes('trial-plan'));assert(markup.includes('data-trial-next'));assert(markup.includes(lang==='it'?'gratuita':'free trial'));const report=ctx.window.ResourceViews.storageReport({gb_hours:2,duration_seconds:3600,cost_micro:100,segments:[{start_ts:1,end_ts:3601,paid_bytes:2*1024**3,free_bytes:0,rate_micro_per_gb_hour:50,cost_micro:100}]});assert(report.includes('<table'));assert(report.includes('2.0000'));} """
    subprocess.run(['node','-e',script,source],check=True,timeout=10)
