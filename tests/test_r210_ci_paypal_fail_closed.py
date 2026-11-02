"""UI-facing endpoints must retain holds when complete cash is unavailable."""
from app import auth, payment_reconcile_service as service, resource_accounts
from test_r210_account_acceptance import client
from test_r210_paypal import provider as provider  # noqa: F401
from test_r210_paypal_dispute_history import fixture, report
from test_r210_paypal_item_movements import movements, partial
from test_r210_subscriptions import account as account  # noqa: F401

HEADERS = {'X-MTA-Request': '1'}


def test_owner_ambiguous_payout_keeps_hold_until_later_exact_outcome(account, provider, monkeypatch):
    local, _, documents, _, _ = fixture(account, provider, monkeypatch, paid=True, multi=True)
    web = client(account, monkeypatch)
    url = '/api/account/payments/paypal/' + local + '/verify'
    assert web.post(url, json={'confirm': True}, headers=HEADERS).status_code == 200
    documents['PP-D-123'].update(status='RESOLVED', update_time='2026-10-24T02:00:00Z',
                                dispute_outcome={'outcome_code': 'RESOLVED_WITH_PAYOUT'})
    assert web.post(url, json={'confirm': True}, headers=HEADERS).status_code == 409
    item = web.get('/api/account/payments').json()['items'][0]
    assert item['financial_review_pending'] and item['financial_held_minor'] == 500
    assert resource_accounts.state(account)['credits_micro'] == 0 and report()['pending'] >= 1
    documents['PP-D-123'].update(update_time='2026-10-24T03:00:00Z',
                                dispute_outcome={'outcome_code': 'RESOLVED_SELLER_FAVOUR'})
    assert web.post(url, json={'confirm': True}, headers=HEADERS).status_code == 200
    assert resource_accounts.state(account)['credits_micro'] == 5_000_000 and report()['pending'] == 0


def test_admin_unavailable_cash_keeps_held_funds_until_resolution(account, provider, monkeypatch):
    local, _, documents, _, _ = fixture(account, provider, monkeypatch, paid=True)
    assert service.reconcile_paypal(local)['ledger_reconciled']
    documents['PP-D-123'].update(status='RESOLVED', dispute_outcome={'outcome_code': 'RESOLVED_WITH_PAYOUT'})
    web = client(auth.find_user('admin')['id'], monkeypatch)
    url = '/api/admin/service-regime/reconcile-payment'
    body = {'provider': 'paypal', 'order_id': local}
    assert web.post(url, json=body, headers=HEADERS).status_code in (409, 422)
    assert resource_accounts.state(account)['credits_micro'] == 3_000_000 and report()['pending'] >= 1
    documents['PP-D-123'].update(update_time='2026-10-24T03:00:00Z',
                                dispute_outcome={'outcome_code': 'RESOLVED_SELLER_FAVOUR'})
    assert web.post(url, json=body, headers=HEADERS).status_code == 200
    assert resource_accounts.state(account)['credits_micro'] == 5_000_000 and report()['pending'] == 0


def test_admin_failed_cash_check_retains_existing_movement_observations(account, provider, monkeypatch):
    local, _, docs, _, _ = partial(account, provider, monkeypatch, paid=True)
    docs['PP-D-123'].update(status='RESOLVED', dispute_outcome={'outcome_code': 'RESOLVED_WITH_PAYOUT'},
                           **movements(reason='DISPUTE_FEE', value='90071992547409.93', direction='CREDIT'))
    assert service.reconcile_paypal(local)['financial_review_pending']
    web = client(auth.find_user('admin')['id'], monkeypatch)
    response = web.post('/api/admin/service-regime/reconcile-payment',
                        json={'provider': 'paypal', 'order_id': local}, headers=HEADERS)
    assert response.status_code in (409, 422)
    assert resource_accounts.state(account)['credits_micro'] == 2_000_000 and report()['pending'] >= 2
    assert report()['positions'][0]['movement_reviews']['items']
