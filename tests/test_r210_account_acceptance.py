"""Complete shipped owner pages, actual API/database, no live provider access."""
import json
from datetime import datetime,timezone
from urllib.parse import urlsplit

import pytest
from fastapi.testclient import TestClient
from app import auth,resource_accounts as resources,resource_entitlements
from test_r210_subscriptions import account as account,plan  # noqa: F401
from test_r210_noncommercial_collection_browser import nc_browser_config as nc_browser_config  # noqa: F401
from test_r210_legal_documents import cookie


def client(account,monkeypatch):
    from app import main
    monkeypatch.setattr(main,'NATIVE_SINGLE_USER',False);monkeypatch.setattr(main,'check_basic_auth',lambda request:False)
    monkeypatch.delenv('MTA_ALLOW_INSECURE_NO_AUTH',raising=False)
    result=TestClient(main.app);result.cookies.update(cookie(account));return result


def configure(account,scenario,language):
    resources.configure({'enabled':True,'self_service':True,'credits_enabled':True})
    if scenario in ('active','paid','credits_disabled','permission_disabled','historical_nc'):
        plan(account,price_micro=5_000_000 if scenario=='paid' else 0)
        resources.grant(account,12_345_678,'private accounting fixture',1,'account-acceptance-grant')
    if scenario=='trial':resources.subscribe(account,'trial',0,next_plan='month',next_price=0)
    if scenario=='credits_disabled':resources.configure({'credits_enabled':False})
    if scenario=='permission_disabled':resource_entitlements.set_policy(account,{'subscriptions_allowed':False},1)
    if scenario in ('nc','historical_nc'):
        with auth.db() as c:c.execute("UPDATE regime_fence_state SET regime='NON_COMMERCIAL'")
        (auth.data_root()/'service-regime.json').write_text(json.dumps({'regime':'NON_COMMERCIAL','revision':0}))
    with auth.db() as c:c.execute('UPDATE users SET language=?,limits_expanded=1 WHERE id=?',(language,account))


def serve(client,calls,*,fail=None,intercept=None):
    def handle(route):
        url=urlsplit(route.request.url)
        if intercept and intercept(route,url):return
        assert url.hostname=='mta.test','Unexpected external request'
        if fail and url.path in fail:
            route.fulfill(status=503,content_type='application/json',body='{"detail":"unavailable"}');return
        path=url.path+('?' +url.query if url.query else '')
        response=client.request(route.request.method,path,content=route.request.post_data,headers={'X-MTA-Request':'1','Content-Type':'application/json'})
        calls.append((route.request.method,url.path,response.status_code))
        route.fulfill(status=response.status_code,content_type=response.headers.get('content-type','application/json'),body=response.content)
    return handle


def assert_accessible_owner_page(page):
    assert page.locator('main').count()==1
    assert page.locator('h1').count()==1
    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
    missing=page.locator('input:not([type=hidden]),select,textarea').evaluate_all("els=>els.filter(e=>e.getClientRects().length&&!e.disabled&&!(e.labels?.length||e.getAttribute('aria-label')||e.getAttribute('aria-labelledby'))).map(e=>e.outerHTML)")
    assert missing==[]
    assert page.locator('img:not([alt])').count()==0


@pytest.mark.parametrize('scenario',['no_plan','active','paid','trial','credits_disabled','permission_disabled','nc','historical_nc'])
@pytest.mark.parametrize('language',['it','en'])
@pytest.mark.parametrize('width',[390,1280])
def test_full_account_and_credit_pages_regime_policy_language_and_keyboard(account,monkeypatch,nc_browser_config,scenario,language,width):
    from playwright.sync_api import sync_playwright
    configure(account,scenario,language);web=client(account,monkeypatch);calls=[];errors=[]
    with sync_playwright() as pw:
        browser=pw.chromium.launch(**nc_browser_config);page=browser.new_page(viewport={'width':width,'height':1000},locale='it-IT' if language=='it' else 'en-GB')
        page.on('pageerror',lambda e:errors.append(str(e)));page.route('**/*',serve(web,calls));page.goto('https://mta.test/account')
        page.locator('[data-account-financial]').wait_for();page.locator('[data-payment-refunds] [data-refund-content] p').first.wait_for()
        assert page.locator('html').get_attribute('lang')==language
        assert page.locator('[data-payment-refunds] h2').inner_text()==('Rimborsi dei pagamenti' if language=='it' else 'Payment refunds')
        if scenario in ('nc','historical_nc'):
            assert page.locator('[data-resource-account]').is_hidden()
            assert page.locator('[data-activate],[data-cancel],[data-overage]').count()==0
            assert ('non sono un debito' if language=='it' else 'not a debt') in page.locator('[data-account-financial]').inner_text()
        else:
            page.locator('[data-resource-account] [data-content] .credits-total').wait_for()
            assert page.locator('[data-resource-account]').is_visible()
            if scenario=='no_plan':assert page.locator('[data-activate=trial]').count()==1
            if scenario=='paid':assert page.get_by_role('button',name='Paga abbonamento con PayPal' if language=='it' else 'Pay subscription with PayPal',exact=False).count()==0
            if scenario in ('active','trial','paid','credits_disabled','permission_disabled'):assert page.locator('[data-cancel]').count()==1
        # Keyboard reaches the named refresh control, without an artificial click.
        page.locator('#accountLimitsRefresh').focus();assert page.locator('#accountLimitsRefresh').evaluate('e=>document.activeElement===e')
        page.keyboard.press('Enter');page.locator('[data-account-financial]').wait_for()
        assert_accessible_owner_page(page)
        page.goto('https://mta.test/account/credits');page.locator('[data-owner-payments] button').first.wait_for()
        page.locator('[data-credit-content] p').first.wait_for()
        assert page.locator('html').get_attribute('lang')==language
        assert page.locator('[data-payment-refunds] h2').inner_text()==('Rimborsi dei pagamenti' if language=='it' else 'Payment refunds')
        assert page.get_by_role('button',name='Buy with Stripe').count()==0 and page.get_by_role('button',name='Acquista con Stripe').count()==0
        if scenario in ('nc','historical_nc'):
            assert ('Pagamenti non disponibili' if language=='it' else 'Payments unavailable') in page.locator('[data-credit-shop]').inner_text()
        assert_accessible_owner_page(page)
        assert not errors and all(status<400 for _,_,status in calls)
        assert not any(method=='POST' for method,_,_ in calls)
        browser.close()


@pytest.mark.parametrize('language',['it','en'])
@pytest.mark.parametrize('width',[390,1280])
def test_actual_trial_contract_renewal_storage_overage_and_cancel(account,monkeypatch,nc_browser_config,language,width):
    from playwright.sync_api import sync_playwright
    configure(account,'no_plan',language);web=client(account,monkeypatch);calls=[];errors=[]
    with sync_playwright() as pw:
        browser=pw.chromium.launch(**nc_browser_config);page=browser.new_page(viewport={'width':width,'height':1000},timezone_id='UTC')
        page.on('pageerror',lambda e:errors.append(str(e)));page.route('**/*',serve(web,calls));page.goto('https://mta.test/account#subscriptions')
        trial=page.locator('[data-activate=trial]');trial.wait_for();page.locator('[data-trial-next]').select_option('month')
        page.once('dialog',lambda d:d.dismiss());trial.click();assert resources.state(account)['subscription'] is None
        page.once('dialog',lambda d:d.accept());trial.click();page.locator('[data-cancel]').wait_for()
        initial=resources.state(account);assert initial['subscription']=='trial' and initial['next_plan']['plan']=='month'
        resources.grant(account,5_000_000,'storage funds',1,'full-page-storage-grant')
        page.locator('[data-resource-account] [data-refresh]').click();page.locator('[data-overage]').wait_for()
        with page.expect_response(lambda r:'/api/account/subscription' in r.url and r.request.method=='PATCH'):page.locator('[data-overage]').check()
        page.wait_for_function("!document.querySelector('[data-resource-account]').hasAttribute('aria-busy')")
        assert resources.state(account)['overage'] is True
        with page.expect_response(lambda r:'/api/account/subscription' in r.url and r.request.method=='PATCH'):page.locator('[data-overage]').uncheck()
        page.wait_for_function("!document.querySelector('[data-resource-account]').hasAttribute('aria-busy')")
        assert resources.state(account)['overage'] is False
        page.locator('[data-renew-plan]').select_option('year');page.once('dialog',lambda d:d.accept())
        with page.expect_response(lambda r:r.url.endswith('/api/account/subscription/renewal') and r.request.method=='POST'):page.locator('[data-renew-plan-save]').click()
        page.wait_for_function("!document.querySelector('[data-resource-account]').hasAttribute('aria-busy')")
        page.wait_for_function("document.querySelector('[data-renew-plan]')?.value==='year'")
        assert resources.state(account)['next_plan']['plan']=='year' and resources.state(account)['period']['start']==initial['period']['start']
        before=resources.state(account);gib=before['limits']['storage_bytes']//(1024**3)+1
        page.locator('[data-field=storage]').fill(str(gib));page.once('dialog',lambda d:d.accept())
        with page.expect_response(lambda r:r.url.endswith('/api/account/subscription/storage') and r.request.method=='PUT'):page.locator('[data-storage]').click()
        page.wait_for_function("!document.querySelector('[data-resource-account]').hasAttribute('aria-busy')")
        page.wait_for_function("document.querySelector('[data-field=storage]')?.value==="+repr(str(gib)))
        assert resources.state(account)['limits']['storage_bytes']==gib*1024**3
        page.wait_for_function("document.querySelector('#accountLimitsContent .limits-tile')?.textContent.includes("+repr(str(gib)+' GiB')+")")
        stamp=__import__('time').time();fmt=lambda ts:datetime.fromtimestamp(ts,timezone.utc).strftime('%Y-%m-%dT%H:%M')
        page.locator('[data-report]').locator('..').locator('..').evaluate('e=>e.open=true')
        page.locator('[data-report-start]').fill(fmt(stamp-3600));page.locator('[data-report-end]').fill(fmt(stamp))
        page.locator('[data-report]').click();page.locator('[data-report-result] table').wait_for()
        page.once('dialog',lambda d:d.accept());page.locator('[data-cancel]').click()
        page.get_by_text('Il rinnovo si interrompe il' if language=='it' else 'Renewal stops on',exact=False).wait_for()
        assert resources.state(account)['renewal_stops_at']==initial['period']['end']
        assert_accessible_owner_page(page);assert not errors and all(status<400 for _,_,status in calls)
        browser.close()


@pytest.mark.parametrize('language',['it','en'])
def test_profile_locale_roundtrip_refreshes_every_owner_financial_panel(account,monkeypatch,nc_browser_config,language):
    from playwright.sync_api import sync_playwright
    configure(account,'active',language);web=client(account,monkeypatch);calls=[];other='en' if language=='it' else 'it'
    with sync_playwright() as pw:
        browser=pw.chromium.launch(**nc_browser_config);page=browser.new_page()
        page.route('**/*',serve(web,calls));page.goto('https://mta.test/account')
        page.locator('[data-account-financial]').wait_for();page.locator('#profileForm [name=language]').select_option(other)
        page.locator('#profileForm button').click();page.wait_for_function('window.MtaLocale.language==='+repr(other))
        assert auth.get_user(account)['language']==other
        page.wait_for_function("document.querySelector('.ai-resource-panel [data-language]')?.value==="+repr(other))
        assert page.locator('[data-payment-refunds] h2').inner_text()==('Payment refunds' if other=='en' else 'Rimborsi dei pagamenti')
        assert page.locator('[data-payment-refunds] [data-refund-refresh]').inner_text()==('Refresh refunds' if other=='en' else 'Aggiorna rimborsi')
        page.reload();page.wait_for_function('window.MtaLocale.language==='+repr(other));page.locator('[data-account-financial]').wait_for()
        assert page.locator('[data-payment-refunds] h2').inner_text()==('Payment refunds' if other=='en' else 'Rimborsi dei pagamenti')
        browser.close()
