"""Server-side PayPal quotes/capture/webhook security without moving real money."""
import copy
import json
import pytest
from app import auth,resource_accounts as r,paypal_payments as paypal
from test_r210_subscriptions import account as account,plan  # noqa: F401


@pytest.fixture
def provider(account,monkeypatch):
    from app import legal
    regime_file = auth.data_root() / 'service-regime.json'
    regime_file.write_text(json.dumps({'regime':'COMMERCIAL','revision':0}))
    legal.save({'operator_name':'Test','operator_country':'Italy','support_email':'support@example.test','public_url':'https://mta.example.test','effective_date':'2026-10-19'},1)
    paypal.settings({'enabled':True,'environment':'sandbox','client_id':'test-client','client_secret':'test-secret','webhook_id':'test-webhook'})
    orders={};calls=[]
    def api(config,method,path,payload=None,request_id=None):
        calls.append((method,path,payload,request_id))
        if path=='/v2/checkout/orders':
            identifier='ORDER000'+str(len(orders)+1)
            orders[identifier]={'id':identifier,'status':'APPROVED','purchase_units':copy.deepcopy(payload['purchase_units'])}
            return {'id':identifier,'links':[{'rel':'payer-action','href':'https://www.sandbox.paypal.com/checkoutnow?token='+identifier}]}
        if path.endswith('/capture'):
            identifier=path.split('/')[-2];order=orders[identifier];order['status']='COMPLETED'
            order['purchase_units'][0]['payments']={'captures':[{'id':'CAPTURE'+identifier,'status':'COMPLETED','amount':copy.deepcopy(order['purchase_units'][0]['amount'])}]}
            return order
        if method=='GET' and path.startswith('/v1/customer/disputes?'):return {'items':[],'links':[]}
        if method=='GET' and path.startswith('/v2/payments/captures/'):
            return copy.deepcopy(next(x for order in orders.values() for x in order.get('purchase_units',[{}])[0].get('payments',{}).get('captures',[]) if x['id']==path.rsplit('/',1)[1]))
        if method=='GET':return copy.deepcopy(orders[path.split('/')[-1]])
        if path.endswith('/verify-webhook-signature'):return {'verification_status':'SUCCESS'}
        raise AssertionError((method,path))
    monkeypatch.setattr(paypal,'_api',api)
    return orders,calls


def test_settings_sealed_and_no_secret_disclosure(provider):
    result=paypal.settings();assert result['configured'] and result['environment']=='sandbox'
    assert 'test-client' not in json.dumps(result) and 'test-secret' not in json.dumps(result)
    with auth.db() as c:assert 'test-secret' not in c.execute('SELECT client_secret FROM paypal_config').fetchone()[0]
    with pytest.raises(ValueError):paypal.settings({'environment':'https://evil.test'})


def test_credit_checkout_capture_and_retries_only_credit_once(account,provider):
    plan(account);orders,calls=provider
    body={'kind':'credits','amount_cents':500,'request_id':'paypal-purchase-123'}
    order=paypal.checkout(account,body)
    assert order==paypal.checkout(account,body) and len(orders)==1
    assert r.state(account)['credits_micro']==0
    assert paypal.capture(account,order['order_id'])['status']=='paid'
    paypal.capture(account,order['order_id'])
    assert r.state(account)['credits_micro']==5_000_000
    capture_calls=[c for c in calls if c[1].endswith('/capture')]
    assert len(capture_calls)==1 and capture_calls[0][3].startswith('mta-capture-')


def test_checkout_requires_eligible_subscription(account,provider):
    with pytest.raises(ValueError):paypal.checkout(account,{'kind':'credits','amount_cents':500,'request_id':'no-plan-credit-request'})
    plan(account);r.configure({'credits_enabled':False})
    with pytest.raises(ValueError):paypal.checkout(account,{'kind':'credits','amount_cents':500,'request_id':'disabled-credit-request'})


def test_subscription_payment_settles_fee_without_adding_overage_credits(account,provider):
    before=plan(account,price_micro=5_000_000)
    order=paypal.checkout(account,{'kind':'subscription','period_start':before['period']['start'],'request_id':'subscription-pay-123'})
    paypal.capture(account,order['order_id'])
    assert r.state(account)['credits_micro']==0
    assert r.transactions(account)['subscription_fees'][0]['status']=='paid'


def test_capture_wrong_owner_amount_currency_identity_and_unpaid_are_refused(account,provider):
    plan(account);orders,_=provider
    order=paypal.checkout(account,{'kind':'credits','amount_cents':500,'request_id':'tampered-checkout-123'})
    with pytest.raises(ValueError):paypal.capture(999,order['order_id'])
    pid=next(iter(orders));approved=copy.deepcopy(orders[pid])
    with pytest.raises(ValueError):paypal.fulfill(order['order_id'],approved)
    orders[pid]['status']='COMPLETED';unit=orders[pid]['purchase_units'][0]
    unit['payments']={'captures':[{'id':'CAPTURE123','status':'COMPLETED','amount':{'value':'5.00','currency_code':'EUR'}}]}
    for field,value in [('custom_id','wrong'),('amount',{'value':'5.00','currency_code':'USD'}),('amount',{'value':'50.00','currency_code':'EUR'})]:
        bad=copy.deepcopy(orders[pid]);bad['purchase_units'][0][field]=value
        with pytest.raises(ValueError):paypal.fulfill(order['order_id'],bad)
    assert r.state(account)['credits_micro']==0
    paypal.fulfill(order['order_id'],orders[pid]);assert r.state(account)['credits_micro']==5_000_000


def test_webhook_signature_verified_and_canonical_order_fetched(account,provider,monkeypatch):
    plan(account);orders,calls=provider
    paypal.checkout(account,{'kind':'credits','amount_cents':500,'request_id':'webhook-payment-123'})
    pid=next(iter(orders));provider_api=paypal._api
    provider_api({},'POST','/v2/checkout/orders/'+pid+'/capture')
    payload={'id':'event-123','event_type':'PAYMENT.CAPTURE.COMPLETED','resource':{'supplementary_data':{'related_ids':{'order_id':pid}}}}
    raw=json.dumps(payload).encode();headers={k:'test' for k in ['paypal-auth-algo','paypal-cert-url','paypal-transmission-id','paypal-transmission-sig','paypal-transmission-time']}
    with pytest.raises(ValueError):paypal.webhook(raw,{})
    def bad_verify(cfg,method,path,*args):
        if path.endswith('verify-webhook-signature'):return {'verification_status':'FAILURE'}
        return provider_api(cfg,method,path,*args)
    monkeypatch.setattr(paypal,'_api',bad_verify)
    with pytest.raises(ValueError):paypal.webhook(raw,headers)
    assert r.state(account)['credits_micro']==0
    monkeypatch.setattr(paypal,'_api',provider_api)
    paypal.webhook(raw,headers);paypal.webhook(raw,headers)
    assert r.state(account)['credits_micro']==5_000_000
    assert any(c[0]=='GET' and c[1].endswith(pid) for c in calls)


def test_untrusted_approval_url_and_denomination_refused(account,provider,monkeypatch):
    plan(account)
    with pytest.raises(ValueError):paypal.checkout(account,{'kind':'credits','amount_cents':1,'request_id':'bad-amount-request'})
    monkeypatch.setattr(paypal,'_api',lambda *a:{'id':'ORDER123','links':[{'rel':'approve','href':'https://evil.test/'}]})
    with pytest.raises(ValueError,match='approval URL'):paypal.checkout(account,{'kind':'credits','amount_cents':500,'request_id':'bad-url-request-123'})


def test_authenticated_refund_reverses_credits_once(account,provider,monkeypatch):
    plan(account);orders,_=provider
    order=paypal.checkout(account,{'kind':'credits','amount_cents':500,'request_id':'refundable-payment-123'})
    paypal.capture(account,order['order_id']);pid=next(iter(orders));capture_id=orders[pid]['purchase_units'][0]['payments']['captures'][0]['id']
    original=paypal._api
    def api(cfg,method,path,*args):
        if path=='/v2/payments/refunds/REFUND123':return {'id':'REFUND123','status':'COMPLETED','amount':{'value':'2.00','currency_code':'EUR'},'links':[{'rel':'up','href':'https://api-m.sandbox.paypal.com/v2/payments/captures/'+capture_id}]}
        return original(cfg,method,path,*args)
    monkeypatch.setattr(paypal,'_api',api)
    payload={'id':'refund-event-123','event_type':'PAYMENT.CAPTURE.REFUNDED','resource':{'id':'REFUND123','links':[{'rel':'up','href':'https://api-m.sandbox.paypal.com/v2/payments/captures/'+capture_id}]}}
    headers={k:'test' for k in ['paypal-auth-algo','paypal-cert-url','paypal-transmission-id','paypal-transmission-sig','paypal-transmission-time']}
    paypal.webhook(json.dumps(payload).encode(),headers);paypal.webhook(json.dumps(payload).encode(),headers)
    assert r.state(account)['credits_micro']==3_000_000


def test_http_roles_csrf_and_unsigned_webhook_are_enforced(account,provider,monkeypatch):
    from fastapi.testclient import TestClient
    from app import main
    from test_r210_legal_documents import cookie
    monkeypatch.setattr(main,'NATIVE_SINGLE_USER',False);monkeypatch.setattr(main,'check_basic_auth',lambda request:False)
    monkeypatch.delenv('MTA_ALLOW_INSECURE_NO_AUTH',raising=False)
    client=TestClient(main.app);client.cookies.update(cookie(account));headers={'X-MTA-Request':'1'}
    assert client.get('/api/admin/paypal').status_code==403
    assert client.post('/api/admin/subscriptions/users/'+str(account)+'/terminate',json={'reason':'test','request_id':'terminate-api-123'},headers=headers).status_code==403
    assert client.post('/api/billing/paypal/webhook',json={'id':'forged'}).status_code==400
    client.cookies.update(cookie(auth.find_user('admin')['id']))
    assert client.put('/api/admin/paypal',json={'enabled':True}).status_code==403
    assert client.get('/api/admin/paypal').status_code==200
    assert client.post('/api/admin/optional-vst3/install',json={'plugins':['mverb'],'accept_licenses':False},headers=headers).status_code==422


def test_prorated_subscription_fee_remains_payable_after_termination(account,provider,monkeypatch):
    from app import resource_contracts,ai_billing
    clock=[1802822400];monkeypatch.setattr(r.time,'time',lambda:clock[0])
    state=plan(account,price_micro=8_640_000);ai_billing.set_user_billing_enabled(account,True)
    clock[0]+=3600
    resource_contracts.terminate(account,{'reason':'Ended by operator','request_id':'ended-to-pay-123'},1)
    order=paypal.checkout(account,{'kind':'subscription','period_start':state['period']['start'],'request_id':'pay-prorated-123'})
    paypal.capture(account,order['order_id'])
    assert r.transactions(account)['subscription_fees'][0]['status']=='paid'
    assert r.state(account)['credits_micro']==0


def test_webhook_event_and_fulfillment_share_atomic_commit(account, provider, monkeypatch):
    """A failure after credits are staged must roll back both money and event."""
    plan(account)
    orders, _ = provider
    local = paypal.checkout(account, {'kind': 'credits', 'amount_cents': 500,
                                       'request_id': 'webhook-atomic-rollback-123'})
    pid = next(iter(orders))
    paypal._api({}, 'POST', '/v2/checkout/orders/' + pid + '/capture')
    payload = {'id': 'atomic-event-123', 'event_type': 'PAYMENT.CAPTURE.COMPLETED',
               'resource': {'supplementary_data': {'related_ids': {'order_id': pid}}}}
    headers = {k: 'test' for k in ['paypal-auth-algo', 'paypal-cert-url',
               'paypal-transmission-id', 'paypal-transmission-sig',
               'paypal-transmission-time']}
    from app import regime_checkout_fence
    original = regime_checkout_fence.settle_if_enrolled
    def fail_after_mutation(*args, **kwargs):
        raise RuntimeError('simulated failure before commit')
    monkeypatch.setattr(regime_checkout_fence, 'settle_if_enrolled', fail_after_mutation)
    with pytest.raises(RuntimeError, match='simulated failure'):
        paypal.webhook(json.dumps(payload).encode(), headers)
    with auth.db() as c:
        assert c.execute('SELECT 1 FROM paypal_events WHERE id=?', (payload['id'],)).fetchone() is None
        assert c.execute('SELECT status FROM paypal_orders WHERE id=?', (local['order_id'],)).fetchone()[0] == 'pending'
    assert r.state(account)['credits_micro'] == 0
    monkeypatch.setattr(regime_checkout_fence, 'settle_if_enrolled', original)
    paypal.webhook(json.dumps(payload).encode(), headers)
    paypal.webhook(json.dumps(payload).encode(), headers)
    assert r.state(account)['credits_micro'] == 5_000_000
    with auth.db() as c:
        assert c.execute('SELECT COUNT(*) FROM paypal_events WHERE id=?', (payload['id'],)).fetchone()[0] == 1


def test_paypal_outbox_confirmed_on_provider_acceptance(account, provider):
    plan(account)
    order = paypal.checkout(account, {'kind':'credits','amount_cents':500,'request_id':'paypal-outbox-success-123'})
    with auth.db() as c:
        row = c.execute('SELECT state,attempts,provider_reference FROM regime_payment_outbox WHERE operation_id=?',
                        ('checkout:paypal:'+order['order_id'],)).fetchone()
        assert tuple(row) == ('confirmed', 1, next(iter(provider[0])))


def test_paypal_uncertain_provider_failure_requires_reconciliation(account, provider, monkeypatch):
    plan(account)
    calls=[]
    def unavailable(*args, **kwargs):
        calls.append(1)
        raise ValueError('outcome uncertain')
    monkeypatch.setattr(paypal,'_api',unavailable)
    request = {'kind':'credits','amount_cents':500,'request_id':'paypal-outbox-failure-123'}
    with pytest.raises(ValueError, match='uncertain'):
        paypal.checkout(account, request)
    with pytest.raises(Exception):
        paypal.checkout(account, request)
    assert len(calls) == 1
    with auth.db() as c:
        row = c.execute('SELECT state,attempts FROM regime_payment_outbox').fetchone()
        assert tuple(row) == ('uncertain', 1)
