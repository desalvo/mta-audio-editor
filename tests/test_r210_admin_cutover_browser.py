"""Opt-in genuine Chromium against actual admin handlers/accounting; no fake API."""
from urllib.parse import urlsplit
import json

import pytest
from app import auth, regime_admin_cutover as cutover
from test_r210_admin_cutover_e2e import ready as ready, account as account, BASE  # noqa: F401


def browser_session(client, language, browser, width, *, lost_reply=False):
    page = browser.new_page(viewport={'width': width, 'height': 850})
    errors = []
    posts = []
    flags = {'lost': False, 'audit_unavailable': False}
    page.on('pageerror', lambda error: errors.append(str(error)))
    def serve(route):
        url = urlsplit(route.request.url)
        if url.path == '/':
            route.fulfill(content_type='text/html', body=f'''<!doctype html><html lang="{language}">
                <meta name="viewport" content="width=device-width,initial-scale=1"><title>MTA acceptance</title>
                <main id="serviceRegimePanel"><h2>MTA</h2></main>
                <script src="/static/regime_cutover_panel.js"></script></html>''')
            return
        if url.path == BASE and route.request.method == 'GET' and flags['audit_unavailable']:
            route.fulfill(status=503, content_type='application/json', body='{}')
            return
        if route.request.method == 'POST':
            assert route.request.headers.get('x-mta-request') == '1'
            posts.append((url.path, json.loads(route.request.post_data)))
            if len(posts) > 1:
                flags['audit_unavailable'] = False
        headers = {key: value for key, value in route.request.headers.items()
                   if key in {'content-type', 'x-mta-request', 'accept-language'}}
        response = client.request(route.request.method, url.path + ('?' + url.query if url.query else ''),
                                  headers=headers, content=route.request.post_data)
        if lost_reply and route.request.method == 'POST' and url.path == BASE and not flags['lost']:
            assert response.status_code == 200, response.text
            flags.update(lost=True, audit_unavailable=True)
            route.abort('failed')
            return
        route.fulfill(status=response.status_code, content_type=response.headers.get('content-type', 'application/json'), body=response.content)
    page.route('https://mta.test/**', serve)
    page.goto('https://mta.test/')
    page.wait_for_selector('[data-regime-cutover]')
    return page, errors, posts


def check_and_change(page, language, target):
    page.locator('#maintenanceCutoverTarget').select_option(target)
    page.get_by_role('button', name='Verifica prima del cambio' if language == 'it' else 'Check before changing', exact=True).click()
    confirm = page.get_by_role('button', name='Conferma cambio di regime' if language == 'it' else 'Confirm regime change', exact=True)
    from playwright.sync_api import expect
    expect(confirm).to_be_enabled()
    confirm.click()


@pytest.mark.parametrize('language', ['it', 'en'])
@pytest.mark.parametrize('width', [390, 1280])
def test_actual_cutover_roundtrip_wallet_periods_keyboard_and_audit(ready, chromium_capability, language, width):
    from playwright.sync_api import sync_playwright, expect
    from app.regime_balance_continuity import snapshot
    client, uid, _ = ready
    with auth.db() as con:
        con.execute('BEGIN IMMEDIATE')
        before = snapshot(con)
    with sync_playwright() as api:
        browser = api.chromium.launch(headless=True, args=['--no-sandbox'])
        page, errors, posts = browser_session(client, language, browser, width)
        page.on('dialog', lambda dialog: dialog.accept())
        page.locator('#maintenanceCutoverTarget').focus()
        page.keyboard.press('Tab')
        expect(page.get_by_role('button', name='Verifica prima del cambio' if language == 'it' else 'Check before changing', exact=True)).to_be_focused()
        check_and_change(page, language, 'NON_COMMERCIAL')
        expect(page.locator('[data-cutover-status]')).to_contain_text('Passaggio completato' if language == 'it' else 'Change completed')
        expect(page.locator('#maintenanceCutoverTarget')).to_be_enabled()
        check_and_change(page, language, 'COMMERCIAL')
        expect(page.locator('[data-cutover-status]')).to_contain_text('Passaggio completato' if language == 'it' else 'Change completed')
        expect(page.locator('[data-cutover-audit] li')).to_have_count(2)
        assert page.evaluate('document.documentElement.scrollWidth') <= width
        assert len(posts) == 2 and not errors
        with auth.db() as con:
            con.execute('BEGIN IMMEDIATE')
            assert snapshot(con) == before
        assert client.get('/api/service-regime').json()['regime'] == 'COMMERCIAL'
        browser.close()


@pytest.mark.parametrize('language', ['it', 'en'])
def test_actual_committed_recovery_requires_confirmation_and_preserves_wallet(ready, monkeypatch, chromium_capability, language):
    from playwright.sync_api import sync_playwright, expect
    from app import resource_accounts
    client, uid, _ = ready
    original = cutover.reconcile_mirror
    calls = []
    def fail_once(*args):
        result = original(*args)
        calls.append(True)
        if len(calls) == 1:
            raise OSError('Injected interruption after durable mirror replacement')
        return result
    monkeypatch.setattr(cutover, 'reconcile_mirror', fail_once)
    with sync_playwright() as api:
        browser = api.chromium.launch(headless=True, args=['--no-sandbox'])
        page, errors, posts = browser_session(client, language, browser, 1280)
        page.on('dialog', lambda dialog: dialog.accept())
        check_and_change(page, language, 'NON_COMMERCIAL')
        recovery = page.get_by_role('button', name='Completa il recupero' if language == 'it' else 'Complete recovery', exact=True)
        expect(recovery).to_be_visible()
        assert client.get('/api/service-regime').status_code == 503
        recovery.click()
        expect(page.locator('[data-cutover-status]')).to_contain_text('Passaggio completato' if language == 'it' else 'Change completed')
        assert len(posts) == 2 and posts[1][0].endswith('/recover') and not errors
        assert client.get(BASE).json()['total'] == 1
        with auth.db() as con:
            assert resource_accounts._balance(con, uid) == 1_000_000
        browser.close()


@pytest.mark.parametrize('language', ['it', 'en'])
def test_lost_response_reload_retries_only_original_identity_without_second_cutover(ready, chromium_capability, language):
    from playwright.sync_api import sync_playwright, expect
    client, _, _ = ready
    with sync_playwright() as api:
        browser = api.chromium.launch(headless=True, args=['--no-sandbox'])
        page, errors, posts = browser_session(client, language, browser, 390, lost_reply=True)
        page.on('dialog', lambda dialog: dialog.accept())
        check_and_change(page, language, 'NON_COMMERCIAL')
        retry_name = 'Verifica o riprendi la stessa operazione' if language == 'it' else 'Check or resume the same operation'
        expect(page.locator('[data-cutover-audit-status]')).to_contain_text('Registro non disponibile' if language == 'it' else 'Audit unavailable')
        expect(page.get_by_role('button', name=retry_name, exact=True)).to_be_enabled()
        page.reload()
        retry = page.get_by_role('button', name=retry_name, exact=True)
        expect(page.locator('[data-cutover-audit-status]')).to_contain_text('Registro non disponibile' if language == 'it' else 'Audit unavailable')
        expect(retry).to_be_enabled()
        retry.click()
        expect(page.locator('[data-cutover-status]')).to_contain_text('Passaggio completato' if language == 'it' else 'Change completed')
        assert len(posts) == 2 and posts[0] == posts[1] and not errors
        assert client.get(BASE).json()['total'] == 1
        browser.close()


def test_unknown_financial_history_cannot_enable_confirmation(ready, chromium_capability):
    from playwright.sync_api import sync_playwright, expect
    client, _, _ = ready
    with auth.db() as con:
        con.execute("INSERT INTO paypal_events VALUES('unknown-browser-history',1)")
    with sync_playwright() as api:
        browser = api.chromium.launch(headless=True, args=['--no-sandbox'])
        page, errors, posts = browser_session(client, 'en', browser, 390)
        page.get_by_role('button', name='Check before changing', exact=True).click()
        expect(page.locator('[data-cutover-status]')).to_contain_text('Change unavailable')
        expect(page.get_by_role('button', name='Confirm regime change', exact=True)).to_be_disabled()
        assert not posts and not errors
        browser.close()
