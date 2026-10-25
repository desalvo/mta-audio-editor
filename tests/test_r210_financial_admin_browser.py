"""Real Chromium panel + actual FastAPI handlers + persistent test database."""
from pathlib import Path
from urllib.parse import urlsplit

import pytest
from fastapi.testclient import TestClient
from app import auth, credit_purchases as shop
from test_r210_subscriptions import account as account  # noqa: F401
from test_r210_credit_checkout import signed,paid_event
from test_r210_payment_reconciliation_e2e import purchase
from test_r210_legal_documents import cookie


@pytest.mark.parametrize('language',['it','en'])
def test_browser_reads_actual_financial_api_and_never_enables_switch(account,monkeypatch,chromium_capability,language):
    from playwright.sync_api import sync_playwright
    from app import main
    monkeypatch.setattr(main,'NATIVE_SINGLE_USER',False)
    monkeypatch.setattr(main,'check_basic_auth',lambda request:False)
    monkeypatch.delenv('MTA_ALLOW_INSECURE_NO_AUTH',raising=False)
    order=purchase(account,monkeypatch);shop.event(*signed(paid_event(order)))
    client=TestClient(main.app);client.cookies.update(cookie(auth.find_user('admin')['id']))
    errors=[];requests=[]
    def serve(route):
        path=urlsplit(route.request.url).path
        if path=='/':
            route.fulfill(content_type='text/html',body=f'<html lang="{language}"><div id="serviceRegimePanel"></div></html>');return
        requests.append(path)
        result=client.request(route.request.method,route.request.url.replace('https://mta.test',''),
                              headers={'X-MTA-Request':'1','Content-Type':'application/json'},content=route.request.post_data)
        if route.request.method=='POST':assert result.status_code==200,result.text
        route.fulfill(status=result.status_code,content_type='application/json',body=result.content)
    script=(Path(__file__).resolve().parents[1]/'app/static/regime_admin_panel.js').read_text()
    with sync_playwright() as browser_api:
        browser=browser_api.chromium.launch(headless=True,args=['--no-sandbox'])
        page=browser.new_page();page.on('pageerror',lambda error:errors.append(str(error)))
        page.route('https://mta.test/**',serve);page.goto('https://mta.test/')
        page.add_script_tag(content=script)
        page.wait_for_selector('#regimeFinance table')
        assert order in page.locator('#regimeFinance').inner_text()
        assert '5.00' in page.locator('#regimeFinance').inner_text() if language=='en' else '5,00' in page.locator('#regimeFinance').inner_text()
        assert page.locator('#regimeReadiness').inner_text()==('Regime switching is not yet enabled' if language=='en' else 'Cambio di regime non ancora abilitato')
        assert not errors
        assert '/api/admin/service-regime/payment-ledger' in requests
        assert page.get_by_role('button',name='Reconcile from provider' if language=='en' else 'Riconcilia dal provider',exact=False).count()==1
        from app import payment_reconcile_service,resource_accounts
        from test_r210_authenticated_ledger_service import transport
        import httpx
        mock,_=transport(order)
        def reconcile(provider,local_id):
            assert provider=='stripe' and local_id==order
            with httpx.Client(transport=mock) as remote:
                return payment_reconcile_service.reconcile_stripe(local_id,client=remote)
        monkeypatch.setattr(payment_reconcile_service,'reconcile_checkout',reconcile)
        page.on('dialog',lambda dialog:dialog.accept())
        page.get_by_role('button',name='Reconcile from provider' if language=='en' else 'Riconcilia dal provider',exact=False).click()
        page.wait_for_function("document.querySelector('#regimeFinance').textContent.includes("+repr('3.00' if language=='en' else '3,00')+")")
        assert resource_accounts.state(account)['credits_micro']==3_000_000

        browser.close()


def test_admin_finance_roles_csrf_and_request_shape(account,monkeypatch):
    from app import main,payment_reconcile_service
    monkeypatch.setattr(main,'NATIVE_SINGLE_USER',False)
    monkeypatch.setattr(main,'check_basic_auth',lambda request:False)
    monkeypatch.delenv('MTA_ALLOW_INSECURE_NO_AUTH',raising=False)
    client=TestClient(main.app)
    assert client.get('/api/admin/service-regime/payment-ledger').status_code==401
    client.cookies.update(cookie(account));assert client.get('/api/admin/service-regime/payment-ledger').status_code==403
    client.cookies.update(cookie(auth.find_user('admin')['id']))
    assert client.get('/api/admin/service-regime/payment-ledger?limit=0').status_code==422
    assert client.post('/api/admin/service-regime/reconcile-payment',json={'provider':'stripe','order_id':'x'}).status_code==403
    calls=[]
    monkeypatch.setattr(payment_reconcile_service,'reconcile_checkout',lambda *args:calls.append(args) or {'ledger_reconciled':True})
    headers={'X-MTA-Request':'1'}
    assert client.post('/api/admin/service-regime/reconcile-payment',headers=headers,json={'provider':'stripe','order_id':'x','amount':1}).status_code==422
    assert not calls
    assert client.post('/api/admin/service-regime/reconcile-payment',headers=headers,json={'provider':'stripe','order_id':'x'}).status_code==200
    assert calls==[('stripe','x')]


def test_admin_diagnostics_remain_readable_during_drain(account,monkeypatch):
    from app import main
    monkeypatch.setattr(main,'NATIVE_SINGLE_USER',False)
    monkeypatch.setattr(main,'check_basic_auth',lambda request:False)
    monkeypatch.delenv('MTA_ALLOW_INSECURE_NO_AUTH',raising=False)
    with auth.db() as c:c.execute('UPDATE regime_fence_state SET transitioning=1')
    client=TestClient(main.app);client.cookies.update(cookie(auth.find_user('admin')['id']))
    assert client.get('/api/admin/service-regime').status_code==200
    result=client.get('/api/admin/service-regime/combined-readiness?target=NON_COMMERCIAL')
    assert result.status_code==200 and 'transition_already_pending' in result.json()['unresolved']
    assert result.json()['ready_for_automatic_transition'] is False
