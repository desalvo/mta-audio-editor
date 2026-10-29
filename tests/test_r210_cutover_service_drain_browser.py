"""Opt-in actual settings UI -> durable drain -> real cutover and forward recovery."""
import json
from urllib.parse import urlsplit

import pytest

from app import auth, regime_admin_cutover as cutover, service_admission as gate
from test_r210_noncommercial_collection_browser import nc_browser_config as nc_browser_config  # noqa: F401
from test_r210_admin_cutover_e2e import ready as ready, account as account, BASE  # noqa: F401


def session(ready, monkeypatch, browser, language, width, *, lose_begin=False, unavailable=None):
    client, _, admin = ready
    with auth.db() as con:
        con.execute('UPDATE users SET language=? WHERE id=?', (language, admin))
    monkeypatch.setenv('MTA_SERVICE_ADMISSION', gate.MODE)
    assert client.get('/api/admin/service-admission').json()['phase'] == 'open'
    page = browser.new_page(viewport={'width': width, 'height': 1000})
    errors = []; posts = []; lost = []
    page.on('pageerror', lambda exc: errors.append(str(exc)))
    def serve(route):
        request = route.request; url = urlsplit(request.url)
        assert url.hostname == 'mta.test'
        if unavailable and unavailable[0] and url.path == '/api/admin/service-admission':
            route.fulfill(status=503, content_type='application/json', body='{}'); return
        if request.method == 'POST':
            assert request.headers.get('x-mta-request') == '1'
            posts.append((url.path, json.loads(request.post_data)))
        response = client.request(request.method, url.path + ('?' + url.query if url.query else ''),
            content=request.post_data, headers={k: v for k, v in request.headers.items()
                                               if k in {'content-type', 'x-mta-request'}})
        if lose_begin and not lost and request.method == 'POST' and url.path.endswith('/service-admission/change'):
            assert response.status_code == 200
            lost.append(True); route.abort('failed'); return
        route.fulfill(status=response.status_code, content_type=response.headers.get('content-type', 'application/json'),
                      body=response.content)
    page.route('**/*', serve)
    page.goto('https://mta.test/settings'); page.wait_for_load_state('networkidle')
    return page, errors, posts


def action(page, key): return page.locator('[data-service-drain-action=' + key + ']')


def confirm(page, button):
    page.once('dialog', lambda dialog: dialog.accept()); button.focus(); page.keyboard.press('Enter')


@pytest.mark.parametrize('language', ['it', 'en'])
@pytest.mark.parametrize('width', [390, 1280])
def test_full_settings_original_drain_two_way_cutover_explicit_resume(ready, monkeypatch, nc_browser_config, language, width):
    from playwright.sync_api import sync_playwright, expect
    with sync_playwright() as api:
        browser = api.chromium.launch(**nc_browser_config)
        page, errors, posts = session(ready, monkeypatch, browser, language, width)
        expect(action(page, 'begin')).to_be_enabled()
        page.once('dialog', lambda dialog: dialog.dismiss()); action(page, 'begin').click()
        assert posts == []
        confirm(page, action(page, 'begin'))
        expect(page.locator('[data-service-drain-status]')).to_contain_text('Lavoro originale chiuso' if language == 'it' else 'Original work closed')
        original = posts[0][1]
        for target in ('NON_COMMERCIAL', 'COMMERCIAL'):
            page.locator('#maintenanceCutoverTarget').select_option(target)
            page.get_by_role('button', name='Verifica prima del cambio' if language == 'it' else 'Check before changing', exact=True).click()
            execute = page.get_by_role('button', name='Conferma cambio di regime' if language == 'it' else 'Confirm regime change', exact=True)
            page.locator('[data-cutover-acknowledged]').check()
            try:
                expect(execute).to_be_enabled()
            except AssertionError:
                raise AssertionError(json.dumps({'status': page.locator('[data-cutover-status]').inner_text(),
                    'progress': page.locator('[data-cutover-progress]').inner_text(),
                    'preview': ready[0].get(BASE + '/preview?target=' + target).text})) from None
            confirm(page, execute)
            expect(page.locator('[data-cutover-status]')).to_contain_text('Passaggio completato' if language == 'it' else 'Change completed')
        confirm(page, action(page, 'resume'))
        expect(page.locator('[data-service-drain-status]')).to_contain_text('Servizio aperto' if language == 'it' else 'Service open')
        assert posts[-1][1]['identifier'] == original['identifier'] and posts[-1][1]['expected_generation'] == 1
        assert len([p for p, _ in posts if p == BASE]) == 2
        assert ready[0].get('/api/service-regime').json()['regime'] == 'COMMERCIAL'
        assert page.evaluate('document.documentElement.scrollWidth<=innerWidth') and not errors
        browser.close()


@pytest.mark.parametrize('language', ['it', 'en'])
def test_lost_drain_response_reload_uses_original_server_identity_without_second_begin(ready, monkeypatch, nc_browser_config, language):
    from playwright.sync_api import sync_playwright, expect
    with sync_playwright() as api:
        browser = api.chromium.launch(**nc_browser_config)
        page, errors, posts = session(ready, monkeypatch, browser, language, 390, lose_begin=True)
        confirm(page, action(page, 'begin'))
        expect(page.locator('[data-service-drain-status]')).to_contain_text('Esito da verificare' if language == 'it' else 'Outcome needs verification')
        expect(action(page, 'begin')).to_be_disabled(); expect(action(page, 'resume')).to_be_disabled()
        original = posts[0][1]
        page.reload(); expect(action(page, 'resume')).to_be_enabled()
        expect(page.locator('[data-service-drain-status]')).to_contain_text(original['identifier'])
        confirm(page, action(page, 'resume'))
        expect(action(page, 'begin')).to_be_enabled()
        assert len(posts) == 2 and posts[-1][1]['identifier'] == original['identifier']
        assert not errors; browser.close()


@pytest.mark.parametrize('language', ['it', 'en'])
def test_committed_crash_holds_service_until_original_forward_recovery(ready, monkeypatch, nc_browser_config, language):
    from playwright.sync_api import sync_playwright, expect
    with sync_playwright() as api:
        browser = api.chromium.launch(**nc_browser_config)
        page, errors, posts = session(ready, monkeypatch, browser, language, 390)
        confirm(page, action(page, 'begin')); expect(action(page, 'resume')).to_be_enabled()
        page.get_by_role('button', name='Verifica prima del cambio' if language == 'it' else 'Check before changing', exact=True).click()
        execute = page.get_by_role('button', name='Conferma cambio di regime' if language == 'it' else 'Confirm regime change', exact=True)
        page.locator('[data-cutover-acknowledged]').check()
        expect(execute).to_be_enabled()
        real = cutover.reconcile_mirror
        def crash(*args): raise OSError('Simulated mirror failure')
        monkeypatch.setattr(cutover, 'reconcile_mirror', crash)
        confirm(page, execute)
        recover = page.locator('[data-cutover-recovery]'); expect(recover).to_be_enabled()
        action(page, 'refresh').click(); expect(action(page, 'resume')).to_be_disabled()
        monkeypatch.setattr(cutover, 'reconcile_mirror', real)
        confirm(page, recover)
        expect(page.locator('[data-cutover-progress]')).to_contain_text('Nessun passaggio attivo' if language == 'it' else 'No active transition')
        action(page, 'refresh').click(); expect(action(page, 'resume')).to_be_enabled()
        confirm(page, action(page, 'resume')); expect(action(page, 'begin')).to_be_enabled()
        assert len([p for p, _ in posts if p == BASE]) == 1
        assert not errors; browser.close()


@pytest.mark.parametrize('language', ['it', 'en'])
def test_unavailable_drain_read_disables_controls_until_explicit_refresh(ready, monkeypatch, nc_browser_config, language):
    from playwright.sync_api import sync_playwright, expect
    unavailable = [True]
    with sync_playwright() as api:
        browser = api.chromium.launch(**nc_browser_config)
        page, errors, posts = session(ready, monkeypatch, browser, language, 390, unavailable=unavailable)
        expect(page.locator('[data-service-drain-status]')).to_contain_text('Stato non disponibile' if language == 'it' else 'State unavailable')
        for key in ('begin', 'resume'): expect(action(page, key)).to_be_disabled()
        unavailable[0] = False; action(page, 'refresh').click(); expect(action(page, 'begin')).to_be_enabled()
        assert not posts and not errors; browser.close()


@pytest.mark.parametrize('language', ['it', 'en'])
def test_build_mismatch_requires_explicit_original_handoff(ready, monkeypatch, nc_browser_config, language):
    from playwright.sync_api import sync_playwright, expect
    import sqlite3
    with sync_playwright() as api:
        browser = api.chromium.launch(**nc_browser_config)
        page, errors, posts = session(ready, monkeypatch, browser, language, 390)
        confirm(page, action(page, 'begin')); expect(action(page, 'resume')).to_be_enabled()
        with sqlite3.connect(gate.path()) as con: con.execute('UPDATE state SET build=?', ('a'*64,))
        action(page, 'refresh').click(); expect(action(page, 'upgrade')).to_be_enabled()
        expect(action(page, 'resume')).to_be_disabled()
        confirm(page, action(page, 'upgrade')); expect(action(page, 'resume')).to_be_enabled()
        assert posts[-1][1] == {'expected_generation': 1, 'expected_build': 'a'*64, 'confirm': True}
        assert not errors; browser.close()
