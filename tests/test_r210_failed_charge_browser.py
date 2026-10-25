"""Actual credits page -> explicit owner verification -> receipt -> new admission."""
from urllib.parse import urlsplit

import httpx
import pytest
from app import auth, payment_reconcile_service as service
from test_r210_subscriptions import account as account  # noqa: F401
from test_r210_owner_payments import client
from test_r210_failed_charge_recovery import failed_history, pending
from test_r210_terminal_checkout_e2e import assert_closed
from test_r210_noncommercial_collection_browser import nc_browser_config as nc_browser_config  # noqa: F401


@pytest.mark.parametrize('language',['it','en'])
@pytest.mark.parametrize('width',[390,1280])
@pytest.mark.parametrize('failure',[False,True])
def test_failed_checkout_actual_page_closure_or_preserved_hold(account,monkeypatch,nc_browser_config,language,width,failure):
    from playwright.sync_api import sync_playwright
    local,state,mock,reads=failed_history(account,monkeypatch)
    with auth.db() as c:c.execute('UPDATE users SET language=? WHERE id=?',(language,account))
    if failure:state['charges'][0]['amount_captured']=1
    owner=client(account,monkeypatch);calls=[];errors=[];redirects=[]
    def reconcile(provider,order_id,*,expected_owner):
        assert provider=='stripe' and order_id==local and expected_owner==account
        with httpx.Client(transport=mock) as remote:return service.reconcile_stripe(order_id,client=remote,expected_owner=expected_owner)
    monkeypatch.setattr(service,'reconcile_checkout',reconcile)
    def serve(route):
        url=urlsplit(route.request.url)
        if url.hostname=='checkout.stripe.com':
            assert not failure and route.request.method=='GET'
            redirects.append(route.request.url);route.fulfill(content_type='text/html',body='<p>Isolated checkout</p>');return
        assert url.hostname=='mta.test','Never contact a real provider or server'
        response=owner.request(route.request.method,url.path+('?' +url.query if url.query else ''),headers={'X-MTA-Request':'1','Content-Type':'application/json'},content=route.request.post_data)
        calls.append((route.request.method,url.path,response.status_code))
        route.fulfill(status=response.status_code,content_type=response.headers.get('content-type','application/json'),body=response.content)
    with sync_playwright() as api:
        browser=api.chromium.launch(**nc_browser_config);page=browser.new_page(viewport={'width':width,'height':1000})
        page.on('pageerror',lambda error:errors.append(str(error)));page.route('**/*',serve)
        response=page.goto('https://mta.test/account/credits');assert 'text/html' in response.headers['content-type']
        panel=page.locator('[data-owner-payments]');panel.get_by_text(local,exact=False).wait_for()
        assert page.locator('[data-credit-content] .plan-grid button').count()==0
        verify=panel.get_by_role('button',name='Verifica esito senza incassare' if language=='it' else 'Verify status without collecting payment')
        page.once('dialog',lambda dialog:dialog.dismiss());verify.click();assert not reads
        page.once('dialog',lambda dialog:dialog.accept());verify.click()
        if failure:
            panel.get_by_text('Payment history unavailable' if language=='en' else 'Storico pagamenti non disponibile',exact=False).wait_for()
            assert panel.get_by_role('button',name='Verifica esito senza incassare' if language=='it' else 'Verify status without collecting payment').count()==0
            pending(local,account)
            page.reload();panel.get_by_text(local,exact=False).wait_for()
            assert page.locator('[data-credit-content] .plan-grid button').count()==0
        else:
            panel.get_by_text('Annullato' if language=='it' else 'Cancelled',exact=False).wait_for();assert_closed(local,'stripe',account)
            button=page.locator('[data-credit-content]').get_by_role('button',name='Acquista con Stripe' if language=='it' else 'Buy with Stripe').first
            button.wait_for();assert not panel.get_by_role('button',name='Riprendi checkout esistente' if language=='it' else 'Resume existing checkout').count()
            assert not errors and page.evaluate('document.documentElement.scrollWidth<=innerWidth')
            button.click();page.wait_for_url('https://checkout.stripe.com/**')
            assert len(redirects)==1
            with auth.db() as c:assert c.execute('SELECT count(*) FROM credit_purchase_orders').fetchone()[0]==2
        assert not errors and not any('/capture' in path for _,path,_ in calls)
        assert sum(method=='POST' and path.endswith('/verify') for method,path,_ in calls)==1
        browser.close()
