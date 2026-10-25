"""Lost create response -> exact canonical ID binding, never another create."""
import copy
from concurrent.futures import ThreadPoolExecutor

import httpx
import pytest
from fastapi.testclient import TestClient
from app import auth,credit_purchases as stripe,paypal_payments as paypal,resource_accounts as resources
from app import checkout_reference_recovery as recovery,payment_reconcile_service as reconciliation
from app.regime_operation_fence import FenceBlocked
from test_r210_subscriptions import account as account,plan  # noqa: F401
from test_r210_paypal import provider as provider  # noqa: F401
from test_r210_credit_checkout import prepare
from test_r210_legal_documents import cookie


def unknown_stripe(account,monkeypatch):
    prepare(account,monkeypatch);posts=[]
    def create(*args):posts.append(1);raise ValueError('lost response after provider submission')
    monkeypatch.setattr(stripe,'_stripe',create)
    with pytest.raises(ValueError):stripe.checkout(account,500,'unknown-create-123')
    with auth.db() as c:local=c.execute("SELECT id FROM credit_purchase_orders WHERE request_id='unknown-create-123'").fetchone()[0]
    reference='cs_test_recovered_123'
    doc={'id':reference,'mode':'payment','status':'expired','payment_status':'unpaid','amount_total':500,'currency':'eur',
         'client_reference_id':local,'metadata':{'mta_order':local},'payment_intent':None,'url':None}
    def handle(request):
        assert request.method=='GET' and request.url.path=='/v1/checkout/sessions/'+reference
        assert request.headers['authorization']=='Bearer sk_test_test'
        return httpx.Response(200,json=copy.deepcopy(doc))
    return local,reference,doc,httpx.MockTransport(handle),posts


def test_lost_stripe_create_response_binds_then_terminal_readback_closes(account,monkeypatch):
    local,ref,_,mock,posts=unknown_stripe(account,monkeypatch)
    with httpx.Client(transport=mock) as client:
        first=recovery.recover('stripe',local,ref,client=client)
        assert first['reference_confirmed'] and not first['ledger_reconciled']
        assert recovery.recover('stripe',local,ref,client=client)['duplicate']
        assert reconciliation.reconcile_stripe(local,client=client)['checkout_closed']
        assert recovery.recover('stripe',local,ref,client=client)['duplicate']
    assert len(posts)==1 and resources.state(account)['credits_micro']==0
    with auth.db() as c:
        assert tuple(c.execute('SELECT state,attempts,provider_reference FROM regime_payment_outbox').fetchone())==('confirmed',1,ref)
        assert c.execute('SELECT status FROM credit_purchase_orders WHERE id=?',(local,)).fetchone()[0]=='cancelled'


@pytest.mark.parametrize('failure',['reference','owner','amount','currency','mode','config','local','epoch','drain','mirror','network','not_found','url'])
def test_invalid_or_changing_recovery_proof_keeps_uncertain_dispatch(account,monkeypatch,failure):
    local,ref,doc,mock,posts=unknown_stripe(account,monkeypatch)
    if failure=='reference':doc['id']='cs_test_other'
    if failure=='owner':doc['metadata']['mta_order']='other'
    if failure=='amount':doc['amount_total']=1
    if failure=='currency':doc['currency']='usd'
    if failure=='mode':doc['mode']='subscription'
    if failure=='url':doc['url']='https://evil.example/approval'
    if failure in ('epoch','drain'):
        with auth.db() as c:c.execute('UPDATE regime_fence_state SET revision=1' if failure=='epoch' else 'UPDATE regime_fence_state SET transitioning=1')
    if failure=='mirror':(auth.data_root()/'service-regime.json').write_text('{"regime":"NON_COMMERCIAL","revision":0}')
    original=mock.handler
    def handle(request):
        if failure=='network':raise httpx.ReadTimeout('fixture timeout')
        if failure=='not_found':return httpx.Response(404,json={'error':'missing'})
        result=original(request)
        if failure=='config':stripe.settings({'secret_key':'sk_test_changed'})
        if failure=='local':
            with auth.db() as c:c.execute('UPDATE credit_purchase_orders SET amount_cents=600 WHERE id=?',(local,))
        return result
    with httpx.Client(transport=httpx.MockTransport(handle)) as client,pytest.raises((ValueError,FenceBlocked)):
        recovery.recover('stripe',local,ref,client=client)
    with auth.db() as c:
        assert c.execute('SELECT session_id FROM credit_purchase_orders WHERE id=?',(local,)).fetchone()[0] is None
        assert tuple(c.execute('SELECT state,attempts,provider_reference FROM regime_payment_outbox').fetchone())==('uncertain',1,None)
    assert len(posts)==1


def test_concurrent_reference_binding_never_reposts_or_claims_payment(account,monkeypatch):
    local,ref,_,mock,posts=unknown_stripe(account,monkeypatch)
    def bind(_):
        with httpx.Client(transport=mock) as client:return recovery.recover('stripe',local,ref,client=client)
    with ThreadPoolExecutor(max_workers=4) as pool:results=list(pool.map(bind,range(4)))
    assert sum(not result['duplicate'] for result in results)==1 and len(posts)==1
    with auth.db() as c:
        assert c.execute('SELECT count(*) FROM payment_reconciliation_events').fetchone()[0]==1
        assert c.execute('SELECT status FROM regime_fence_operations WHERE operation_id=?',('checkout:stripe:'+local,)).fetchone()[0]=='open'


def unknown_paypal(account,provider,monkeypatch,*,body=None):
    if body is None:plan(account);body={'kind':'credits','amount_cents':500,'request_id':'unknown-paypal-123'}
    original=paypal._api
    def api(cfg,method,path,*args):
        result=original(cfg,method,path,*args)
        if method=='POST' and path=='/v2/checkout/orders':raise ValueError('lost PayPal create response')
        return result
    monkeypatch.setattr(paypal,'_api',api)
    with pytest.raises(ValueError):paypal.checkout(account,body)
    with auth.db() as c:local=c.execute('SELECT id FROM paypal_orders WHERE user_id=? AND request_id=?',(account,body['request_id'])).fetchone()[0]
    ref=list(provider[0])[-1];document=provider[0][ref];document['intent']='CAPTURE'
    return local,ref,document


def test_lost_paypal_creation_binds_and_owner_capture_funds_once(account,provider,monkeypatch):
    local,ref,_=unknown_paypal(account,provider,monkeypatch)
    assert recovery.recover('paypal',local,ref)['reference_confirmed']
    assert resources.state(account)['credits_micro']==0
    paypal.capture(account,local);assert recovery.recover('paypal',local,ref)['duplicate']
    assert resources.state(account)['credits_micro']==5_000_000
    assert len([call for call in provider[1] if call[0]=='POST' and call[1]=='/v2/checkout/orders'])==1


def test_legacy_provider_reference_cannot_be_bound_to_second_local_order(account,monkeypatch):
    local,ref,doc,mock,_=unknown_stripe(account,monkeypatch)
    with auth.db() as c:
        row=c.execute('SELECT * FROM credit_purchase_orders WHERE id=?',(local,)).fetchone()
        c.execute('INSERT INTO credit_purchase_orders(id,user_id,request_id,amount_cents,credit_value_micro,created_at,session_id) VALUES(?,?,?,?,?,?,?)',('legacy-other-order',account,'legacy-other-key',500,row['credit_value_micro'],1,ref))
    with httpx.Client(transport=mock) as client,pytest.raises(FenceBlocked):recovery.recover('stripe',local,ref,client=client)


def test_reference_recovery_endpoint_roles_csrf_and_shape(account,monkeypatch):
    from app import main
    monkeypatch.setattr(main,'NATIVE_SINGLE_USER',False);monkeypatch.setattr(main,'check_basic_auth',lambda request:False)
    monkeypatch.delenv('MTA_ALLOW_INSECURE_NO_AUTH',raising=False)
    local,ref,_,mock,_=unknown_stripe(account,monkeypatch)
    client=TestClient(main.app);url='/api/admin/service-regime/recover-checkout-reference';body={'provider':'stripe','order_id':local,'provider_reference':ref};headers={'X-MTA-Request':'1'}
    assert client.post(url,headers=headers,json=body).status_code==401
    client.cookies.update(cookie(account));assert client.post(url,headers=headers,json=body).status_code==403
    client.cookies.update(cookie(auth.find_user('admin')['id']));assert client.post(url,json=body).status_code==403
    assert client.post(url,headers=headers,json={**body,'amount':1}).status_code==422
    original=recovery.recover
    def recover(provider,order_id,reference):
        with httpx.Client(transport=mock) as remote:return original(provider,order_id,reference,client=remote)
    monkeypatch.setattr(recovery,'recover',recover)
    result=client.post(url,headers=headers,json=body);assert result.status_code==200,result.text
    assert not result.json()['ledger_reconciled'] and not result.json()['transition_authorized']
