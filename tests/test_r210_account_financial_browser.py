"""Real Chromium -> real owner API; no provider I/O or simulated financial balances."""
from pathlib import Path
from urllib.parse import urlsplit

import pytest
from fastapi.testclient import TestClient
from app import main
from test_r210_noncommercial_collection_e2e import nc_env as nc_env,enable,pledge,receipt  # noqa: F401
from test_r210_subscriptions import account as account,plan  # noqa: F401
from test_r210_noncommercial_collection_browser import nc_browser_config as nc_browser_config  # noqa: F401
from test_r210_legal_documents import cookie


def server(client,language,fail,calls):
    root=Path(__file__).resolve().parents[1]
    def serve(route):
        url=urlsplit(route.request.url);assert url.hostname=='mta.test'
        if url.path=='/context-test':
            css=''.join((root/'app/static'/name).read_text() for name in ('auth.css','admin_controls.css','subscriptions.css','noncommercial_contributions.css'))
            route.fulfill(content_type='text/html',body='<html lang="'+language+'"><meta name="viewport" content="width=device-width,initial-scale=1"><style>'+css+'</style><script>window.MtaLocale={language:'+repr(language)+'}</script><body class="settings-body"><a data-subscription-nav href="#subscriptions">Subscriptions</a><main class="settings-grid"><section class="settings-card"><details id="accountLimits" open><summary>Usage</summary><div id="accountLimitsContent"></div><button id="accountLimitsRefresh">Refresh</button><p id="accountLimitsStatus" role="status"></p><section data-resource-account></section><section data-nc-contributions="owner" hidden></section></details></section></main></body></html>');return
        if fail['enabled'] and url.path in ('/api/account/limits','/api/account/subscription'):
            route.fulfill(status=503,content_type='application/json',body='{"detail":"Accounting unavailable"}');return
        response=client.request(route.request.method,url.path+('?' +url.query if url.query else ''),headers={'X-MTA-Request':'1','Content-Type':'application/json'},content=route.request.post_data)
        calls.append((route.request.method,url.path,response.status_code));route.fulfill(status=response.status_code,content_type=response.headers.get('content-type','application/json'),body=response.content)
    return serve


@pytest.mark.parametrize('language',['it','en'])
@pytest.mark.parametrize('width',[390,1280])
def test_nc_financial_overview_is_voluntary_private_and_refresh_safe(nc_env,nc_browser_config,language,width):
    from playwright.sync_api import sync_playwright
    enable(nc_env);item=pledge(nc_env);receipt(nc_env,item,amount=150)
    client=TestClient(main.app);client.cookies.update(cookie(nc_env[1]));root=Path(__file__).resolve().parents[1]
    fail={'enabled':False};calls=[];errors=[]
    with sync_playwright() as api:
        browser=api.chromium.launch(**nc_browser_config);page=browser.new_page(viewport={'width':width,'height':1000},timezone_id='UTC')
        page.on('pageerror',lambda error:errors.append(str(error)));page.route('**/*',server(client,language,fail,calls));page.goto('https://mta.test/context-test')
        for name in ('account_limits.js','subscriptions.js','noncommercial_contributions.js'):page.add_script_tag(content=(root/'app/static'/name).read_text())
        page.evaluate('window.MtaAccountLimits.init({id:'+str(nc_env[1])+',limits_expanded:true})')
        financial=page.locator('[data-account-financial]');financial.wait_for()
        assert ('non sono un debito' if language=='it' else 'not a debt') in financial.inner_text()
        assert ('Rimborso dovuto dal gestore' if language=='it' else 'Refund due from operator') in financial.inner_text()
        page.wait_for_function("document.querySelector('[data-resource-account]').hidden===true")
        assert page.locator('[data-activate]').count()==0 and page.locator('[data-cancel]').count()==0
        assert not errors and page.evaluate('document.documentElement.scrollWidth<=innerWidth')
        fail['enabled']=True;page.locator('#accountLimitsRefresh').click()
        page.wait_for_function("document.getElementById('accountLimitsContent').innerHTML==='' ")
        assert page.locator('#accountLimitsStatus').inner_text()
        fail['enabled']=False;page.locator('#accountLimitsRefresh').click();financial.wait_for()
        assert not any(method!='GET' for method,_,_ in calls)
        browser.close()


@pytest.mark.parametrize('language',['it','en'])
@pytest.mark.parametrize('width',[390,1280])
def test_commercial_controls_fail_closed_and_recover_after_get_failure(account,nc_browser_config,language,width):
    from playwright.sync_api import sync_playwright
    from app import resource_accounts as resources
    plan(account);resources.configure({'self_service':True})
    client=TestClient(main.app);client.cookies.update(cookie(account));root=Path(__file__).resolve().parents[1]
    fail={'enabled':False};calls=[];errors=[]
    with sync_playwright() as api:
        browser=api.chromium.launch(**nc_browser_config);page=browser.new_page(viewport={'width':width,'height':1000})
        page.on('pageerror',lambda error:errors.append(str(error)));page.route('**/*',server(client,language,fail,calls));page.goto('https://mta.test/context-test')
        for name in ('account_limits.js','subscriptions.js'):page.add_script_tag(content=(root/'app/static'/name).read_text())
        page.evaluate('window.MtaAccountLimits.init({id:'+str(account)+',limits_expanded:true})')
        page.locator('[data-cancel]').wait_for();page.locator('[data-account-financial]').wait_for()
        assert ('Saldo portafoglio crediti' if language=='it' else 'Credit wallet balance') in page.locator('[data-account-financial]').inner_text()
        fail['enabled']=True;page.locator('[data-resource-account] [data-refresh]').click()
        page.wait_for_function("document.querySelectorAll('[data-resource-account] [data-cancel]').length===0")
        assert page.locator('[data-resource-account] [role=status]').inner_text()
        fail['enabled']=False;page.locator('[data-resource-account] [data-refresh]').click();page.locator('[data-cancel]').wait_for()
        page.once('dialog',lambda dialog:dialog.dismiss());page.locator('[data-cancel]').click()
        assert not any(method=='POST' for method,_,_ in calls)
        page.once('dialog',lambda dialog:dialog.accept());page.locator('[data-cancel]').click()
        page.get_by_text('Il rinnovo si interrompe il' if language=='it' else 'Renewal stops on',exact=False).wait_for()
        assert any(method=='POST' and path.endswith('/cancel') and status==200 for method,path,status in calls)
        assert not errors and page.evaluate('document.documentElement.scrollWidth<=innerWidth')
        browser.close()


def test_late_previous_language_response_cannot_replace_current_wallet(account,nc_browser_config):
    from playwright.sync_api import sync_playwright
    from app import resource_accounts as resources
    plan(account)
    client=TestClient(main.app);client.cookies.update(cookie(account));root=Path(__file__).resolve().parents[1]
    initial=client.get('/api/account/subscription');assert initial.status_code==200
    resources.grant(account,123450000,'late response fixture',1,'language-wallet-grant')
    delayed=[];calls=[];base=server(client,'en',{'enabled':False},calls)
    def serve(route):
        if urlsplit(route.request.url).path=='/api/account/subscription' and not delayed:
            delayed.append(route);return
        base(route)
    with sync_playwright() as api:
        browser=api.chromium.launch(**nc_browser_config);page=browser.new_page()
        page.route('**/*',serve);page.goto('https://mta.test/context-test')
        page.add_script_tag(content=(root/'app/static/subscriptions.js').read_text())
        page.wait_for_function("document.querySelector('[data-resource-account] [data-content]')!==null")
        page.evaluate("window.MtaLocale.language='it';window.dispatchEvent(new Event('mta:language'))")
        page.locator('[data-resource-account] .credits-total').wait_for()
        current=page.locator('[data-resource-account] .credits-total').inner_text();assert '123,45' in current
        delayed[0].fulfill(status=200,content_type='application/json',body=initial.content)
        page.evaluate('new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)))')
        assert page.locator('[data-resource-account] .credits-total').inner_text()==current
        browser.close()


@pytest.mark.parametrize('language',['it','en'])
@pytest.mark.parametrize('width',[390,1280])
def test_actual_account_page_mounts_private_accounting_without_duplicate_controls(nc_env,nc_browser_config,language,width):
    from playwright.sync_api import sync_playwright
    from app import auth
    with auth.db() as c:c.execute('UPDATE users SET language=?,limits_expanded=1 WHERE id=?',(language,nc_env[1]))
    client=TestClient(main.app);client.cookies.update(cookie(nc_env[1]));calls=[];errors=[]
    with sync_playwright() as api:
        browser=api.chromium.launch(**nc_browser_config);page=browser.new_page(viewport={'width':width,'height':1000})
        page.on('pageerror',lambda error:errors.append(str(error)))
        page.route('**/*',server(client,language,{'enabled':False},calls));page.goto('https://mta.test/account')
        page.locator('[data-account-financial]').wait_for()
        page.wait_for_function("window.MtaLocale?.language==="+repr(language))
        assert page.locator('#profileForm').count()==1 and page.locator('[data-account-financial]').count()==1
        page.wait_for_function("document.querySelector('[data-resource-account]').hidden===true")
        assert page.locator('[data-activate]').count()==0 and not errors
        assert ('non sono un debito' if language=='it' else 'not a debt') in page.locator('[data-account-financial]').inner_text()
        assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
        browser.close()
