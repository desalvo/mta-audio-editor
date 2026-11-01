"""Malformed provider replies preserve an uncertain, recoverable checkout."""
import pytest

from app import auth, credit_purchases as stripe, paypal_payments as paypal
from app.regime_operation_fence import FenceBlocked
from test_r210_subscriptions import account as account, plan  # noqa: F401
from test_r210_paypal import provider as provider  # noqa: F401
from test_r210_credit_checkout import prepare


@pytest.mark.parametrize('reply', [None, [], 'unexpected', {'id': 17, 'url': 'https://checkout.stripe.com/test'},
    {'id': '', 'url': 'https://checkout.stripe.com/test'}, {'id': 'pi_wrong', 'url': 'https://checkout.stripe.com/test'},
    {'id': 'cs_../wrong', 'url': 'https://checkout.stripe.com/test'}, {'id': 'cs_'+('a'*111), 'url': 'https://checkout.stripe.com/test'}])
def test_stripe_malformed_create_is_uncertain_and_never_reposted(account, monkeypatch, reply):
    prepare(account, monkeypatch)
    attempts = []
    monkeypatch.setattr(stripe, '_stripe', lambda *args: attempts.append(1) or reply)
    for error in (ValueError, FenceBlocked):
        with pytest.raises(error):
            stripe.checkout(account, 500, 'malformed-stripe-request')
    with auth.db() as c:
        assert tuple(c.execute('SELECT state,attempts,provider_reference FROM regime_payment_outbox').fetchone()) == ('uncertain', 1, None)
        assert c.execute('SELECT session_id FROM credit_purchase_orders').fetchone()[0] is None
    assert len(attempts) == 1


@pytest.mark.parametrize('reply', [None, [], {'id': 42, 'links': []}, {'id': 'ORDER123', 'links': None},
                                   {'id': 'ORDER123', 'links': [None]}])
def test_paypal_malformed_create_is_uncertain_and_never_reposted(account, provider, monkeypatch, reply):
    plan(account)
    original = paypal._api
    attempts = []
    def api(cfg, method, path, *args):
        if method == 'POST' and path == '/v2/checkout/orders':
            attempts.append(1)
            return reply
        return original(cfg, method, path, *args)
    monkeypatch.setattr(paypal, '_api', api)
    body = {'kind': 'credits', 'amount_cents': 500, 'request_id': 'malformed-paypal-request'}
    for error in (ValueError, FenceBlocked):
        with pytest.raises(error):
            paypal.checkout(account, body)
    with auth.db() as c:
        assert tuple(c.execute('SELECT state,attempts,provider_reference FROM regime_payment_outbox').fetchone()) == ('uncertain', 1, None)
        assert c.execute('SELECT provider_order FROM paypal_orders').fetchone()[0] is None
    assert len(attempts) == 1


def test_malformed_paypal_create_can_be_recovered_and_captured_once(account, provider, monkeypatch):
    from app import checkout_reference_recovery as recovery, resource_accounts
    plan(account)
    original = paypal._api
    def api(cfg, method, path, *args):
        response = original(cfg, method, path, *args)
        if method == 'POST' and path == '/v2/checkout/orders':
            return {'id': response['id'], 'links': [None]}
        return response
    monkeypatch.setattr(paypal, '_api', api)
    body = {'kind': 'credits', 'amount_cents': 500, 'request_id': 'malformed-recover-request'}
    with pytest.raises(ValueError):
        paypal.checkout(account, body)
    with auth.db() as c:
        local = c.execute('SELECT id FROM paypal_orders').fetchone()[0]
    reference = next(iter(provider[0]))
    provider[0][reference]['intent'] = 'CAPTURE'
    assert recovery.recover('paypal', local, reference)['reference_confirmed']
    assert paypal.capture(account, local)['status'] == 'paid'
    assert paypal.capture(account, local)['status'] == 'paid'
    assert resource_accounts.state(account)['credits_micro'] == 5_000_000
    assert len([c for c in provider[1] if c[0] == 'POST' and c[1] == '/v2/checkout/orders']) == 1
