"""Chromium -> actual admin/owner HTTP -> fixed provider fixture -> ledger."""
from pathlib import Path
from urllib.parse import urlsplit

import httpx
import pytest
from fastapi.testclient import TestClient
from app import auth,resource_accounts,checkout_reference_recovery as recovery,payment_reconcile_service as reconciliation
from test_r210_subscriptions import account as account  # noqa: F401
from test_r210_paypal import provider as provider  # noqa: F401
from test_r210_subscription_repayment_e2e import debt as debt,balance  # noqa: F401
from test_r210_checkout_reference_recovery import unknown_stripe,unknown_paypal
from test_r210_legal_documents import cookie

ROOT=Path(__file__).resolve().parents[1]


def client_for(monkeypatch,uid):
    from app import main
    monkeypatch.setattr(main,'NATIVE_SINGLE_USER',False);monkeypatch.setattr(main,'check_basic_auth',lambda request:False)
    monkeypatch.delenv('MTA_ALLOW_INSECURE_NO_AUTH',raising=False)
    client=TestClient(main.app);client.cookies.update(cookie(uid));return client


@pytest.mark.parametrize('language',['it','en'])
@pytest.mark.parametrize('width',[480,1280])
def test_admin_recovers_reference_and_closes_expired_without_new_create(account,monkeypatch,chromium_capability,language,width):
    from playwright.sync_api import sync_playwright
    local,ref,_,mock,posts=unknown_stripe(account,monkeypatch)
    original=recovery.recover
    def recover(provider,order_id,reference):
        with httpx.Client(transport=mock) as remote:return original(provider,order_id,reference,client=remote)
    def reconcile(provider,order_id):
        assert provider=='stripe'
        with httpx.Client(transport=mock) as remote:return reconciliation.reconcile_stripe(order_id,client=remote)
    monkeypatch.setattr(recovery,'recover',recover);monkeypatch.setattr(reconciliation,'reconcile_checkout',reconcile)
    client=client_for(monkeypatch,auth.find_user('admin')['id']);calls=[];errors=[]
    def serve(route):
        url=urlsplit(route.request.url)
        if url.path=='/':route.fulfill(content_type='text/html',body='<html lang="'+language+'"><div id="serviceRegimePanel"></div></html>');return
        path=url.path+('?' +url.query if url.query else '')
        result=client.request(route.request.method,path,headers={'X-MTA-Request':'1','Content-Type':'application/json'},content=route.request.post_data)
        calls.append((route.request.method,url.path));assert result.status_code==200,result.text
        route.fulfill(status=result.status_code,content_type='application/json',body=result.content)
    with sync_playwright() as pw:
        browser=pw.chromium.launch(headless=True,args=['--no-sandbox']);page=browser.new_page(viewport={'width':width,'height':900})
        page.on('pageerror',lambda error:errors.append(str(error)));page.route('https://mta.test/**',serve)
        page.goto('https://mta.test/');page.add_script_tag(content=(ROOT/'app/static/regime_admin_panel.js').read_text())
        field=page.get_by_role('textbox',name=('ID checkout del provider: ' if language=='it' else 'Provider checkout ID: ')+'stripe · '+local,exact=False);field.wait_for();field.fill(ref)
        button=page.get_by_role('button',name='Verifica riferimento' if language=='it' else 'Verify reference')
        page.once('dialog',lambda dialog:dialog.dismiss());button.click()
        assert not any(method=='POST' for method,_ in calls)
        page.once('dialog',lambda dialog:dialog.accept());button.click()
        page.get_by_text('Riferimento verificato; il pagamento resta da riconciliare.' if language=='it' else 'Reference verified; payment remains to reconcile.',exact=True).wait_for()
        assert resource_accounts.state(account)['credits_micro']==0 and len(posts)==1
        assert page.get_by_role('button',name='Verifica riferimento' if language=='it' else 'Verify reference').count()==0
        page.once('dialog',lambda dialog:dialog.accept())
        page.get_by_role('button',name='Riconcilia dal provider' if language=='it' else 'Reconcile from provider',exact=False).click()
        page.get_by_text('Checkout chiuso senza incasso; nessun credito emesso.' if language=='it' else 'Unpaid checkout closed; no credits issued.',exact=True).wait_for()
        assert 'expired' in page.locator('#regimeFinance').inner_text()
        with auth.db() as c:assert c.execute('SELECT status FROM credit_purchase_orders WHERE id=?',(local,)).fetchone()[0]=='cancelled'
        assert resource_accounts.state(account)['credits_micro']==0 and len(posts)==1 and not errors
        browser.close()


@pytest.mark.parametrize('language',['it','en'])
def test_owner_can_complete_recovered_repayment_without_approval_url(account,provider,debt,monkeypatch,chromium_capability,language):
    from playwright.sync_api import sync_playwright
    local,ref,_=unknown_paypal(account,provider,monkeypatch,body={'kind':'subscription_reversal','refund_id':'REFUND111','expected_due_micro':3_000_000,'request_id':'recover-owner-debt-123'})
    assert recovery.recover('paypal',local,ref)['reference_confirmed']
    before=balance(account);assert before['pending_reference_known'] and before['pending_checkout_url'] is None
    client=client_for(monkeypatch,account);errors=[]
    def serve(route):
        path=urlsplit(route.request.url).path
        if path=='/':route.fulfill(content_type='text/html',body='<details open><summary>Account</summary><section data-resource-account></section></details>');return
        result=client.request(route.request.method,path,headers={'X-MTA-Request':'1','Content-Type':'application/json'},content=route.request.post_data)
        assert result.status_code==200,result.text
        route.fulfill(status=result.status_code,content_type='application/json',body=result.content)
    with sync_playwright() as pw:
        browser=pw.chromium.launch(headless=True,args=['--no-sandbox']);page=browser.new_page();page.on('pageerror',lambda error:errors.append(str(error)))
        page.route('https://mta.test/**',serve);page.goto('https://mta.test/')
        page.add_script_tag(content='window.MtaLocale={language:'+repr(language)+'};'+(ROOT/'app/static/subscriptions.js').read_text())
        button=page.get_by_role('button',name='Verifica pagamento PayPal' if language=='it' else 'Verify PayPal payment');button.wait_for()
        page.once('dialog',lambda dialog:dialog.accept());button.click()
        page.wait_for_function("document.querySelector('[data-reversal-panel]')?.textContent.includes("+repr('Regolato' if language=='it' else 'Settled')+") && document.querySelectorAll('[data-repayment]').length===0")
        assert balance(account)['due_micro']==0 and resource_accounts.state(account)['credits_micro']==0
        assert not errors
        browser.close()


@pytest.mark.parametrize('language',['it','en'])
def test_owner_resumes_recovered_credit_purchase_from_private_catalog(account,provider,monkeypatch,chromium_capability,language):
    from playwright.sync_api import sync_playwright
    local,ref,_=unknown_paypal(account,provider,monkeypatch)
    recovery.recover('paypal',local,ref)
    client=client_for(monkeypatch,account);errors=[]
    def serve(route):
        path=urlsplit(route.request.url).path
        if path=='/':route.fulfill(content_type='text/html',body='<section data-credit-shop><h1></h1><p role="status"></p><div data-credit-content></div></section>');return
        result=client.request(route.request.method,path,headers={'X-MTA-Request':'1','Content-Type':'application/json'},content=route.request.post_data)
        assert result.status_code==200,result.text
        route.fulfill(status=result.status_code,content_type='application/json',body=result.content)
    with sync_playwright() as pw:
        browser=pw.chromium.launch(headless=True,args=['--no-sandbox']);page=browser.new_page();page.on('pageerror',lambda error:errors.append(str(error)))
        page.route('https://mta.test/**',serve);page.goto('https://mta.test/')
        page.add_script_tag(content='window.MtaLocale={language:'+repr(language)+'};'+(ROOT/'app/static/credit_shop.js').read_text())
        button=page.get_by_role('button',name='Completa pagamento PayPal esistente' if language=='it' else 'Complete existing PayPal payment');button.wait_for()
        page.once('dialog',lambda dialog:dialog.dismiss());button.click()
        assert resource_accounts.state(account)['credits_micro']==0
        page.once('dialog',lambda dialog:dialog.accept());button.click()
        page.get_by_text('Pagamento verificato' if language=='it' else 'Payment verified',exact=True).wait_for()
        page.wait_for_function("!document.querySelector('[data-credit-content]').textContent.includes("+repr(local)+")")
        assert resource_accounts.state(account)['credits_micro']==5_000_000
        assert not errors
        browser.close()
