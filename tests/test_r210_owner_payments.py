"""Private pending recovery and serialized fresh-ID admission; no live money."""
from concurrent.futures import ThreadPoolExecutor
import json

import httpx
import pytest
from fastapi.testclient import TestClient
from app import auth, owner_payments as owner, credit_purchases as stripe, paypal_payments as paypal
from app import payment_reconcile_service as service
from app.regime_operation_fence import FenceBlocked
from test_r210_subscriptions import account as account, plan  # noqa: F401
from test_r210_paypal import provider as provider  # noqa: F401
from test_r210_credit_checkout import prepare
from test_r210_terminal_checkout_e2e import stripe_fixture, assert_closed
from test_r210_legal_documents import cookie


def client(uid, monkeypatch):
    from app import main
    monkeypatch.setattr(main, 'NATIVE_SINGLE_USER', False)
    monkeypatch.setattr(main, 'check_basic_auth', lambda request: False)
    monkeypatch.delenv('MTA_ALLOW_INSECURE_NO_AUTH', raising=False)
    result = TestClient(main.app)
    if uid: result.cookies.update(cookie(uid))
    return result


def test_private_paginated_history_no_provider_or_credentials(account, provider, monkeypatch):
    prepare(account, monkeypatch)
    first = stripe.checkout(account, 500, 'first-stripe-request')
    data = owner.history(account, limit=1)
    assert data['credit_checkout_pending'] and data['scope'] == 'local_checkout_records'
    assert data['items'][0]['id'] == first['order_id']
    assert data['items'][0]['can_verify'] and data['items'][0]['checkout_url']
    assert owner.history(999)['items'] == []
    for private in ('session_id', 'provider_order', 'secret_key', 'test-client', 'request_id', 'sk_test'):
        assert private not in json.dumps(data)
    with auth.db() as c:
        c.execute("UPDATE credit_purchase_orders SET status='paid'")
    second = paypal.checkout(account, {'kind':'credits','amount_cents':500,'request_id':'second-paypal-request'})
    pages = [owner.history(account, offset=i, limit=1) for i in (0,1,2)]
    assert {row['id'] for page in pages for row in page['items']} == {first['order_id'], second['order_id']}
    assert pages[0]['next_offset'] == 1 and pages[1]['next_offset'] is None
    assert pages[1]['credit_checkout_pending']  # Hold is not limited to selected page.
    api = client(account, monkeypatch)
    assert api.get('/api/account/payments?limit=51').status_code == 422
    assert api.get('/api/account/payments?offset=-1').status_code == 422
    assert client(None, monkeypatch).get('/api/account/payments').status_code in (401,403)


@pytest.mark.parametrize('url', ['javascript:alert(1)','https://evil.test/pay','https://checkout.stripe.com@evil.test/',
    'https://user:pw@checkout.stripe.com/','https://checkout.stripe.com:444/', 'https://checkout.stripe.com\\@evil.test/',
    'https://checkout.stripe.com/\r\nBad', 'https://checkout.stripe.com:bad/'])
def test_legacy_resume_url_rejected(url):
    assert owner.safe_url(url,'stripe') is None


@pytest.mark.parametrize('first_provider',['stripe','paypal'])
def test_fresh_ids_and_other_provider_do_not_escape_pending(account,provider,monkeypatch,first_provider):
    calls = prepare(account,monkeypatch)
    if first_provider == 'stripe': original = stripe.checkout(account,500,'original-stripe-1')
    else: original = paypal.checkout(account,{'kind':'credits','amount_cents':500,'request_id':'original-paypal-1'})
    before = len(calls), len(provider[1])
    for invoke in (lambda:stripe.checkout(account,1000,'new-stripe-request'),
                   lambda:paypal.checkout(account,{'kind':'credits','amount_cents':500,'request_id':'new-paypal-request'})):
        with pytest.raises(FenceBlocked): invoke()
    assert before == (len(calls),len(provider[1]))
    if first_provider == 'stripe': assert stripe.checkout(account,500,'original-stripe-1') == original
    else: assert paypal.checkout(account,{'kind':'credits','amount_cents':500,'request_id':'original-paypal-1'}) == original
    assert before == (len(calls),len(provider[1]))


def test_unknown_creation_blocks_new_purchase_and_owner_probe(account,provider,monkeypatch):
    prepare(account,monkeypatch)
    def lost(*args):raise ValueError('response lost')
    monkeypatch.setattr(stripe,'_stripe',lost)
    with pytest.raises(ValueError):stripe.checkout(account,500,'lost-response-request')
    item = owner.history(account)['items'][0]
    assert item['needs_admin'] and not item['can_verify'] and item['checkout_url'] is None
    with pytest.raises(FenceBlocked):paypal.checkout(account,{'kind':'credits','amount_cents':500,'request_id':'fresh-paypal-request'})
    api = client(account,monkeypatch)
    assert api.post('/api/account/payments/stripe/'+item['id']+'/verify',headers={'X-MTA-Request':'1'},json={'confirm':True}).status_code == 409


def test_concurrent_cross_provider_new_ids_admit_only_one(account,provider,monkeypatch):
    prepare(account,monkeypatch)
    def purchase(index):
        try:
            if index%2:return stripe.checkout(account,500,'parallel-stripe-'+str(index))
            return paypal.checkout(account,{'kind':'credits','amount_cents':500,'request_id':'parallel-paypal-'+str(index)})
        except FenceBlocked:return None
    with ThreadPoolExecutor(max_workers=6) as pool: results=list(pool.map(purchase,range(6)))
    assert sum(result is not None for result in results)==1
    with auth.db() as c:
        assert c.execute('SELECT COUNT(*) FROM credit_purchase_orders').fetchone()[0]+c.execute('SELECT COUNT(*) FROM paypal_orders').fetchone()[0]==1


def test_owner_get_reconciliation_closes_terminal_and_releases_guard(account,monkeypatch):
    local,_,_,transport,calls = stripe_fixture(account,monkeypatch)
    api=client(account,monkeypatch)
    def reconcile(provider,order_id,*,expected_owner):
        assert provider=='stripe' and expected_owner==account
        with httpx.Client(transport=transport) as remote:
            return service.reconcile_stripe(order_id,client=remote,expected_owner=expected_owner)
    monkeypatch.setattr(service,'reconcile_checkout',reconcile)
    url='/api/account/payments/stripe/'+local+'/verify'
    assert api.post(url,json={'confirm':True}).status_code==403
    for body in ({},{'confirm':False},{'confirm':1},{'confirm':True,'observation':{}}):
        assert api.post(url,headers={'X-MTA-Request':'1'},json=body).status_code==422
    assert not calls
    assert api.post(url,headers={'X-MTA-Request':'1'},json={'confirm':True}).json()=={'verified':True}
    assert_closed(local,'stripe',account)
    assert not owner.history(account)['credit_checkout_pending']
    assert stripe.checkout(account,500,'new-after-confirmed-terminal')['checkout_url']


def test_wrong_owner_refused_before_any_provider_io(account,provider,monkeypatch):
    local,_,_,transport,calls=stripe_fixture(account,monkeypatch)
    with httpx.Client(transport=transport) as remote:
        with pytest.raises(ValueError):service.reconcile_stripe(local,client=remote,expected_owner=999)
    assert not calls
    with auth.db() as c:c.execute("UPDATE credit_purchase_orders SET status='paid'")
    order=paypal.checkout(account,{'kind':'credits','amount_cents':500,'request_id':'paypal-ownership-request'})
    before=len(provider[1])
    with pytest.raises(ValueError):service.reconcile_paypal(order['order_id'],expected_owner=999)
    assert len(provider[1])==before
    other=client(1,monkeypatch)
    assert other.post('/api/account/payments/paypal/'+order['order_id']+'/verify',headers={'X-MTA-Request':'1'},json={'confirm':True}).status_code==409
    assert len(provider[1])==before


def test_paypal_approved_verify_never_captures_and_preserves_hold(account,provider):
    plan(account)
    order=paypal.checkout(account,{'kind':'credits','amount_cents':500,'request_id':'approved-verify-request'})
    provider[0][next(iter(provider[0]))]['intent']='CAPTURE'
    before=len(provider[1])
    assert owner.verify(account,'paypal',order['order_id'])=={'verified':True}
    assert all(call[0]=='GET' for call in provider[1][before:])
    assert owner.history(account)['credit_checkout_pending']


def test_subscription_same_period_guard_and_readonly_nc_history(account,provider):
    state=plan(account,price_micro=5_000_000)
    body={'kind':'subscription','period_start':state['period']['start'],'request_id':'subscription-first'}
    first=paypal.checkout(account,body)
    with pytest.raises(FenceBlocked):paypal.checkout(account,{**body,'request_id':'subscription-second'})
    assert paypal.checkout(account,body)==first
    (auth.data_root()/'service-regime.json').write_text(json.dumps({'regime':'NON_COMMERCIAL','revision':0}))
    with auth.db() as c:c.execute("UPDATE regime_fence_state SET regime='NON_COMMERCIAL'")
    data=owner.history(account)
    assert data['items'][0]['kind']=='subscription'
    assert not data['commercial_payments'] and not data['items'][0]['can_verify'] and data['items'][0]['checkout_url'] is None


@pytest.mark.parametrize('change',['owner','credentials'])
def test_owner_probe_rejects_midflight_identity_change(account,monkeypatch,change):
    local,_,_,transport,_=stripe_fixture(account,monkeypatch)
    original=transport.handler
    changed=False
    def handle(request):
        nonlocal changed
        response=original(request)
        if not changed:
            changed=True
            with auth.db() as c:
                if change=='owner':c.execute('UPDATE credit_purchase_orders SET user_id=1 WHERE id=?',(local,))
                else:c.execute('UPDATE credit_payment_config SET secret_key=?',(auth._seal('sk_test_rotated'),))
        return response
    with httpx.Client(transport=httpx.MockTransport(handle)) as remote:
        with pytest.raises(FenceBlocked):service.reconcile_stripe(local,client=remote,expected_owner=account)
    with auth.db() as c:
        assert c.execute('SELECT status FROM credit_purchase_orders WHERE id=?',(local,)).fetchone()[0]=='pending'
        assert c.execute('SELECT status FROM regime_fence_operations').fetchone()[0]=='open'


@pytest.mark.parametrize('failure',['404','timeout'])
def test_failed_provider_lookup_keeps_pending_and_never_recreates(account,monkeypatch,failure):
    local,_,_,_,_=stripe_fixture(account,monkeypatch)
    def handle(request):
        assert request.method=='GET'
        if failure=='timeout':raise httpx.ReadTimeout('fixture timeout',request=request)
        return httpx.Response(404,json={})
    with httpx.Client(transport=httpx.MockTransport(handle)) as remote:
        with pytest.raises((ValueError,httpx.HTTPError)):service.reconcile_stripe(local,client=remote,expected_owner=account)
    assert owner.history(account)['credit_checkout_pending']
    with pytest.raises(FenceBlocked):stripe.checkout(account,500,'retry-after-failed-provider-lookup')


def test_owner_paid_and_refund_readback_is_net_and_idempotent(account,provider,monkeypatch):
    from test_r210_paypal_history_reconciliation import history_fixture
    from app import resource_accounts as resources
    local,_,_,calls=history_fixture(account,provider,monkeypatch)
    assert owner.verify(account,'paypal',local)=={'verified':True}
    assert resources.state(account)['credits_micro']==1_000_000
    assert owner.verify(account,'paypal',local)=={'verified':True}
    assert resources.state(account)['credits_micro']==1_000_000
    assert calls and not owner.history(account)['credit_checkout_pending']


@pytest.mark.parametrize('gateway',['stripe','paypal'])
@pytest.mark.parametrize('malformed',['credentials','port','control'])
def test_new_checkout_response_uses_same_strict_redirect_boundary(account,provider,monkeypatch,gateway,malformed):
    prepare(account,monkeypatch)
    host='checkout.stripe.com' if gateway=='stripe' else 'www.sandbox.paypal.com'
    target='https://'+('user:pw@' if malformed=='credentials' else '')+host+(':444' if malformed=='port' else '')+'/checkout'+('\r\nBad' if malformed=='control' else '')
    if gateway=='stripe':
        monkeypatch.setattr(stripe,'_stripe',lambda data,key,order:{'id':'cs_test_'+order,'url':target})
        invoke=lambda:stripe.checkout(account,500,'strict-provider-redirect')
    else:
        original=paypal._api
        def bad(cfg,method,path,*args):
            result=original(cfg,method,path,*args)
            assert method=='POST' and path=='/v2/checkout/orders'
            result['links'][0]['href']=target
            return result
        monkeypatch.setattr(paypal,'_api',bad)
        invoke=lambda:paypal.checkout(account,{'kind':'credits','amount_cents':500,'request_id':'strict-provider-redirect'})
    with pytest.raises(ValueError):invoke()
    data=owner.history(account)
    assert data['credit_checkout_pending'] and data['items'][0]['needs_admin']
    assert data['items'][0]['checkout_url'] is None
    with pytest.raises(FenceBlocked):stripe.checkout(account,500,'fresh-after-bad-redirect')


@pytest.mark.parametrize('gateway',['stripe','paypal'])
def test_valid_provider_redirect_is_stored_resumable_without_redispatch(account,provider,monkeypatch,gateway):
    calls=prepare(account,monkeypatch)
    if gateway=='stripe':invoke=lambda:stripe.checkout(account,500,'valid-redirect-request')
    else:invoke=lambda:paypal.checkout(account,{'kind':'credits','amount_cents':500,'request_id':'valid-redirect-request'})
    first=invoke();before=len(calls),len(provider[1]);assert invoke()==first
    assert (len(calls),len(provider[1]))==before
    item=owner.history(account)['items'][0]
    assert item['checkout_url']==first['checkout_url'] and item['can_verify'] and not item['needs_admin']
