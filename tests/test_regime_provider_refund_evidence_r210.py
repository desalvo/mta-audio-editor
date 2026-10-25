import httpx
import pytest

from app.regime_provider_probe import ProviderProbeError
from app.regime_provider_refund_evidence import inspect_stripe_charge, inspect_paypal_capture


def charge_payload():
    return {'object': 'charge', 'id': 'ch_12345', 'status': 'succeeded', 'paid': True,
            'captured': True, 'amount_refunded': 0, 'refunded': False,
            'disputed': False, 'refunds': {'object': 'list', 'has_more': False, 'data': []}}


def test_stripe_charge_read_only_and_non_authorizing():
    seen = []
    def handler(req):
        seen.append((req.method, req.url.path))
        return httpx.Response(200, json=charge_payload())
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = inspect_stripe_charge('ch_12345', 'sk_test_mock', client=client)
    assert seen == [('GET', '/v1/charges/ch_12345')]
    assert result['no_reversal_observed_at_lookup']
    assert not result['authorizes_cutover'] and not result['authorizes_entitlement']


@pytest.mark.parametrize('field,value', [
    ('amount_refunded', 1), ('amount_refunded', None), ('refunded', True),
    ('refunded', None), ('disputed', True), ('disputed', None),
    ('status', 'pending'), ('paid', False), ('captured', False),
])
def test_stripe_charge_bad_states_fail_closed(field, value):
    payload = charge_payload()
    payload[field] = value
    with httpx.Client(transport=httpx.MockTransport(lambda req: httpx.Response(200, json=payload))) as client:
        with pytest.raises(ProviderProbeError):
            inspect_stripe_charge('ch_12345', 'sk_test_mock', client=client)


@pytest.mark.parametrize('refunds', [None, {}, {'object':'list', 'has_more':True,'data':[]},
    {'object':'list','has_more':False,'data':[{'id':'re_1'}]}])
def test_stripe_incomplete_refund_evidence_blocked(refunds):
    payload = charge_payload()
    payload['refunds'] = refunds
    with httpx.Client(transport=httpx.MockTransport(lambda req: httpx.Response(200, json=payload))) as client:
        with pytest.raises(ProviderProbeError):
            inspect_stripe_charge('ch_12345', 'sk_test_mock', client=client)


def test_paypal_capture_status_does_not_certify_refund_absence():
    seen = []
    def handler(req):
        seen.append(req.url.path)
        return httpx.Response(200, json={'id':'CAPTURE123','status':'COMPLETED'})
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = inspect_paypal_capture('CAPTURE123', 'token', environment='sandbox', client=client)
    assert seen == ['/v2/payments/captures/CAPTURE123']
    assert result['refunds_and_disputes_verified'] is False
    assert result['authorizes_cutover'] is False


@pytest.mark.parametrize('status', ['REFUNDED','PARTIALLY_REFUNDED','PENDING',None])
def test_paypal_capture_noncomplete_is_rejected(status):
    with httpx.Client(transport=httpx.MockTransport(lambda req: httpx.Response(200, json={'id':'CAPTURE123','status':status}))) as client:
        with pytest.raises(ProviderProbeError):
            inspect_paypal_capture('CAPTURE123', 'token', environment='sandbox', client=client)
