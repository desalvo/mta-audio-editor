"""Chromium IT/EN -> actual FastAPI/DB -> provider fixture -> verified return."""
from pathlib import Path
from urllib.parse import urlsplit

import pytest
from fastapi.testclient import TestClient
from app import auth,resource_accounts,paypal_payments
from test_r210_subscriptions import account as account  # noqa: F401
from test_r210_paypal import provider as provider  # noqa: F401
from test_r210_subscription_repayment_e2e import debt as debt,balance  # noqa: F401
from test_r210_legal_documents import cookie


@pytest.mark.parametrize('language',['it','en'])
@pytest.mark.parametrize('width',[390,1280])
def test_owner_confirms_resumes_and_returns_to_settled_debt(account,provider,debt,monkeypatch,chromium_capability,language,width):
    from playwright.sync_api import sync_playwright
    from app import main
    monkeypatch.setattr(main,'NATIVE_SINGLE_USER',False);monkeypatch.setattr(main,'check_basic_auth',lambda request:False)
    monkeypatch.delenv('MTA_ALLOW_INSECURE_NO_AUTH',raising=False)
    client=TestClient(main.app);client.cookies.update(cookie(account))
    errors=[];calls=[];root=Path(__file__).resolve().parents[1]
    def serve(route):
        url=urlsplit(route.request.url)
        if url.hostname=='www.sandbox.paypal.com':route.fulfill(content_type='text/html',body='<p>Isolated PayPal approval fixture</p>');return
        assert url.hostname=='mta.test'
        if url.path=='/account':
            route.fulfill(content_type='text/html',body='<style>body{overflow-wrap:anywhere}button{max-width:100%}</style><details open><summary>Account</summary><section data-resource-account></section></details>');return
        path=url.path+('?' +url.query if url.query else '')
        response=client.request(route.request.method,path,headers={'X-MTA-Request':'1','Content-Type':'application/json'},content=route.request.post_data)
        calls.append((route.request.method,path,response.status_code))
        assert response.status_code==200,response.text
        route.fulfill(status=response.status_code,content_type='application/json',body=response.content)
    script='window.MtaLocale={language:'+repr(language)+'};'+(root/'app/static/subscriptions.js').read_text()
    with sync_playwright() as pw:
        browser=pw.chromium.launch(headless=True,args=['--no-sandbox'])
        page=browser.new_page(viewport={'width':width,'height':900});page.on('pageerror',lambda error:errors.append(str(error)))
        page.route('**/*',serve)
        page.goto('https://mta.test/account');page.add_script_tag(content=script)
        button=page.get_by_role('button',name='Regola con PayPal' if language=='it' else 'Repay with PayPal',exact=False);button.wait_for()
        page.once('dialog',lambda dialog:dialog.dismiss());button.click()
        assert not any(method=='POST' for method,_,_ in calls)
        page.once('dialog',lambda dialog:dialog.accept());button.click()
        page.wait_for_url('https://www.sandbox.paypal.com/**')
        local=balance(account)['pending_order_id'];assert local
        assert len(provider[0])==2
        # Reload the account: resume the same approved checkout without creating
        # a new provider order or using browser storage for payment identifiers.
        page.goto('https://mta.test/account');page.add_script_tag(content=script)
        resume=page.get_by_role('button',name='Riprendi pagamento PayPal' if language=='it' else 'Resume PayPal repayment');resume.wait_for()
        page.once('dialog',lambda dialog:dialog.accept());resume.click();page.wait_for_url('https://www.sandbox.paypal.com/**')
        assert sum(method=='POST' and path=='/api/account/paypal/checkout' for method,path,_ in calls)==1
        page.goto('https://mta.test/account?paypal_order='+local);page.add_script_tag(content=script)
        page.get_by_text('Pagamento verificato' if language=='it' else 'Payment verified',exact=True).wait_for()
        page.wait_for_function("document.querySelector('[data-reversal-panel]')?.textContent.includes("+repr('Regolato' if language=='it' else 'Settled')+")")
        assert page.locator('[data-repayment]').count()==0
        assert balance(account)['due_micro']==0 and resource_accounts.state(account)['credits_micro']==0
        assert errors==[]
        browser.close()


@pytest.mark.parametrize('language',['it','en'])
def test_admin_reads_actual_outstanding_and_repaid_amount(account,provider,debt,monkeypatch,chromium_capability,language):
    from playwright.sync_api import sync_playwright
    from app import main
    from test_r210_subscription_repayment_e2e import checkout
    monkeypatch.setattr(main,'NATIVE_SINGLE_USER',False);monkeypatch.setattr(main,'check_basic_auth',lambda request:False)
    monkeypatch.delenv('MTA_ALLOW_INSECURE_NO_AUTH',raising=False)
    client=TestClient(main.app);client.cookies.update(cookie(auth.find_user('admin')['id']))
    root=Path(__file__).resolve().parents[1]
    def serve(route):
        path=urlsplit(route.request.url).path
        if path=='/':route.fulfill(content_type='text/html',body='<html lang="'+language+'"><div id="serviceRegimePanel"></div></html>');return
        result=client.get(route.request.url.replace('https://mta.test',''));assert result.status_code==200,result.text
        route.fulfill(content_type='application/json',body=result.content)
    with sync_playwright() as pw:
        browser=pw.chromium.launch(headless=True,args=['--no-sandbox']);page=browser.new_page()
        page.route('https://mta.test/**',serve);page.goto('https://mta.test/')
        page.add_script_tag(content=(root/'app/static/regime_admin_panel.js').read_text())
        text=page.locator('#regimeReceivables');text.wait_for()
        assert ('3,00 EUR' if language=='it' else '3.00 EUR') in text.inner_text()
        local=checkout(account)['order_id'];paypal_payments.capture(account,local)
        page.locator('#regimeRefresh').click()
        page.wait_for_function("document.querySelector('#regimeReceivables')?.textContent==="+repr(('Recuperi abbonamenti da incassare: 0,00 EUR · Rimborsi recuperi dovuti dal gestore: 0,00 EUR') if language=='it' else 'Subscription recoveries outstanding: 0.00 EUR · Repayment refunds due from operator: 0.00 EUR'))
        assert 'Regime switching is not yet enabled' in page.locator('#regimeReadiness').inner_text() if language=='en' else 'Cambio di regime non ancora abilitato' in page.locator('#regimeReadiness').inner_text()
        browser.close()
