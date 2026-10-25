"""Actual owner pages -> authenticated local API -> GET-only provider fixture."""
from urllib.parse import urlsplit

import pytest
from app import auth, paypal_payments as paypal, resource_accounts as resources
from test_r210_subscriptions import account as account, plan  # noqa: F401
from test_r210_paypal import provider as provider  # noqa: F401
from test_r210_owner_payments import client
from test_r210_noncommercial_collection_browser import nc_browser_config as nc_browser_config  # noqa: F401


@pytest.mark.parametrize('language',['it','en'])
@pytest.mark.parametrize('width',[390,1280])
@pytest.mark.parametrize('path',['/account','/account/credits'])
def test_actual_private_history_recovery_no_automatic_capture(account,provider,monkeypatch,nc_browser_config,language,width,path):
    from playwright.sync_api import sync_playwright
    plan(account)
    order=paypal.checkout(account,{'kind':'credits','amount_cents':500,'request_id':'browser-pending-payment'})
    provider[0][next(iter(provider[0]))]['intent']='CAPTURE'
    with auth.db() as c:c.execute('UPDATE users SET language=? WHERE id=?',(language,account))
    owner=client(account,monkeypatch);calls=[];errors=[];fail={'enabled':False}
    def serve(route):
        url=urlsplit(route.request.url)
        assert url.hostname=='mta.test','No real provider or server may be contacted'
        if fail['enabled'] and url.path=='/api/account/payments':
            route.fulfill(status=503,content_type='application/json',body='{}');return
        response=owner.request(route.request.method,url.path+('?' +url.query if url.query else ''),headers={'X-MTA-Request':'1','Content-Type':'application/json'},content=route.request.post_data)
        calls.append((route.request.method,url.path,response.status_code))
        route.fulfill(status=response.status_code,content_type=response.headers.get('content-type','application/json'),body=response.content)
    with sync_playwright() as api:
        browser=api.chromium.launch(**nc_browser_config);page=browser.new_page(viewport={'width':width,'height':1000})
        page.on('pageerror',lambda error:errors.append(str(error)));page.route('**/*',serve)
        response=page.goto('https://mta.test'+path)
        assert response.status==200 and 'text/html' in response.headers['content-type']
        panel=page.locator('[data-owner-payments]');panel.get_by_text(order['order_id'],exact=False).wait_for()
        verify=panel.get_by_role('button',name='Verifica esito senza incassare' if language=='it' else 'Verify status without collecting payment')
        resume=panel.get_by_role('button',name='Riprendi checkout esistente' if language=='it' else 'Resume existing checkout')
        page.once('dialog',lambda dialog:dialog.dismiss());resume.click()
        assert not any(method=='POST' for method,_,_ in calls)
        page.once('dialog',lambda dialog:dialog.dismiss());verify.click()
        assert not any(method=='POST' for method,_,_ in calls)
        before=len(provider[1]);page.once('dialog',lambda dialog:dialog.accept());verify.click()
        page.wait_for_function("document.querySelector('[data-owner-payments]').textContent.includes('"+order['order_id']+"') && !document.querySelector('[data-owner-payments] button').disabled")
        assert any(method=='POST' and url.endswith('/verify') and code==200 for method,url,code in calls)
        assert all(call[0]=='GET' for call in provider[1][before:])
        if path.endswith('/credits'):
            assert page.locator('[data-credit-content] .plan-grid button').count()==0
        page.reload();panel.get_by_text(order['order_id'],exact=False).wait_for()
        assert len(provider[0])==1
        # Eligibility loss must not hide the recoverable existing checkout.
        resources.configure({'credits_enabled':False});page.reload();resume.wait_for()
        fail['enabled']=True;panel.get_by_role('button',name='Aggiorna storico' if language=='it' else 'Refresh history').click()
        panel.get_by_text('Storico pagamenti non disponibile' if language=='it' else 'Payment history unavailable',exact=False).wait_for()
        assert panel.get_by_role('button',name='Verifica esito senza incassare' if language=='it' else 'Verify status without collecting payment').count()==0
        assert panel.get_by_role('button',name='Riprendi checkout esistente' if language=='it' else 'Resume existing checkout').count()==0
        fail['enabled']=False;panel.get_by_role('button',name='Aggiorna storico' if language=='it' else 'Refresh history').click();resume.wait_for()
        assert not errors and page.evaluate('document.documentElement.scrollWidth<=innerWidth')
        assert not any('/capture' in url for _,url,_ in calls)
        browser.close()


def test_late_history_response_cannot_restore_old_payment_controls(account,provider,monkeypatch,nc_browser_config):
    from playwright.sync_api import sync_playwright
    plan(account)
    order=paypal.checkout(account,{'kind':'credits','amount_cents':500,'request_id':'delayed-history-request'})
    owner=client(account,monkeypatch)
    initial=owner.get('/api/account/payments?offset=0&limit=20');assert initial.status_code==200
    delayed=[]
    def serve(route):
        url=urlsplit(route.request.url);assert url.hostname=='mta.test'
        if url.path=='/api/account/payments' and not delayed:delayed.append(route);return
        response=owner.request(route.request.method,url.path+('?' +url.query if url.query else ''),headers={'X-MTA-Request':'1','Content-Type':'application/json'},content=route.request.post_data)
        route.fulfill(status=response.status_code,content_type=response.headers.get('content-type','application/json'),body=response.content)
    with sync_playwright() as api:
        browser=api.chromium.launch(**nc_browser_config);page=browser.new_page();page.route('**/*',serve)
        page.goto('https://mta.test/account/credits')
        page.locator('[data-owner-payments] button').wait_for()
        with auth.db() as c:c.execute("UPDATE paypal_orders SET status='cancelled',checkout_url=NULL WHERE id=?",(order['order_id'],))
        page.evaluate("window.MtaLocale.setChoice('it')")
        panel=page.locator('[data-owner-payments]');panel.get_by_text('Annullato',exact=False).wait_for()
        delayed[0].fulfill(status=200,content_type='application/json',body=initial.content)
        page.evaluate('new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)))')
        assert 'Annullato' in panel.inner_text()
        assert panel.get_by_role('button',name='Resume existing checkout').count()==0
        assert panel.get_by_role('button',name='Riprendi checkout esistente').count()==0
        browser.close()


@pytest.mark.parametrize('gateway',['stripe','paypal'])
def test_existing_redirect_and_unknown_reference_after_reload(account,provider,monkeypatch,nc_browser_config,gateway):
    from playwright.sync_api import sync_playwright
    from app import credit_purchases as stripe
    from test_r210_credit_checkout import prepare
    prepare(account,monkeypatch)
    if gateway=='stripe':order=stripe.checkout(account,500,'resume-existing-stripe')
    else:order=paypal.checkout(account,{'kind':'credits','amount_cents':500,'request_id':'resume-existing-paypal'})
    owner=client(account,monkeypatch);outbound=[]
    def serve(route):
        url=urlsplit(route.request.url)
        if url.hostname!='mta.test':
            assert route.request.url==order['checkout_url'] and route.request.method=='GET'
            outbound.append(route.request.url);route.fulfill(content_type='text/html',body='<p>Isolated provider page</p>');return
        response=owner.request(route.request.method,url.path+('?' +url.query if url.query else ''),headers={'X-MTA-Request':'1','Content-Type':'application/json'},content=route.request.post_data)
        route.fulfill(status=response.status_code,content_type=response.headers.get('content-type','application/json'),body=response.content)
    with sync_playwright() as api:
        browser=api.chromium.launch(**nc_browser_config);page=browser.new_page(viewport={'width':390,'height':900});page.route('**/*',serve)
        page.goto('https://mta.test/account/credits')
        page.once('dialog',lambda dialog:dialog.accept());page.locator('[data-owner-payments]').get_by_role('button',name='Resume existing checkout').click()
        page.wait_for_url(order['checkout_url']);assert outbound==[order['checkout_url']]
        with auth.db() as c:
            if gateway=='stripe':c.execute('UPDATE credit_purchase_orders SET session_id=NULL WHERE id=?',(order['order_id'],))
            else:c.execute('UPDATE paypal_orders SET provider_order=NULL WHERE id=?',(order['order_id'],))
        page.goto('https://mta.test/account/credits')
        panel=page.locator('[data-owner-payments]');panel.get_by_text('No provider reference is available.',exact=False).wait_for()
        assert panel.get_by_role('button',name='Resume existing checkout').count()==0
        assert panel.get_by_role('button',name='Verify status without collecting payment').count()==0
        assert page.locator('[data-credit-content] .plan-grid button').count()==0
        browser.close()
