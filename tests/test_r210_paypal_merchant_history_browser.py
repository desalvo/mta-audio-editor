"""Prepared actual Chromium/admin API workflow; skip when engine unavailable."""
from pathlib import Path
from urllib.parse import urlsplit
import pytest
from app import auth
from test_r210_subscriptions import account as account  # noqa: F401
from test_r210_paypal import provider as provider  # noqa: F401
from test_r210_paypal_merchant_history import reporting as reporting  # noqa: F401


@pytest.fixture
def merchant_panel_client(reporting,monkeypatch):
    """Real isolated admin API, including the lazily created empty outbox."""
    from fastapi.testclient import TestClient
    from app import main
    from app.regime_payment_outbox import SCHEMA
    from test_r210_legal_documents import cookie
    monkeypatch.setattr(main,'NATIVE_SINGLE_USER',False)
    monkeypatch.setattr(main,'check_basic_auth',lambda _:False)
    monkeypatch.delenv('MTA_ALLOW_INSECURE_NO_AUTH',raising=False)
    with auth.db() as connection:
        connection.execute(SCHEMA)
    with TestClient(main.app) as client:
        client.cookies.update(cookie(reporting[0]))
        yield client


@pytest.mark.parametrize('language',['it','en'])
@pytest.mark.parametrize('width',[390,1280])
def test_actual_admin_history_confirmation_readback_and_reload(reporting,merchant_panel_client,chromium_capability,language,width):
    from playwright.sync_api import sync_playwright, expect
    client=merchant_panel_client
    requests=[];errors=[]
    def serve(route):
        url=urlsplit(route.request.url)
        assert url.hostname=='mta.test'
        if url.path=='/':
            route.fulfill(content_type='text/html',body=f'<html lang="{language}"><div id="serviceRegimePanel"></div></html>');return
        path=url.path+('?' +url.query if url.query else '')
        response=client.request(route.request.method,path,headers={'Content-Type':'application/json','X-MTA-Request':'1'},content=route.request.post_data)
        assert response.status_code==200,response.text
        requests.append((route.request.method,path))
        route.fulfill(status=response.status_code,content_type='application/json',body=response.content)
    script=(Path(__file__).resolve().parents[1]/'app/static/regime_admin_panel.js').read_text()
    with sync_playwright() as pw:
        browser=pw.chromium.launch(headless=True,args=['--no-sandbox'])
        page=browser.new_page(viewport={'width':width,'height':900});page.on('pageerror',lambda e:errors.append(str(e)))
        page.route('https://mta.test/**',serve);page.goto('https://mta.test/');page.add_script_tag(content=script)
        box=page.locator('[data-merchant-history]')
        # Chromium normalizes zero seconds away; Playwright 1.51 compares the
        # value verbatim, so fill the canonical datetime-local minute form.
        box.locator('[name=start_date]').fill('2026-09-01T00:00')
        box.locator('[name=end_date]').fill('2026-09-02T00:00')
        button=box.get_by_role('button',name='Leggi storico PayPal' if language=='it' else 'Read PayPal history')
        page.once('dialog',lambda d:d.dismiss());button.click();assert not reporting[1]
        page.once('dialog',lambda d:d.accept());button.click()
        page.wait_for_function("document.querySelector('[data-merchant-history] [role=status]').textContent.includes("+repr('Osservazioni salvate' if language=='it' else 'Observations saved')+")")
        assert len(reporting[1])==2
        assert all(q['start_date']==['2026-09-01T00:00:00Z'] and
                   q['end_date']==['2026-09-02T00:00:00Z'] for q in reporting[1])
        box.locator('summary').click()
        box.get_by_role('button',name='Carica osservazioni' if language=='it' else 'Load observations').click()
        expect(box.locator('pre')).to_contain_text('UNBOUND123')
        assert 'SECRET' not in box.inner_text() and 'private@example.test' not in box.inner_text()
        assert sum(method=='POST' for method,_ in requests)==1
        page.reload();page.add_script_tag(content=script)
        page.locator('[data-merchant-history]').get_by_role('button',name='Mostra letture salvate' if language=='it' else 'Show saved readbacks').click()
        page.locator('[data-merchant-history] summary').wait_for()
        assert len(reporting[1])==2 and not errors
        with auth.db() as c:assert c.execute('SELECT count(*) FROM paypal_orders').fetchone()[0]==0
        browser.close()
