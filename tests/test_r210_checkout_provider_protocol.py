"""Actual HTTP adapters reject malformed JSON without repeat dispatch."""
import json
import httpx
import pytest

from app import credit_purchases as stripe, paypal_payments as paypal


@pytest.mark.parametrize('payload', [None, [], 'wrong', 1, True])
def test_stripe_http_non_object_response_is_rejected(monkeypatch, payload):
    calls=[]
    client=httpx.Client
    def handle(request):
        calls.append(request)
        return httpx.Response(200,content=json.dumps(payload))
    monkeypatch.setattr(httpx, 'Client', lambda **kwargs: client(transport=httpx.MockTransport(handle),**kwargs))
    with pytest.raises(ValueError,match='Invalid checkout response'):
        stripe._stripe({},'sk_test_dummy','protocol-order')
    assert len(calls)==1 and calls[0].headers['idempotency-key']=='mta-credits-protocol-order'


@pytest.mark.parametrize('phase', ['token','result'])
@pytest.mark.parametrize('payload', [None, [], 'wrong', 1, True])
def test_paypal_http_non_object_response_is_rejected(monkeypatch, phase, payload):
    calls=[]
    client=httpx.Client
    def handle(request):
        calls.append(request)
        if request.url.path=='/v1/oauth2/token':
            return httpx.Response(200,content=json.dumps(payload if phase=='token' else {'access_token':'temporary'}))
        return httpx.Response(201,content=json.dumps(payload))
    monkeypatch.setattr(httpx,'Client',lambda **kwargs: client(transport=httpx.MockTransport(handle),**kwargs))
    cfg={'enabled':True,'environment':'sandbox','client_id':'example','client_secret':'example'}
    with pytest.raises(ValueError,match='Invalid PayPal'):
        paypal._api(cfg,'POST','/v2/checkout/orders',{},'protocol-order')
    assert len(calls)==(1 if phase=='token' else 2)
    if phase=='result':assert calls[-1].headers['paypal-request-id']=='protocol-order'


@pytest.mark.parametrize('phase', ['stripe','token','result'])
def test_http_invalid_json_is_reported_without_retry(monkeypatch,phase):
    calls=[]
    client=httpx.Client
    def handle(request):
        calls.append(request)
        if phase=='result' and request.url.path=='/v1/oauth2/token':
            return httpx.Response(200,json={'access_token':'temporary'})
        return httpx.Response(200,content=b'not-json')
    monkeypatch.setattr(httpx,'Client',lambda **kwargs: client(transport=httpx.MockTransport(handle),**kwargs))
    with pytest.raises(ValueError,match='Invalid (checkout|PayPal)'):
        if phase=='stripe':stripe._stripe({},'sk_test_dummy','protocol-order')
        else:paypal._api({'enabled':True,'environment':'sandbox','client_id':'example','client_secret':'example'},
                         'POST','/v2/checkout/orders',{},'protocol-order')
    assert len(calls)==(2 if phase=='result' else 1)
