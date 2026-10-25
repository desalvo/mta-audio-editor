"""Real Chromium forms -> actual authenticated API and financial persistence."""
import os
from pathlib import Path
from urllib.parse import urlsplit

import pytest
from fastapi.testclient import TestClient
from app import ai_billing
from test_r210_noncommercial_collection_e2e import nc_env as nc_env,enable,pledge,overview  # noqa: F401
from test_r210_legal_documents import cookie


@pytest.fixture
def nc_browser_config(request):
    executable=os.environ.get('MTA_TEST_CHROMIUM_EXECUTABLE')
    args=['--no-sandbox']
    if executable:
        assert Path(executable).is_file(),'Configured Chromium executable is absent'
        return {'executable_path':executable,'headless':True,'args':args+['--disable-dev-shm-usage','--no-zygote','--single-process','--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader']}
    request.getfixturevalue('chromium_capability')
    return {'headless':True,'args':args}


def page_server(client,language,admin,calls,errors):
    root=Path(__file__).resolve().parents[1]
    css=(root/'app/static/auth.css').read_text()+(root/'app/static/subscriptions.css').read_text()+(root/'app/static/noncommercial_contributions.css').read_text()
    def serve(route):
        url=urlsplit(route.request.url)
        assert url.hostname=='mta.test','Browser test must never contact a real bank or provider'
        if url.path=='/nc-test':
            route.fulfill(content_type='text/html',body='<html lang="'+language+'"><style>'+css+'</style><body class="settings-body"><main class="settings-grid"><section class="settings-card" data-nc-contributions="'+('admin' if admin else 'owner')+'"></section></main></body></html>');return
        response=client.request(route.request.method,url.path+('?' +url.query if url.query else ''),headers={'X-MTA-Request':'1','Content-Type':'application/json'},content=route.request.post_data)
        calls.append((route.request.method,url.path,response.status_code))
        if response.status_code>=500:errors.append(response.text)
        route.fulfill(status=response.status_code,content_type=response.headers.get('content-type','application/json'),body=response.content)
    return serve


def clients(env,monkeypatch):
    from app import main
    monkeypatch.setattr(main,'NATIVE_SINGLE_USER',False);monkeypatch.setattr(main,'check_basic_auth',lambda request:False)
    monkeypatch.delenv('MTA_ALLOW_INSECURE_NO_AUTH',raising=False)
    owner=TestClient(main.app);owner.cookies.update(cookie(env[1]))
    admin=TestClient(main.app);admin.cookies.update(cookie(env[0]))
    return owner,admin


@pytest.mark.parametrize('language',['it','en'])
@pytest.mark.parametrize('width',[390,1280])
def test_owner_optional_amount_report_actual_receipt_and_private_exports(nc_env,monkeypatch,nc_browser_config,language,width):
    from playwright.sync_api import sync_playwright
    from test_r210_noncommercial_collection_e2e import receipt
    enable(nc_env);owner,admin=clients(nc_env,monkeypatch);calls=[];errors=[]
    root=Path(__file__).resolve().parents[1];script=(root/'app/static/noncommercial_contributions.js').read_text()
    with sync_playwright() as pw:
        browser=pw.chromium.launch(**nc_browser_config);page=browser.new_page(viewport={'width':width,'height':900},accept_downloads=True)
        page.on('pageerror',lambda e:errors.append(str(e)));page.route('**/*',page_server(owner,language,False,calls,errors))
        page.goto('https://mta.test/nc-test');page.add_script_tag(content=script)
        form=page.locator('[data-nc-pledge]');form.wait_for();form.locator('[name=amount]').fill('0.60')
        page.once('dialog',lambda d:d.dismiss());form.locator('button').click();assert not any(m=='POST' for m,_,_ in calls)
        page.once('dialog',lambda d:d.accept());form.locator('button').click()
        report=page.locator('[data-nc-report]');report.wait_for();assert overview(nc_env[1])['contributions'][0]['received_cents']==0
        page.once('dialog',lambda d:d.accept());report.click()
        page.get_by_text('Bonifico segnalato; incasso non ancora verificato' if language=='it' else 'Transfer reported; receipt not yet verified',exact=False).wait_for()
        item=overview(nc_env[1])['contributions'][0];assert item['amount_cents']==60
        receipt(nc_env,item,amount=60)
        page.locator('[data-nc-refresh]').click()
        page.get_by_text('Ricevuto e verificato dall’amministratore' if language=='it' else 'Received and reviewed by administrator',exact=False).wait_for()
        assert page.locator('[data-nc-pledge] [name=amount]').input_value()=='0.40'
        with page.expect_download():page.get_by_role('button',name='Esporta il mio storico contributi (CSV)' if language=='it' else 'Export my contribution history (CSV)').click()
        with page.expect_download():page.locator('[data-nc-statement-csv]').click()
        assert errors==[]
        assert page.evaluate('document.documentElement.scrollWidth<=window.innerWidth')
        assert all(code==200 for _,_,code in calls)
        browser.close()


@pytest.mark.parametrize('language',['it','en'])
@pytest.mark.parametrize('width',[390,1280])
def test_admin_configuration_bank_evidence_excess_refund_and_period_closure(nc_env,monkeypatch,nc_browser_config,language,width):
    from playwright.sync_api import sync_playwright
    enable(nc_env);item=pledge(nc_env);owner,admin=clients(nc_env,monkeypatch);calls=[];errors=[]
    job=ai_billing.create_job(nc_env[1],'whisper',started_at=400);ai_billing.finish_job(job,'done',{'cpu_seconds':1},source='worker',finished_at=402)
    root=Path(__file__).resolve().parents[1]
    with sync_playwright() as pw:
        browser=pw.chromium.launch(**nc_browser_config);page=browser.new_page(viewport={'width':width,'height':900},timezone_id='UTC')
        page.on('pageerror',lambda e:errors.append(str(e)));page.route('**/*',page_server(admin,language,True,calls,errors))
        page.goto('https://mta.test/nc-test');page.add_script_tag(content=(root/'app/static/noncommercial_contributions.js').read_text())
        cfg=page.locator('[data-nc-config]');cfg.wait_for();cfg.locator('[name=instructions]').fill('Updated receiving bank instructions <svg onload=alert(1)>')
        page.once('dialog',lambda d:d.dismiss());cfg.locator('button').click();assert not any(m=='PUT' for m,_,_ in calls)
        page.once('dialog',lambda d:d.accept());cfg.locator('button').click()
        page.wait_for_function("document.querySelector('[data-nc-config]')?.dataset.ncRevision==='2'")
        article=page.locator('[data-nc-contribution="'+item['id']+'"]');form=article.locator('[data-nc-receipt]')
        form.locator('[name=amount]').fill('1.50');form.locator('[name=reference]').fill('BANK-RECEIPT-BROWSER');form.locator('[name=evidence]').fill('a'*64)
        form.locator('button').click();assert not any(m=='POST' for m,_,_ in calls)
        form.locator('[name=verified]').check();page.once('dialog',lambda d:d.dismiss());form.locator('button').click();assert not any(m=='POST' for m,_,_ in calls)
        page.once('dialog',lambda d:d.accept());form.locator('button').click()
        page.get_by_text('Incasso eccedente: rimborso dovuto dal gestore' if language=='it' else 'Excess receipt: refund due from operator',exact=False).wait_for()
        assert overview(nc_env[1])['contributions'][0]['excess_cents']==50
        form.locator('[name=kind]').select_option('reversed');form.locator('[name=amount]').fill('0.50')
        original=overview(nc_env[1])['contributions'][0]['events'][0]['id'];form.locator('[name=original]').select_option(original)
        form.locator('[name=reference]').fill('BANK-REFUND-BROWSER');form.locator('[name=evidence]').fill('b'*64);form.locator('[name=verified]').check()
        page.once('dialog',lambda d:d.accept());form.locator('button').click()
        page.get_by_text('Ricevuto e verificato dall’amministratore' if language=='it' else 'Received and reviewed by administrator',exact=False).wait_for()
        assert overview(nc_env[1])['contributions'][0]['excess_cents']==0
        close=page.locator('[data-nc-close]');close.locator('[name=start]').fill('1970-01-01T00:05');close.locator('[name=end]').fill('1970-01-01T00:08:20');close.locator('[name=cost]').fill('1.00')
        page.once('dialog',lambda d:d.accept());close.locator('button').click()
        page.wait_for_function("document.querySelectorAll('[data-nc-statement-csv]').length===2")
        assert overview(nc_env[1])['statements'][1]['contribution_cents']==100
        # A genuine zero-cost period must also be closable from the UI.
        close.locator('[name=start]').fill('1970-01-01T00:08:20');close.locator('[name=end]').fill('1970-01-01T00:10');close.locator('[name=cost]').fill('0.00')
        page.once('dialog',lambda d:d.accept());close.locator('button').click()
        page.wait_for_function("document.querySelectorAll('[data-nc-statement-csv]').length===3")
        assert not page.locator('svg[onload]').count() and errors==[]
        assert page.evaluate('document.documentElement.scrollWidth<=window.innerWidth')
        assert all(code==200 for _,_,code in calls)
        browser.close()


@pytest.mark.parametrize('language',['it','en'])
@pytest.mark.parametrize('role',['owner','admin'])
def test_actual_mounts_and_noncommercial_controls_hide_subscription_forms(nc_env,monkeypatch,nc_browser_config,language,role):
    from playwright.sync_api import sync_playwright
    owner,admin=clients(nc_env,monkeypatch);client=owner if role=='owner' else admin
    root=Path(__file__).resolve().parents[1];calls=[];errors=[]
    template=client.get('/account' if role=='owner' else '/admin')
    assert template.status_code==200
    assert 'data-nc-contributions="'+role+'"' in template.text
    assert '/static/noncommercial_contributions.js' in template.text and '/static/noncommercial_contributions.css' in template.text
    base=page_server(client,language,role=='admin',calls,errors)
    def serve(route):
        if urlsplit(route.request.url).path=='/nc-test':
            route.fulfill(content_type='text/html',body='<html lang="'+language+'"><a data-subscription-nav href="#subscriptions">Subscriptions</a><details open><section data-resource-'+('account' if role=='owner' else 'admin')+'></section><section data-nc-contributions="'+role+'"></section></details></html>');return
        base(route)
    with sync_playwright() as pw:
        browser=pw.chromium.launch(**nc_browser_config);page=browser.new_page(viewport={'width':390,'height':900})
        page.on('pageerror',lambda e:errors.append(str(e)));page.route('**/*',serve);page.goto('https://mta.test/nc-test')
        page.add_script_tag(content='window.MtaLocale={language:'+repr(language)+'};'+(root/'app/static/subscriptions.js').read_text())
        page.add_script_tag(content=(root/'app/static/noncommercial_contributions.js').read_text())
        page.locator('[data-nc-statement-csv]').wait_for()
        if role=='owner':
            page.wait_for_function("document.querySelector('[data-resource-account]').hidden===true")
            assert page.locator('[data-subscription-nav]').get_attribute('href')=='#accountLimits'
        else:
            page.get_by_text('I controlli per abbonamenti e crediti non sono disponibili' if language=='it' else 'Subscription and credit controls are unavailable',exact=False).wait_for()
            assert not page.locator('[data-resource-admin] input').count()
            assert not any(path=='/api/admin/subscriptions' for _,path,_ in calls)
        assert errors==[]
        browser.close()


@pytest.mark.parametrize('language',['it','en'])
def test_commercial_mode_retains_private_nc_history_as_read_only(nc_env,monkeypatch,nc_browser_config,language):
    from playwright.sync_api import sync_playwright
    from app import auth
    from test_r210_noncommercial_collection_e2e import receipt
    enable(nc_env);item=pledge(nc_env);receipt(nc_env,item)
    # Fixture-only epoch change tests historical rendering; this is not an
    # enabled administrative cutover and must not certify criterion D6.
    with auth.db() as c:c.execute("UPDATE regime_fence_state SET regime='COMMERCIAL'")
    (auth.data_root()/'service-regime.json').write_text('{"regime":"COMMERCIAL","revision":0}')
    owner,_=clients(nc_env,monkeypatch);root=Path(__file__).resolve().parents[1];calls=[];errors=[]
    with sync_playwright() as pw:
        browser=pw.chromium.launch(**nc_browser_config);page=browser.new_page(viewport={'width':390,'height':900})
        page.on('pageerror',lambda e:errors.append(str(e)));page.route('**/*',page_server(owner,language,False,calls,errors))
        page.goto('https://mta.test/nc-test');page.add_script_tag(content=(root/'app/static/noncommercial_contributions.js').read_text())
        page.locator('[data-nc-statement-csv]').wait_for()
        assert page.locator('[data-nc-contributions]').is_visible()
        assert not page.locator('[data-nc-contributions] form').count()
        assert not page.locator('[data-nc-report]').count() and errors==[]
        browser.close()
