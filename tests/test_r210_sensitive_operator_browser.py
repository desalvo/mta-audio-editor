"""Entire shipped settings, actual private financial review and original writes."""
import os
import sqlite3

import pytest

from app import auth, ai_billing
from app.regime_worker_claims import claim
from test_r210_admin_cutover_e2e import ready as ready, account as account, BASE  # noqa: F401
from test_r210_cutover_service_drain_browser import session, action, confirm
from test_r210_noncommercial_collection_browser import nc_browser_config as nc_browser_config  # noqa: F401


def legacy_orders(ready, count=125):
    with auth.db() as c:
        for n in range(count):
            c.execute('''INSERT INTO paypal_orders
                (id,user_id,request_id,kind,period_start,amount_cents,environment,client_fingerprint,
                 provider_order,status,created_at,paid_at) VALUES(?,?,?,'subscription',1,500,'sandbox','legacy',?,'paid',1,2)''',
                (f'legacy-{n:03d}', ready[1], f'legacy-request-{n}', f'LEGACYPAY{n:06d}'))


def setup(ready, monkeypatch, scenario):
    if scenario == 'legacy': legacy_orders(ready)
    elif scenario == 'provider':
        with auth.db() as c:
            c.execute('UPDATE paypal_config SET enabled=1,client_secret=? WHERE id=1', (auth._seal('private-preflight-marker'),))
            c.execute("INSERT INTO paypal_events(id,received_at) VALUES('actual-provider-history',1)")
    elif scenario == 'unknown-schema':
        with auth.db() as c: c.execute('CREATE TABLE unreviewed_financial_history(id TEXT)')
    elif scenario == 'worker':
        identifier = ai_billing.create_job(ready[1], 'vocal-harmony')
        with auth.db() as c:
            c.execute('BEGIN IMMEDIATE'); claim(c, identifier, worker_id='original-review-worker', token='original-review-token')
    elif scenario == 'ledger-unavailable':
        from app import payment_reconciliation
        def unavailable(*args, **kwargs): raise sqlite3.OperationalError('private diagnostic marker')
        monkeypatch.setattr(payment_reconciliation, 'report', unavailable)


@pytest.mark.parametrize('has_history', [False, True])
def test_provider_configuration_and_actual_history_have_distinct_preflight_results(ready, monkeypatch, has_history):
    if has_history:
        setup(ready, monkeypatch, 'provider')
    else:
        with auth.db() as c:
            c.execute('UPDATE paypal_config SET enabled=1,client_secret=? WHERE id=1',
                (auth._seal('private-preflight-marker'),))
    response = ready[0].get(BASE + '/preflight?target=NON_COMMERCIAL')
    assert response.status_code == 200
    data = response.json()
    assert 'private-preflight-marker' not in response.text
    provider = next(item for item in data['sections'] if item['id'] == 'provider_history')
    assert provider['counts']['records'] == int(has_history)
    assert provider['state'] == ('review_required' if has_history else 'verified')
    assert data['maintenance_eligibility'] == ('blocked' if has_history else 'verified_precommercial_profile')


@pytest.mark.parametrize('language', ['it', 'en'])
@pytest.mark.parametrize('width', [390, 1280])
@pytest.mark.parametrize('scenario,family', [('provider', 'provider_history'), ('legacy', 'original_subscription_basis'),
    ('unknown-schema', 'schema_coverage'), ('worker', 'worker_claims'), ('ledger-unavailable', 'payment_ledger')])
def test_complete_financial_review_blocks_unsafe_confirmation_and_keeps_all_families_readable(
        ready, monkeypatch, nc_browser_config, language, width, scenario, family):
    from playwright.sync_api import sync_playwright, expect
    setup(ready, monkeypatch, scenario)
    with sync_playwright() as api:
        browser = api.chromium.launch(**nc_browser_config)
        page, errors, posts = session(ready, monkeypatch, browser, language, width)
        confirm(page, action(page, 'begin'))
        page.get_by_role('button', name='Verifica prima del cambio' if language == 'it' else 'Check before changing', exact=True).click()
        expect(page.locator('[data-preflight-family]')).to_have_count(13)
        selected = page.locator('[data-preflight-family=' + family + ']')
        expect(selected).to_contain_text('completa necessaria' if scenario == 'provider' and language == 'it' else
            'Complete review required' if scenario == 'provider' else
            'Da completare' if scenario == 'worker' and language == 'it' else
            'Outstanding' if scenario == 'worker' else
            'Prova non verificabile' if language == 'it' else 'Evidence unverified')
        expect(page.locator('[data-cutover-acknowledged]')).to_be_disabled()
        execute = page.get_by_role('button', name='Conferma cambio di regime' if language == 'it' else 'Confirm regime change', exact=True)
        expect(execute).to_be_disabled()
        assert not any(path == BASE for path, _ in posts)
        payload = ready[0].get(BASE + '/preflight?target=NON_COMMERCIAL').text
        assert 'private-preflight-marker' not in payload and 'private diagnostic marker' not in payload
        if scenario == 'legacy':
            expect(selected).to_contain_text('125')
            expect(page.locator('[data-preflight-case]')).to_have_count(50)
            page.locator('[data-preflight-more]').click(); expect(page.locator('[data-preflight-case]').first).to_contain_text('legacy-050')
            page.locator('[data-preflight-more]').click(); expect(page.locator('[data-preflight-case]').last).to_contain_text('legacy-124')
            expect(page.locator('[data-preflight-case]')).to_have_count(25)
            expect(execute).to_be_disabled()
        assert page.evaluate('document.documentElement.scrollWidth<=innerWidth') and not errors
        browser.close()


@pytest.mark.parametrize('language', ['it', 'en'])
@pytest.mark.parametrize('width', [390, 1280])
@pytest.mark.parametrize('provider_prepared', [False, True])
def test_sensitive_review_requires_unchecked_acknowledgement_and_invalidates_after_new_drain(
        ready, monkeypatch, nc_browser_config, language, width, provider_prepared):
    from playwright.sync_api import sync_playwright, expect
    if provider_prepared:
        with auth.db() as c:
            c.execute('UPDATE paypal_config SET enabled=1,client_secret=? WHERE id=1',
                (auth._seal('private-preflight-marker'),))
    with sync_playwright() as api:
        browser = api.chromium.launch(**nc_browser_config)
        page, errors, posts = session(ready, monkeypatch, browser, language, width)
        confirm(page, action(page, 'begin'))
        check = page.get_by_role('button', name='Verifica prima del cambio' if language == 'it' else 'Check before changing', exact=True)
        execute = page.get_by_role('button', name='Conferma cambio di regime' if language == 'it' else 'Confirm regime change', exact=True)
        ack = page.locator('[data-cutover-acknowledged]')
        check.click(); expect(ack).to_be_enabled(); expect(ack).not_to_be_checked(); expect(execute).to_be_disabled()
        ack.check(); expect(execute).to_be_enabled()
        confirm(page, action(page, 'resume')); expect(ack).not_to_be_checked(); expect(execute).to_be_disabled()
        confirm(page, action(page, 'begin')); check.click(); expect(ack).not_to_be_checked()
        ack.check(); expect(execute).to_be_enabled()
        page.once('dialog', lambda d: d.dismiss()); execute.click()
        assert not any(path == BASE for path, _ in posts)
        confirm(page, execute)
        expect(page.locator('[data-cutover-status]')).to_contain_text('Passaggio completato' if language == 'it' else 'Change completed')
        assert len([path for path, _ in posts if path == BASE]) == 1
        assert not errors; browser.close()


@pytest.mark.parametrize('language', ['it', 'en'])
@pytest.mark.parametrize('width', [390, 1280])
@pytest.mark.parametrize('phase', ['ready', 'blocked'])
def test_entire_shipped_sensitive_controls_accessible_without_rule_exclusions(
        ready, monkeypatch, nc_browser_config, language, width, phase):
    from playwright.sync_api import sync_playwright, expect
    supplied = os.environ.get('MTA_TEST_AXE_CORE')
    if not supplied: pytest.skip('Pinned test-only axe-core required')
    if phase == 'blocked': setup(ready, monkeypatch, 'provider')
    with sync_playwright() as api:
        browser = api.chromium.launch(**nc_browser_config)
        page, errors, posts = session(ready, monkeypatch, browser, language, width)
        confirm(page, action(page, 'begin'))
        page.get_by_role('button', name='Verifica prima del cambio' if language == 'it' else 'Check before changing', exact=True).click()
        expect(page.locator('[data-preflight-family]')).to_have_count(13)
        page.add_script_tag(path=supplied)
        violations = page.evaluate("async()=>{const r=await axe.run(document.querySelector('#serviceRegimePanel'));return r.violations.map(v=>({id:v.id,nodes:v.nodes.map(n=>n.target)}))}")
        assert violations == [], violations
        assert page.evaluate('document.documentElement.scrollWidth<=innerWidth') and not errors
        assert not any(path == BASE for path, _ in posts)
        browser.close()


@pytest.mark.parametrize('language', ['it', 'en'])
def test_failed_review_read_clears_prior_acknowledgement_until_explicit_retry(
        ready, monkeypatch, nc_browser_config, language):
    from playwright.sync_api import sync_playwright, expect
    with sync_playwright() as api:
        browser = api.chromium.launch(**nc_browser_config)
        page, errors, posts = session(ready, monkeypatch, browser, language, 390)
        confirm(page, action(page, 'begin'))
        check = page.get_by_role('button', name='Verifica prima del cambio' if language == 'it' else 'Check before changing', exact=True)
        execute = page.get_by_role('button', name='Conferma cambio di regime' if language == 'it' else 'Confirm regime change', exact=True)
        ack = page.locator('[data-cutover-acknowledged]')
        check.click(); ack.check(); expect(execute).to_be_enabled()
        def unavailable(route): route.fulfill(status=503, content_type='application/json', body='{}')
        page.route('**/cutovers/preflight?*', unavailable)
        check.click(); expect(execute).to_be_disabled(); expect(ack).not_to_be_checked()
        expect(page.locator('[data-cutover-status]')).to_contain_text('non disponibile' if language == 'it' else 'unavailable')
        page.unroute('**/cutovers/preflight?*', unavailable)
        check.click(); expect(ack).to_be_enabled(); expect(ack).not_to_be_checked()
        assert not any(path == BASE for path, _ in posts) and not errors
        browser.close()
