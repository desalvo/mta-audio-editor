"""Complete settings financial recovery under C2, real service/ledger; fake GET provider only."""
import httpx
import pytest

from app import resource_accounts as resources, service_admission as gate
from test_r210_admin_cutover_e2e import ready as ready, account as account, BASE  # noqa: F401
from test_r210_cutover_service_drain_browser import session, action, confirm
from test_r210_noncommercial_collection_browser import nc_browser_config as nc_browser_config  # noqa: F401


@pytest.mark.parametrize('language', ['it', 'en'])
@pytest.mark.parametrize('width', [390, 1280])
def test_actual_financial_reconciliation_closes_original_checkout_under_drain_without_general_clearance(
        ready, monkeypatch, nc_browser_config, language, width):
    from playwright.sync_api import sync_playwright, expect
    from app import payment_reconcile_service, credit_purchases as shop
    from test_r210_authenticated_ledger_service import transport
    original_client = httpx.Client
    shop.settings({'secret_key': 'sk_test_test', 'webhook_secret': 'whsec_test'})
    monkeypatch.setattr(shop, '_stripe', lambda data, key, local: {
        'id': 'cs_test_' + local, 'url': 'https://checkout.stripe.com/c/pay/' + local})
    order = shop.checkout(ready[1], 500, 'operator-review-financial-1')['order_id']
    mock, calls = transport(order)
    monkeypatch.setattr(payment_reconcile_service.httpx, 'Client', lambda **kw: original_client(transport=mock, **kw))
    before = resources.state(ready[1])['credits_micro']
    with sync_playwright() as api:
        browser = api.chromium.launch(**nc_browser_config)
        page, errors, posts = session(ready, monkeypatch, browser, language, width)
        confirm(page, action(page, 'begin'))
        denied = ready[0].post('/api/admin/service-regime/reconcile-payment', json={'provider': 'stripe', 'order_id': order})
        assert denied.status_code == 403 and not calls
        expect(page.locator('[data-service-drain-status]')).to_contain_text('ancora da verificare' if language == 'it' else 'still requires verification')
        reconcile = page.get_by_role('button', name=('Riconcilia dal provider' if language == 'it' else 'Reconcile from provider') + ' · stripe · ' + order, exact=True)
        expect(reconcile).to_be_enabled(); confirm(page, reconcile)
        expect(page.locator('#regimeActionStatus')).to_contain_text('Ledger riconciliato' if language == 'it' else 'Ledger reconciled')
        action(page, 'refresh').click()
        expect(page.locator('[data-service-drain-status]')).to_contain_text('Lavoro originale chiuso' if language == 'it' else 'Original work closed')
        page.get_by_role('button', name='Verifica prima del cambio' if language == 'it' else 'Check before changing', exact=True).click()
        expect(page.locator('[data-preflight-family=provider_history]')).to_contain_text('Revisione completa necessaria' if language == 'it' else 'Complete review required')
        expect(page.locator('[data-cutover-acknowledged]')).to_be_disabled()
        with gate.control():
            assert resources.state(ready[1])['credits_micro'] == before + 3_000_000
        assert any('/refunds?' in url for url in calls) and len(calls) > 5
        assert len([p for p, _ in posts if p == '/api/admin/service-regime/reconcile-payment']) == 1
        assert not any(p == BASE for p, _ in posts) and not errors
        assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
        browser.close()
