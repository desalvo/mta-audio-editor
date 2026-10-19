"""Atomic quota admission, ordinary-tariff credits, renewal and warning regressions."""
import datetime as dt
import pytest
from app import auth,ai_billing,resource_accounts as r,storage


@pytest.fixture
def account(tmp_path,monkeypatch):
    monkeypatch.setenv('MTA_DATA_DIR',str(tmp_path));monkeypatch.setenv('MTA_ADMIN_PASSWORD','a-secure-test-password')
    monkeypatch.setattr(auth,'DATA_ROOT',tmp_path);monkeypatch.setattr(storage,'ROOT',tmp_path/'projects');storage.ROOT.mkdir()
    auth.init_auth_db()
    with auth.db() as c:
        c.execute("INSERT INTO users(username,email,password_hash,role,active,email_confirmed,created_at,updated_at) VALUES('quota-user','quota@example.test','unused','user',1,1,1,1)")
        uid=c.execute("SELECT id FROM users WHERE username='quota-user'").fetchone()[0]
    r.config();ai_billing.set_price('cpu_seconds',10,valid_from=0);ai_billing.set_price('gpu_seconds',20,valid_from=0)
    ai_billing.set_price('disk_gb_hours',100,valid_from=0)
    return uid


def plan(uid,**kwargs):
    cfg=r.config();p=next(p for p in cfg['plans'] if p['code']=='day');p.update(cpu_seconds=10,gpu_seconds=10,storage_bytes=1024**3,**kwargs)
    r.configure({'enabled':True,'credits_enabled':True,'plans':[p]});return r.assign(uid,{'plan':'day','overage':True},1)


def finish(uid,cpu,gpu=0):
    jid=ai_billing.create_job(uid,'whisper');ai_billing.finish_job(jid,'done',{'cpu_seconds':cpu,'gpu_seconds':gpu},source='gpu-agent');return jid


def test_defaults_and_admin_unlimited(account):
    cfg=r.config();assert not cfg['enabled']
    p=next(p for p in cfg['plans'] if p['code']=='day');assert p['cpu_seconds']==p['gpu_seconds']==14400 and p['storage_bytes']==5*1024**3
    annual=next(p for p in cfg['plans'] if p['code']=='year');assert annual['cpu_seconds']==14400*365*2 and annual['storage_bytes']==10*1024**3
    admin=auth.find_user('admin');assert r.state(admin['id'])['limits']==dict.fromkeys(r.RESOURCES)


def test_manual_daily_limits_inherit_storage_and_block(account):
    r.assign(account,{'cpu_seconds':2,'gpu_seconds':None},1)
    assert r.state(account)['limits']['storage_bytes']==5*1024**3
    finish(account,2)
    with pytest.raises(ValueError,match='quota exceeded'):ai_billing.create_job(account,'whisper')


def test_concurrent_limited_jobs_cannot_double_spend(account):
    plan(account);first=ai_billing.create_job(account,'whisper')
    with pytest.raises(ValueError,match='Another'):ai_billing.create_job(account,'demucs')
    ai_billing.finish_job(first,'cancelled',source='unmetered')
    assert ai_billing.create_job(account,'demucs')


def test_overage_ordinary_tariff_credits_and_no_double_invoice(account):
    plan(account);r.grant(account,1000,'test credits',1,'grant-unique-1')
    jid=finish(account,12,13)
    assert r.state(account)['credits_micro']==920
    ai_billing.finish_job_idempotent(jid,'done',{'cpu_seconds':12,'gpu_seconds':13},source='gpu-agent')
    assert r.state(account)['credits_micro']==920
    with auth.db() as c:
        row=dict(c.execute('SELECT * FROM ai_compute_jobs WHERE id=?',(jid,)).fetchone())
        rates=ai_billing._rates_for_jobs(c,[row])[jid]
        assert rates['cpu_seconds']==rates['gpu_seconds']==0
    with auth.db() as c:c.execute('UPDATE ai_compute_jobs SET accounting_excluded=1 WHERE id=?',(jid,))
    assert r.state(account)['credits_micro']==1000


def test_exhausted_credit_blocks_next_job(account):
    plan(account);r.grant(account,1,'tiny credit',1,'tiny-credit-key');finish(account,12)
    assert r.state(account)['credits_micro']==0
    with pytest.raises(ValueError,match='quota exceeded|credits exhausted'):ai_billing.create_job(account,'whisper')


def test_live_checkpoint_and_alerts_are_idempotent(account):
    r.assign(account,{'cpu_seconds':10,'gpu_seconds':10,'storage_bytes':100},1)
    jid=ai_billing.create_job(account,'whisper')
    assert r.checkpoint(account,jid,{'cpu_seconds_estimated':9.6,'gpu_seconds_estimated':9.6}) is False
    assert r.checkpoint(account,jid,{'cpu_seconds_estimated':10}) is True
    r.sample(account,96);r.sample(account,96)
    with auth.db() as c:
        rows=c.execute('SELECT payload FROM resource_notices').fetchall()
        assert len(rows)==9


def test_no_overage_without_opt_in(account):
    plan(account);r.options(account,{'overage':False});r.grant(account,1000,'credits',1,'credits-no-optin')
    finish(account,12)
    assert r.state(account)['credits_micro']==1000
    with pytest.raises(ValueError):ai_billing.create_job(account,'whisper')


def test_credit_retry_validation_and_promo(account,monkeypatch):
    stamp=1802822400;monkeypatch.setattr(r.time,'time',lambda:stamp);plan(account)
    r.grant(account,100,'promotion',1,'promo-credit-key');r.grant(account,100,'promotion',1,'promo-credit-key')
    assert r.state(account)['credits_micro']==100
    with pytest.raises(ValueError):r.grant(account,200,'promotion',1,'promo-credit-key')
    with pytest.raises(ValueError):r.grant(account,float('nan'),'promotion',1,'nan-credit-key')
    stamp+=1
    cfg=r.config();p=cfg['plans'][0];p['price_micro']=99999;r.configure({'enabled':True,'credits_enabled':True,'plans':[p]})
    assert r.assign(account,{'plan':p['code'],'promo':'Complimentary'},1)['funded']


def test_renewal_freezes_plan_and_charges_once(account,monkeypatch):
    stamp=1802822400;monkeypatch.setattr(r.time,'time',lambda:stamp)
    first=plan(account,price_micro=100);r.grant(account,1000,'subscription funds',1,'renewal-credit-key');first=r.state(account)
    assert first['credits_micro']==1000
    assert r.state(account)['credits_micro']==1000
    cfg=r.config();p=next(p for p in cfg['plans'] if p['code']=='day');p['cpu_seconds']=50;r.configure({'plans':[p]})
    assert r.state(account)['limits']['cpu_seconds']==10
    monkeypatch.setattr(r.time,'time',lambda:stamp+86400)
    assert r.state(account)['limits']['cpu_seconds']==50 and r.state(account)['credits_micro']==1000


def test_unfunded_and_cancellation(account,monkeypatch):
    stamp=1802822400;monkeypatch.setattr(r.time,'time',lambda:stamp)
    assert plan(account,price_micro=100)['funded']
    finish(account,1)
    r.grant(account,100,'funding',1,'funding-credit-key');assert r.state(account)['funded']
    r.cancel_renewal(account);monkeypatch.setattr(r.time,'time',lambda:stamp+86400)
    assert r.state(account)['subscription'] is None


def test_calendar_boundaries_do_not_drift():
    d=dt.datetime(2024,1,31,12,tzinfo=dt.timezone.utc);stamp=int(d.timestamp())
    assert dt.datetime.fromtimestamp(r._boundary(stamp,'month',1),dt.timezone.utc).day==29
    assert dt.datetime.fromtimestamp(r._boundary(stamp,'month',2),dt.timezone.utc).day==31


def test_storage_unlock_is_time_priced_and_idempotent(account,monkeypatch):
    stamp=1802822400;monkeypatch.setattr(r.time,'time',lambda:stamp)
    plan(account);r.grant(account,10000,'storage funds',1,'storage-credit-key')
    with pytest.raises(ValueError):r.storage_check(account,1024**3,1)
    before=r.state(account)['credits_micro'];r.unlock_storage(account,1,'storage-unlock-key',10000)
    after=r.state(account)['credits_micro'];assert after==before
    r.unlock_storage(account,1,'storage-unlock-key',10000);assert r.state(account)['credits_micro']==after
    r.storage_check(account,1024**3,1)
    with pytest.raises(ValueError):r.unlock_storage(account,1,'storage-reprice-key',0)
    monkeypatch.setattr(r.time,'time',lambda:stamp+3600)
    assert r.state(account)['credits_micro']==before-100


def test_history_without_quotas_is_owner_scoped(account):
    finish(account,3,2);r.sample(account,123);r.sample(account,100)
    rows=r.history(account);assert len(rows)==30
    assert sum(x['cpu_seconds'] for x in rows)==3 and sum(x['gpu_seconds'] for x in rows)==2
    assert rows[-1]['storage_bytes']==123 and rows[0]['storage_bytes'] is None
    assert sum(x['cpu_seconds'] for x in r.history(auth.find_user('admin')['id']))==0


def test_self_service_cannot_reset_active_period(account):
    r.configure({'enabled':True,'self_service':True});r.subscribe(account,'day',0)
    with pytest.raises(ValueError,match='already active'):r.subscribe(account,'day',0)
    with pytest.raises(ValueError,match='price'):r.subscribe(account,'month',1)


def test_notice_smtp_absence_does_not_drop_events(account,monkeypatch):
    r.assign(account,{'storage_bytes':100},1);r.sample(account,99)
    monkeypatch.setattr('app.ai_notifications.smtp_configured',lambda:False);r.tick()
    with auth.db() as c:assert c.execute('SELECT count(*) FROM resource_notices WHERE sent=0').fetchone()[0]==3


def test_legal_updates_enqueue_once_and_remove_draft(account):
    from app import legal
    body={'operator_name':'Test operator','operator_country':'Italy','support_email':'support@example.test','public_url':'https://mta.example.test'}
    result=legal.save(body,1)
    with auth.db() as c:
        ids=[x[0] for x in c.execute("SELECT id FROM resource_notices WHERE id LIKE 'legal:%'")]
    assert len(ids)==2
    legal.save(body,1)
    with auth.db() as c:assert c.execute("SELECT count(*) FROM resource_notices WHERE id LIKE 'legal:%'").fetchone()[0]==2
    for language in ('it','en'):
        for kind in ('privacy','terms'):
            text,_=legal.document_html(kind,language)
            assert 'Documento di istanza da completare' not in text and 'awaiting completion' not in text
            assert 'Test operator' in text and 'privacy_email' not in text
    assert result['revision']==1


def test_cancelled_diagnostic_usage_consumes_quota_without_gpu_invoice(account):
    r.assign(account,{'cpu_seconds':2,'gpu_seconds':None},1)
    jid=ai_billing.create_job(account,'whisper')
    assert r.checkpoint(account,jid,{'cpu_seconds_estimated':1.9}) is False
    assert r.state(account)['used']['cpu_seconds']==1.9
    assert r.checkpoint(account,jid,{'cpu_seconds_estimated':2.1}) is True
    ai_billing.finish_job(jid,'cancelled',source='unmetered')
    assert r.state(account)['used']['cpu_seconds']==2.1
    with pytest.raises(ValueError,match='quota exceeded'):ai_billing.create_job(account,'whisper')
    with auth.db() as c:assert c.execute('SELECT usage_json FROM ai_compute_jobs WHERE id=?',(jid,)).fetchone()[0]=='{}'


def test_email_html_links_retries_and_language(account,monkeypatch):
    r.assign(account,{'storage_bytes':100},1);r.sample(account,96)
    monkeypatch.setattr('app.ai_notifications.smtp_configured',lambda:True)
    monkeypatch.setattr('app.ai_notifications._server',lambda:'https://mta.example.test')
    auth.update_profile(account,language='en')
    sent=[]
    def send(recipients,title,plain,body,**kw):
        assert 'cid:mta-logo' in body and '/account#accountLimits' in body
        assert '/account#subscriptions' not in body
        sent.append((title,kw['message_id']))
    monkeypatch.setattr(auth,'send_mail',send)
    r.tick();r.tick()
    assert len(sent)==3 and all(title=='Resource quota warning' for title,key in sent)
    assert len({key for title,key in sent})==3


def test_retention_change_notifies_and_noop_does_not(account):
    from app import account_lifecycle
    account_lifecycle.settings({'project_days':61})
    with auth.db() as c:before=c.execute("SELECT count(*) FROM resource_notices WHERE id LIKE 'retention:%'").fetchone()[0]
    assert before==2
    account_lifecycle.settings({'project_days':61})
    with auth.db() as c:assert c.execute("SELECT count(*) FROM resource_notices WHERE id LIKE 'retention:%'").fetchone()[0]==before


def test_routes_enforce_owner_admin_and_csrf(account,monkeypatch):
    from fastapi.testclient import TestClient
    from app import main
    from test_r210_legal_documents import cookie
    monkeypatch.setattr(main,'NATIVE_SINGLE_USER',False);monkeypatch.setattr(main,'check_basic_auth',lambda request:False)
    monkeypatch.delenv('MTA_ALLOW_INSECURE_NO_AUTH',raising=False)
    client=TestClient(main.app)
    assert client.get('/api/admin/subscriptions').status_code==401
    client.cookies.update(cookie(account))
    assert client.get('/api/admin/subscriptions').status_code==403
    assert client.get('/api/account/subscription').status_code==200
    assert client.put('/api/admin/subscriptions',json={'enabled':True}).status_code==403
    client.cookies.update(cookie(auth.find_user('admin')['id']))
    assert client.put('/api/admin/subscriptions',json={'enabled':True}).status_code==403
    assert client.put('/api/admin/subscriptions',json={'enabled':True},headers={'X-MTA-Request':'1'}).status_code==200


def test_storage_coverage_is_time_bounded_and_does_not_hide_usage(account,monkeypatch):
    stamp=1802822400;monkeypatch.setattr(r.time,'time',lambda:stamp);plan(account)
    ai_billing.record_persistent_storage(account,1024**3,sampled_at=stamp)
    monkeypatch.setattr(r.time,'time',lambda:stamp+3601)
    ai_billing.record_persistent_storage(account,1024**3,sampled_at=stamp+3600)
    with auth.db() as c:
        quantities,costs=ai_billing._priced_storage_usage(c,stamp,stamp+3600,account)
    assert sum(quantities.values())==1 and sum(costs.values())==0
    with auth.db() as c:assert r.covered_storage(c,account,stamp+86401)==0


@pytest.mark.parametrize('language',['it','en'])
def test_privacy_pdf_preserves_all_data_categories(account,language):
    import fitz
    from app import legal
    response=legal.pdf_document('privacy',language)
    with fitz.open(stream=response.body,filetype='pdf') as doc:text=' '.join(page.get_text() for page in doc)
    for value in ('Google','Facebook','GitHub','CPU/GPU','MFA','SSO'):assert value in text
    assert 'quando usi' not in text and 'when you use' not in text


def test_actual_frontend_history_and_escaping():
    import subprocess
    from pathlib import Path
    source=(Path(__file__).parents[1]/'app/static/subscriptions.js').read_text()
    source=source.replace("const personal=document.querySelector", "window.ResourceTest={history,details};const personal=document.querySelector")
    script="""const vm=require('vm'),assert=require('assert');const ctx={document:{querySelector(){return null}},window:{MtaLocale:{language:'en'},addEventListener(){}}};vm.createContext(ctx);vm.runInContext(process.argv[1],ctx);
const rows=[{day:'2026-10-18',cpu_seconds:0,gpu_seconds:2,storage_bytes:null,cpu_missing_jobs:1}];
const text=ctx.window.ResourceTest.history(rows);assert(text.includes('unmeasured jobs'));assert(text.includes('<svg'));assert(text.includes('<table'));
const view=ctx.window.ResourceTest.details({subscription:null,promo:'<img onerror=alert(1)>',funded:true,credits_micro:1000,used:{cpu_seconds:0,gpu_seconds:0,storage_bytes:0},limits:{cpu_seconds:null,gpu_seconds:null,storage_bytes:null},transactions:{credits:[],overages:[]},history:rows});
assert(view.includes('&lt;img'));assert(!view.includes('<img'));assert(view.includes('Unlimited'));
"""
    subprocess.run(['node','-e',script,source],check=True,timeout=10)


def test_ended_subscription_reverts_to_free_accounting(account,monkeypatch):
    stamp=1802822400;monkeypatch.setattr(r.time,'time',lambda:stamp);plan(account)
    r.cancel_renewal(account);monkeypatch.setattr(r.time,'time',lambda:stamp+86400)
    jid=ai_billing.create_job(account,'whisper')
    with auth.db() as c:assert c.execute('SELECT mode FROM resource_job_modes WHERE job_id=?',(jid,)).fetchone()[0]=='free'


def test_zero_storage_quota_is_not_unlimited(account):
    from app.account_limits import summary
    r.assign(account,{'storage_bytes':0},1)
    result=summary(account,{'used_bytes':0})
    assert result['storage']['quota_bytes']==0 and not result['storage']['unlimited']
    with pytest.raises(ValueError):r.storage_check(account,0,1)


def test_existing_explicit_admin_storage_limit_survives_migration(account):
    uid=auth.find_user('admin')['id']
    with auth.db() as c:
        c.execute('UPDATE users SET workspace_quota_bytes=12345 WHERE id=?',(uid,))
        c.execute('ALTER TABLE users DROP COLUMN workspace_quota_explicit')
    auth.init_auth_db()
    assert r.state(uid)['limits']['storage_bytes']==12345


def test_cancelling_queued_job_releases_quota_reservation(account,tmp_path,monkeypatch):
    from app import ai_arranger_runtime as queue
    monkeypatch.setattr(queue,'_ROOT',tmp_path/'queue')
    plan(account)
    queue.start('p','arranger',lambda *args:None,job_id='quota-queued-cancel',defer_spawn=True,payload={'actor_user_id':account})
    jid=ai_billing.provision_inference_job('quota-queued-cancel',account,'arranger')
    assert jid
    queue.cancel('quota-queued-cancel')
    with auth.db() as c:assert c.execute('SELECT status FROM ai_compute_jobs WHERE id=?',(jid,)).fetchone()[0]=='cancelled'
    assert ai_billing.create_job(account,'whisper')


def test_concurrent_renewal_is_one_credit_debit(account,monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    stamp=1802822400;monkeypatch.setattr(r.time,'time',lambda:stamp)
    plan(account,price_micro=100)
    r.grant(account,1000,'renewal funds',1,'concurrent-renewal-grant')
    monkeypatch.setattr(r.time,'time',lambda:stamp+86400)
    with ThreadPoolExecutor(max_workers=2) as pool:values=list(pool.map(lambda _:r.state(account),range(2)))
    assert [v['credits_micro'] for v in values]==[1000,1000]


def test_credit_usage_report_and_email_are_separate_from_ordinary_invoice(account):
    from app import ai_usage_reporting,ai_notifications
    plan(account);r.grant(account,1000,'report funds',1,'report-credits-grant');finish(account,12,13)
    report=ai_usage_reporting.snapshot(account,0,r.time.time()+1)
    assert report['amount_micro']==0 and report['credits_debited_micro']==80
    assert sum(x['credits_debited_micro'] for x in report['by_token'])==80
    title,plain,body=ai_notifications.render({'event':'summary','report':report},'en')
    assert 'CPU/GPU credits used' in plain and '0.000080' in body
