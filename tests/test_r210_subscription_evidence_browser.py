"""Real admin API + shipped panel: bilingual legacy review, retry and pagination."""
from pathlib import Path
from urllib.parse import urlsplit

import pytest

from app import auth
from test_r210_subscriptions import account as account  # noqa: F401
from test_r210_paypal import provider as provider  # noqa: F401
from test_r210_original_subscription_loss import paid as paid  # noqa: F401
from test_r210_subscription_basis_audit import evidence_client as evidence_client, add_legacy_orders  # noqa: F401


@pytest.mark.parametrize('language',['it','en'])
@pytest.mark.parametrize('width',[390,1280])
def test_real_panel_legacy_review_pages_error_and_retry(evidence_client,paid,chromium_capability,language,width):
    from playwright.sync_api import sync_playwright, expect
    from test_r210_legal_documents import cookie
    client=evidence_client
    client.cookies.update(cookie(auth.find_user('admin')['id']))
    with auth.db() as c:
        c.execute('DROP TABLE subscription_payment_basis')
        add_legacy_orders(c,paid[0],26)
    requests=[];errors=[]
    def serve(route):
        url=urlsplit(route.request.url)
        assert url.hostname=='mta.test'
        if url.path=='/':
            route.fulfill(content_type='text/html',body=f'<html lang="{language}"><div id="serviceRegimePanel"></div></html>')
            return
        path=url.path+('?' +url.query if url.query else '')
        response=client.request(route.request.method,path,
                                headers={'Content-Type':'application/json','X-MTA-Request':'1'},
                                content=route.request.post_data)
        requests.append((path,response.status_code))
        route.fulfill(status=response.status_code,content_type='application/json',body=response.content)
    script=(Path(__file__).resolve().parents[1]/'app/static/regime_admin_panel.js').read_text()
    with sync_playwright() as pw:
        browser=pw.chromium.launch(headless=True,args=['--no-sandbox'])
        page=browser.new_page(viewport={'width':width,'height':900})
        page.on('pageerror',lambda error:errors.append(str(error)))
        page.route('https://mta.test/**',serve);page.goto('https://mta.test/');page.add_script_tag(content=script)
        expect(page.locator('#regimeReadiness')).to_contain_text('non ancora abilitato' if language=='it' else 'not yet enabled')
        box=page.locator('[data-subscription-evidence]')
        load=box.get_by_role('button',name='Verifica prove abbonamenti' if language=='it' else 'Check subscription evidence')
        more=box.get_by_role('button',name='Carica altri casi' if language=='it' else 'Load more cases')
        load.focus();page.keyboard.press('Enter')
        expect(box.locator('li')).to_have_count(25)
        expect(box.get_by_role('status')).to_contain_text('27')
        expect(box).to_contain_text('Base originale mancante' if language=='it' else 'Original basis missing')
        more.click();expect(box.locator('li')).to_have_count(27);expect(more).to_be_hidden()
        # Force an actual database-schema error, then restore the prerequisite.
        with auth.db() as c:
            c.execute('CREATE TABLE subscription_payment_basis(order_id TEXT)')
        load.click();expect(box.get_by_role('status')).to_contain_text('HTTP 409')
        expect(box.locator('li')).to_have_count(0);expect(more).to_be_hidden()
        with auth.db() as c:
            c.execute('DROP TABLE subscription_payment_basis')
        load.click();expect(box.locator('li')).to_have_count(25)
        expect(box.get_by_role('status')).to_contain_text('27')
        assert any('offset=25' in path and status==200 for path,status in requests)
        assert any('subscription-evidence' in path and status==409 for path,status in requests)
        assert not errors
        assert 'quota@example.test' not in box.inner_text() and 'client_secret' not in box.inner_text()
        with auth.db() as c:
            assert c.execute('SELECT count(*) FROM paypal_subscription_reversals').fetchone()[0]==0
            assert not c.execute("SELECT 1 FROM sqlite_master WHERE name='subscription_payment_basis'").fetchone()
        browser.close()
