import httpx
import pytest
from app.regime_provider_probe import ProviderProbeError, probe_paypal_order, probe_stripe_checkout


def fake_client(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_stripe_paid_is_evidence_not_settlement():
    def handler(request):
        assert request.method == 'GET' and request.url.host == 'api.stripe.com'
        assert request.headers['Authorization'] == 'Bearer sk_test_dummy'
        return httpx.Response(200, json={'id': 'cs_test_12345', 'status': 'complete', 'payment_status': 'paid'})
    with fake_client(handler) as client:
        result = probe_stripe_checkout('cs_test_12345', 'sk_test_dummy', client=client)
    assert result['payment_status'] == 'paid'
    assert not result['authorizes_entitlement'] and not result['authorizes_cutover']


@pytest.mark.parametrize('response', [
    {'id': 'cs_test_wrong', 'status': 'complete', 'payment_status': 'paid'},
    {'id': 'cs_test_12345', 'status': 'complete', 'payment_status': 'unknown'},
    {'id': 'cs_test_12345', 'status': 'unexpected', 'payment_status': 'paid'},
])
def test_stripe_rejects_inconsistent_response(response):
    with fake_client(lambda req: httpx.Response(200, json=response)) as client:
        with pytest.raises(ProviderProbeError):
            probe_stripe_checkout('cs_test_12345', 'sk_test_dummy', client=client)


def test_paypal_oauth_read_only_and_no_auto_settlement():
    def handler(request):
        if request.url.path.endswith('/oauth2/token'):
            assert request.method == 'POST'
            return httpx.Response(200, json={'access_token': 'private-token'})
        assert request.method == 'GET' and request.headers['Authorization'] == 'Bearer private-token'
        assert request.url.host == 'api-m.sandbox.paypal.com'
        return httpx.Response(200, json={'id': 'ORDER_12345', 'status': 'COMPLETED'})
    with fake_client(handler) as client:
        result = probe_paypal_order('ORDER_12345', 'client', 'secret', environment='sandbox', client=client)
    assert result['requires_capture_reconciliation'] and not result['authorizes_cutover']


def test_paypal_rejects_mismatched_reference():
    def handler(request):
        if request.method == 'POST':
            return httpx.Response(200, json={'access_token': 'token'})
        return httpx.Response(200, json={'id': 'OTHER_12345', 'status': 'COMPLETED'})
    with fake_client(handler) as client:
        with pytest.raises(ProviderProbeError):
            probe_paypal_order('ORDER_12345', 'client', 'secret', environment='sandbox', client=client)


def test_invalid_reference_never_calls_transport():
    def handler(request):
        raise AssertionError('Must not perform network request')
    with fake_client(handler) as client:
        with pytest.raises(ProviderProbeError):
            probe_stripe_checkout('https://attacker/path', 'sk_test_dummy', client=client)
        with pytest.raises(ProviderProbeError):
            probe_paypal_order('../escape', 'client', 'secret', environment='sandbox', client=client)
