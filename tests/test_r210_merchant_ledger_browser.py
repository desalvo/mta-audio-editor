"""Real Chromium, actual administrator API and canonical local ledger."""
from pathlib import Path
from urllib.parse import urlsplit

import pytest
from app import auth, resource_accounts as resources
from test_r210_subscriptions import account as account  # noqa: F401
from test_r210_paypal import provider as provider  # noqa: F401
from test_r210_merchant_ledger_bridge import merchant as merchant  # noqa: F401


@pytest.mark.parametrize('language', ['it', 'en'])
@pytest.mark.parametrize('width', [390, 1280])
@pytest.mark.parametrize('kind', ['capture', 'refund'])
def test_actual_merchant_discovery_confirm_apply_reload(merchant, account, monkeypatch, chromium_capability, language, width, kind):
    from fastapi.testclient import TestClient
    from playwright.sync_api import sync_playwright, expect
    from app import main
    from test_r210_legal_documents import cookie
    monkeypatch.setattr(main, 'NATIVE_SINGLE_USER', False)
    monkeypatch.setattr(main, 'check_basic_auth', lambda _: False)
    monkeypatch.delenv('MTA_ALLOW_INSECURE_NO_AUTH', raising=False)
    snap, _ = merchant['observe'](kind, 'TXN')
    requests = []; errors = []
    script = (Path(__file__).resolve().parents[1]/'app/static/regime_admin_panel.js').read_text()
    with TestClient(main.app) as client, sync_playwright() as pw:
        client.cookies.update(cookie(merchant['admin']))
        def serve(route):
            url = urlsplit(route.request.url)
            assert url.hostname == 'mta.test'
            if url.path == '/':
                route.fulfill(content_type='text/html', body=f'<html lang="{language}"><div id="serviceRegimePanel"></div></html>'); return
            path = url.path+('?' + url.query if url.query else '')
            response = client.request(route.request.method, path, headers={'Content-Type': 'application/json', 'X-MTA-Request': '1'}, content=route.request.post_data)
            assert response.status_code == 200, response.text
            requests.append((route.request.method, path))
            route.fulfill(status=response.status_code, content_type='application/json', body=response.content)
        browser = pw.chromium.launch(headless=True, args=['--no-sandbox'])
        page = browser.new_page(viewport={'width': width, 'height': 900})
        page.on('pageerror', lambda e: errors.append(str(e)))
        page.route('https://mta.test/**', serve); page.goto('https://mta.test/'); page.add_script_tag(content=script)
        box = page.locator('[data-merchant-history]')
        box.get_by_role('button', name='Mostra letture salvate' if language == 'it' else 'Show saved readbacks').click()
        box.locator('summary').click()
        box.get_by_role('button', name='Carica osservazioni' if language == 'it' else 'Load observations').click()
        action = box.get_by_role('button', name='Riconcilia ordine originale' if language == 'it' else 'Reconcile original order')
        expect(action).to_be_enabled(); before = len(merchant['calls'])
        page.once('dialog', lambda d: d.dismiss()); action.click()
        assert len(merchant['calls']) == before and resources.state(account)['credits_micro'] == 0
        page.once('dialog', lambda d: d.accept()); action.focus(); page.keyboard.press('Enter')
        expect(box.locator('[role=status]')).to_contain_text('Ledger originale riconciliato' if language == 'it' else 'Original ledger reconciled')
        assert resources.state(account)['credits_micro'] == 1_000_000
        page.once('dialog', lambda d: d.accept()); action.click()
        expect(action).to_be_enabled(); assert resources.state(account)['credits_micro'] == 1_000_000
        assert sum(method == 'POST' and path.endswith('/reconcile') for method, path in requests) == 2
        assert any(path.startswith('/api/admin/paypal/merchant-history/'+snap+'/review') for _, path in requests)
        page.reload(); page.add_script_tag(content=script)
        page.locator('[data-merchant-history]').get_by_role('button', name='Mostra letture salvate' if language == 'it' else 'Show saved readbacks').click()
        page.locator('[data-merchant-history] summary').wait_for()
        assert resources.state(account)['credits_micro'] == 1_000_000 and not errors
        with auth.db() as c:
            assert c.execute("SELECT count(*) FROM payment_reconciliation_events WHERE normalized_json LIKE '%merchant_discovery_binding%'").fetchone()[0] == 1
        browser.close()
