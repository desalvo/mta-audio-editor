import httpx
import pytest

from app.regime_provider_probe import ProviderProbeError
from app.regime_provider_settlement import (
    verify_stripe_payment_with_reversals,
    verify_paypal_payment_with_capture_observations,
)


def stripe_payload(req):
    path = req.url.path
    if '/checkout/sessions/' in path:
        return {'id': 'cs_test_12345', 'status': 'complete', 'payment_status': 'paid',
                'amount_total': 1200, 'currency': 'eur', 'payment_intent': 'pi_12345'}
    if '/payment_intents/' in path:
        return {'id': 'pi_12345', 'status': 'succeeded', 'amount': 1200,
                'amount_received': 1200, 'currency': 'eur', 'latest_charge': 'ch_12345'}
    return {'object': 'charge', 'id': 'ch_12345', 'payment_intent': 'pi_12345',
            'amount': 1200, 'currency': 'eur', 'paid': True, 'captured': True,
            'status': 'succeeded', 'amount_refunded': 0, 'refunded': False, 'disputed': False,
            'refunds': {'object': 'list', 'has_more': False, 'data': []}}


def test_stripe_cross_evidence_read_only():
    methods = []
    def handler(req):
        methods.append(req.method)
        return httpx.Response(200, json=stripe_payload(req))
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = verify_stripe_payment_with_reversals('cs_test_12345', 'sk_test_key', 1200, 'EUR', client=client)
    assert set(methods) == {'GET'}
    assert result['no_reversal_observed_at_lookup'] and not result['authorizes_entitlement']
    assert not result['local_ledger_reconciled']


@pytest.mark.parametrize('change', [
    {'latest_charge': None}, {'latest_charge': 'ch_changed'},
])
def test_stripe_unlinked_charge_fails(change):
    def handler(req):
        payload = stripe_payload(req)
        if '/payment_intents/' in req.url.path:
            payload.update(change)
        return httpx.Response(200, json=payload)
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(ProviderProbeError):
            verify_stripe_payment_with_reversals('cs_test_12345', 'sk_test_key', 1200, 'EUR', client=client)


def test_stripe_refunded_charge_fails():
    def handler(req):
        payload = stripe_payload(req)
        if '/charges/' in req.url.path:
            payload['amount_refunded'] = 100
        return httpx.Response(200, json=payload)
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(ProviderProbeError):
            verify_stripe_payment_with_reversals('cs_test_12345', 'sk_test_key', 1200, 'EUR', client=client)


def paypal_payload(req):
    if req.url.path.endswith('/oauth2/token'):
        return {'access_token': 'mock-token'}
    if '/checkout/orders/' in req.url.path:
        return {'id': 'ORDER123', 'status': 'COMPLETED',
                'purchase_units': [{'payments': {'captures': [
                    {'id': 'CAPTURE123', 'status': 'COMPLETED',
                     'amount': {'value': '12.00', 'currency_code': 'EUR'}}]}}]}
    return {'id': 'CAPTURE123', 'status': 'COMPLETED'}


def test_paypal_cross_evidence_read_only():
    calls = []
    def handler(req):
        calls.append(req.url.path)
        return httpx.Response(200, json=paypal_payload(req))
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = verify_paypal_payment_with_capture_observations(
            'ORDER123', 'client', 'secret', 1200, 'EUR', environment='sandbox', client=client)
    assert any('/payments/captures/CAPTURE123' in path for path in calls)
    assert not result['refunds_and_disputes_verified'] and not result['authorizes_cutover']


def test_paypal_capture_refunded_fails():
    def handler(req):
        payload = paypal_payload(req)
        if '/payments/captures/' in req.url.path:
            payload['status'] = 'REFUNDED'
        return httpx.Response(200, json=payload)
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(ProviderProbeError):
            verify_paypal_payment_with_capture_observations(
                'ORDER123', 'client', 'secret', 1200, 'EUR', environment='sandbox', client=client)
