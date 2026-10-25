import httpx
import pytest
from app.regime_provider_probe import ProviderProbeError
from app.regime_provider_settlement import verify_paypal_settlement, verify_stripe_settlement


def stripe_handler(req):
    if '/checkout/sessions/' in req.url.path:
        return httpx.Response(200, json={'id': 'cs_test_12345', 'status': 'complete', 'payment_status': 'paid', 'amount_total': 1200, 'currency': 'eur', 'payment_intent': 'pi_12345'})
    return httpx.Response(200, json={'id': 'pi_12345', 'status': 'succeeded', 'amount': 1200, 'amount_received': 1200, 'currency': 'eur'})


def paypal_handler(req):
    if req.url.path.endswith('/oauth2/token'):
        return httpx.Response(200, json={'access_token': 'fake-token'})
    return httpx.Response(200, json={'id': 'ORDER123', 'status': 'COMPLETED', 'purchase_units': [{'payments': {'captures': [{'id': 'CAPTURE123', 'status': 'COMPLETED', 'amount': {'value': '12.00', 'currency_code': 'EUR'}}]}}]})


def test_stripe_payment_observed_not_authorized():
    with httpx.Client(transport=httpx.MockTransport(stripe_handler)) as client:
        data = verify_stripe_settlement('cs_test_12345', 'sk_test_mock', 1200, 'EUR', client=client)
    assert data['remote_payment_observed'] and not data['authorizes_entitlement'] and not data['authorizes_cutover']


def test_stripe_amount_mismatch_rejected():
    with httpx.Client(transport=httpx.MockTransport(stripe_handler)) as client:
        with pytest.raises(ProviderProbeError):
            verify_stripe_settlement('cs_test_12345', 'sk_test_mock', 1500, 'EUR', client=client)


def test_paypal_capture_observed_not_authorized():
    with httpx.Client(transport=httpx.MockTransport(paypal_handler)) as client:
        data = verify_paypal_settlement('ORDER123', 'client', 'secret', 1200, 'EUR', environment='sandbox', client=client)
    assert data['capture_ids'] == ['CAPTURE123'] and not data['authorizes_entitlement']


def test_paypal_amount_mismatch_rejected():
    with httpx.Client(transport=httpx.MockTransport(paypal_handler)) as client:
        with pytest.raises(ProviderProbeError):
            verify_paypal_settlement('ORDER123', 'client', 'secret', 1201, 'EUR', environment='sandbox', client=client)


def test_paypal_duplicate_capture_rejected():
    def bad(req):
        resp = paypal_handler(req)
        if req.url.path.endswith('/orders/ORDER123'):
            payload = __import__('json').loads(resp.content)
            captures = payload['purchase_units'][0]['payments']['captures']
            captures.append(dict(captures[0]))
            return httpx.Response(200, json=payload)
        return resp
    with httpx.Client(transport=httpx.MockTransport(bad)) as client:
        with pytest.raises(ProviderProbeError):
            verify_paypal_settlement('ORDER123', 'client', 'secret', 2400, 'EUR', environment='sandbox', client=client)
