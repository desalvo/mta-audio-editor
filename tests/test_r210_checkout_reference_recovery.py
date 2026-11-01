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
from test_r210_subscription_repayment_e2e import debt as debt,balance  # noqa: F401
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


@pytest.mark.parametrize('bad_identity',[False,True])
def test_paid_stripe_webhook_recovers_lost_reference_then_reconciles_refund(account,monkeypatch,bad_identity):
    from test_r210_credit_checkout import signed,paid_event
    local,ref,doc,_,posts=unknown_stripe(account,monkeypatch)
    doc.update(status='complete',payment_status='paid',payment_intent='pi_test',livemode=False)
    if bad_identity:doc['metadata']['mta_order']='different-order'
    intent={'id':'pi_test','status':'succeeded','amount':500,'amount_received':500,'amount_capturable':0,
            'currency':'eur','latest_charge':'ch_test','livemode':False}
    charge={'id':'ch_test','payment_intent':'pi_test','amount':500,'amount_captured':500,'currency':'eur',
            'status':'succeeded','paid':True,'captured':True,'amount_refunded':200,'refunded':False,
            'disputed':False,'balance_transaction':'txn_paid','failure_balance_transaction':None,'livemode':False}
    refund={'id':'re_test','charge':'ch_test','payment_intent':'pi_test','amount':200,'currency':'eur','status':'succeeded'}
    def handle(request):
        path=request.url.path
        if path=='/v1/checkout/sessions/'+ref:body=doc
        elif path=='/v1/payment_intents/pi_test':body=intent
        elif path=='/v1/charges/ch_test':body=charge
        elif path=='/v1/charges':body={'data':[charge],'has_more':False}
        elif path=='/v1/refunds/re_test':body=refund
        elif path=='/v1/refunds':body={'data':[refund],'has_more':False}
        elif path=='/v1/disputes':body={'data':[],'has_more':False}
        else:raise AssertionError(path)
        return httpx.Response(200,json=copy.deepcopy(body))
    monkeypatch.setattr(stripe,'_webhook_readback_client',lambda:httpx.Client(transport=httpx.MockTransport(handle)))
    event=paid_event(local);event['data']['object']['id']=ref
    if bad_identity:
        with pytest.raises(ValueError):stripe.event(*signed(event))
        assert resources.state(account)['credits_micro']==0
    else:
        assert stripe.event(*signed(event))['received']
        assert resources.state(account)['credits_micro']==3_000_000
    with auth.db() as c:
        state,reference=c.execute('SELECT state,provider_reference FROM regime_payment_outbox').fetchone()
        assert (state,reference)==(('uncertain',None) if bad_identity else ('confirmed',ref))
    assert len(posts)==1


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


def completed_paypal_webhook(reference,event_id='evt_lost_paypal_creation'):
    import json
    from test_r210_paypal_reconciliation_e2e import HEADERS
    payload={'id':event_id,'event_type':'PAYMENT.CAPTURE.COMPLETED',
             'resource':{'supplementary_data':{'related_ids':{'order_id':reference}}}}
    return paypal.webhook(json.dumps(payload).encode(),HEADERS)


@pytest.mark.parametrize('kind',['credits','subscription'])
def test_paypal_completed_webhook_recovers_lost_creation_and_settles_once(account,provider,monkeypatch,kind):
    body=None
    if kind=='subscription':
        state=plan(account,price_micro=5_000_000)
        body={'kind':'subscription','period_start':state['period']['start'],'request_id':'lost-subscription-create'}
    local,ref,_=unknown_paypal(account,provider,monkeypatch,body=body)
    paypal._api({},'POST','/v2/checkout/orders/'+ref+'/capture')
    assert completed_paypal_webhook(ref)=={'received':True}
    assert completed_paypal_webhook(ref)=={'received':True}
    with auth.db() as c:
        assert tuple(c.execute('SELECT provider_order,status FROM paypal_orders WHERE id=?',(local,)).fetchone())==(ref,'paid')
        assert tuple(c.execute('SELECT state,attempts,provider_reference FROM regime_payment_outbox WHERE operation_id=?',('checkout:paypal:'+local,)).fetchone())==('confirmed',1,ref)
        assert c.execute("SELECT count(*) FROM paypal_events WHERE id='evt_lost_paypal_creation'").fetchone()[0]==1
    assert resources.state(account)['credits_micro']==(5_000_000 if kind=='credits' else 0)
    if kind=='subscription':assert resources.transactions(account)['subscription_fees'][0]['status']=='paid'
    assert len([call for call in provider[1] if call[0]=='POST' and call[1]=='/v2/checkout/orders'])==1
    assert len([call for call in provider[1] if call[0]=='POST' and call[1].endswith('/capture')])==1


@pytest.mark.parametrize('defect',['custom_missing','custom_type','reference','invoice','amount','currency','intent','unpaid','units','unknown_local','config','drain','epoch','mirror','unattempted'])
def test_paypal_webhook_cannot_bind_unverified_lost_creation(account,provider,monkeypatch,defect):
    local,ref,document=unknown_paypal(account,provider,monkeypatch)
    paypal._api({},'POST','/v2/checkout/orders/'+ref+'/capture')
    unit=document['purchase_units'][0]
    if defect=='custom_missing':unit.pop('custom_id')
    if defect=='custom_type':unit['custom_id']=[]
    if defect=='reference':unit['reference_id']='different-order'
    if defect=='invoice':unit['invoice_id']='different-invoice'
    if defect=='amount':unit['amount']['value']='6.00'
    if defect=='currency':unit['amount']['currency_code']='USD'
    if defect=='intent':document['intent']='AUTHORIZE'
    if defect=='unpaid':document['status']='APPROVED'
    if defect=='units':document['purchase_units'].append(copy.deepcopy(unit))
    if defect=='unknown_local':unit['custom_id']=unit['reference_id']='unknown-local'
    if defect=='mirror':(auth.data_root()/'service-regime.json').write_text('{"regime":"NON_COMMERCIAL","revision":0}')
    with auth.db() as c:
        if defect=='drain':c.execute('UPDATE regime_fence_state SET transitioning=1')
        if defect=='epoch':c.execute('UPDATE regime_fence_state SET revision=1')
        if defect=='unattempted':c.execute('UPDATE regime_payment_outbox SET attempts=0')
    original=paypal._api
    def api(cfg,method,path,*args):
        value=original(cfg,method,path,*args)
        if defect=='config' and method=='GET' and path=='/v2/checkout/orders/'+ref:
            paypal.settings({'client_secret':'changed-after-webhook-verification'})
        return value
    monkeypatch.setattr(paypal,'_api',api)
    with pytest.raises((ValueError,FenceBlocked)):completed_paypal_webhook(ref)
    assert resources.state(account)['credits_micro']==0
    with auth.db() as c:
        assert c.execute('SELECT provider_order FROM paypal_orders WHERE id=?',(local,)).fetchone()[0] is None
        assert c.execute('SELECT state FROM regime_payment_outbox').fetchone()[0]=='uncertain'
        assert c.execute("SELECT 1 FROM paypal_events WHERE id='evt_lost_paypal_creation'").fetchone() is None
    assert len([call for call in provider[1] if call[0]=='POST' and call[1]=='/v2/checkout/orders'])==1


@pytest.mark.parametrize('incomplete',[False,True])
def test_lost_paypal_creation_replays_earlier_refund_without_gross_credit(account,provider,monkeypatch,incomplete):
    import json
    from test_r210_paypal_reconciliation_e2e import HEADERS
    local,ref,document=unknown_paypal(account,provider,monkeypatch)
    paypal._api({},'POST','/v2/checkout/orders/'+ref+'/capture')
    payments=document['purchase_units'][0]['payments'];capture=payments['captures'][0]
    capture['status']='PARTIALLY_REFUNDED'
    refund={'id':'REFUND999','status':'COMPLETED','amount':{'value':'2.00','currency_code':'EUR'},
            'seller_payable_breakdown':{'total_refunded_amount':{'value':'2.00','currency_code':'EUR'}},
            'links':[{'rel':'up','href':'https://api-m.sandbox.paypal.com/v2/payments/captures/'+capture['id']}]}
    payments['refunds']=[] if incomplete else [copy.deepcopy(refund)]
    original=paypal._api
    def api(cfg,method,path,*args):
        if method=='GET' and path=='/v2/payments/refunds/REFUND999':return copy.deepcopy(refund)
        return original(cfg,method,path,*args)
    monkeypatch.setattr(paypal,'_api',api)
    event={'id':'refund_before_lost_creation','event_type':'PAYMENT.CAPTURE.REFUNDED','resource':refund}
    assert paypal.webhook(json.dumps(event).encode(),HEADERS)['pending']
    if incomplete:
        with pytest.raises(ValueError,match='history is incomplete'):completed_paypal_webhook(ref)
        assert resources.state(account)['credits_micro']==0
        with auth.db() as c:
            assert tuple(c.execute('SELECT provider_order,status FROM paypal_orders WHERE id=?',(local,)).fetchone())==(ref,'pending')
            assert c.execute("SELECT 1 FROM paypal_events WHERE id='evt_lost_paypal_creation'").fetchone() is None
        payments['refunds']=[copy.deepcopy(refund)]
        assert reconciliation.reconcile_paypal(local)['ledger_reconciled']
    completed_paypal_webhook(ref);completed_paypal_webhook(ref)
    assert resources.state(account)['credits_micro']==3_000_000
    with auth.db() as c:
        assert c.execute('SELECT count(*) FROM paypal_refunds WHERE order_id=?',(local,)).fetchone()[0]==1
        assert c.execute("SELECT state FROM payment_reconciliation_events WHERE event_id='refund_before_lost_creation'").fetchone()[0]=='applied'


def test_lost_paypal_creation_preserves_earlier_capture_reversal(account,provider,monkeypatch):
    import json
    from test_r210_paypal_reconciliation_e2e import HEADERS
    local,ref,document=unknown_paypal(account,provider,monkeypatch)
    paypal._api({},'POST','/v2/checkout/orders/'+ref+'/capture')
    capture=document['purchase_units'][0]['payments']['captures'][0]
    event={'id':'reversal_before_lost_creation','event_type':'PAYMENT.CAPTURE.REVERSED',
           'resource':{'id':capture['id'],'amount':copy.deepcopy(capture['amount'])}}
    assert paypal.webhook(json.dumps(event).encode(),HEADERS)['pending']
    completed_paypal_webhook(ref);completed_paypal_webhook(ref)
    assert resources.state(account)['credits_micro']==0
    with auth.db() as c:
        assert c.execute('SELECT status FROM paypal_orders WHERE id=?',(local,)).fetchone()[0]=='paid'
        assert c.execute('SELECT held_minor FROM payment_reconciliation_positions WHERE order_id=?',(local,)).fetchone()[0]==500


def test_lost_paypal_creation_recovers_after_financial_transaction_rolls_back(account,provider,monkeypatch):
    from app import regime_checkout_fence
    local,ref,_=unknown_paypal(account,provider,monkeypatch)
    paypal._api({},'POST','/v2/checkout/orders/'+ref+'/capture')
    original=regime_checkout_fence.settle_if_enrolled
    def fail(*args):raise RuntimeError('Interrupted after staged credit')
    monkeypatch.setattr(regime_checkout_fence,'settle_if_enrolled',fail)
    with pytest.raises(RuntimeError,match='Interrupted after staged credit'):completed_paypal_webhook(ref)
    assert resources.state(account)['credits_micro']==0
    with auth.db() as c:
        assert tuple(c.execute('SELECT provider_order,status FROM paypal_orders WHERE id=?',(local,)).fetchone())==(ref,'pending')
        assert c.execute("SELECT 1 FROM paypal_events WHERE id='evt_lost_paypal_creation'").fetchone() is None
    monkeypatch.setattr(regime_checkout_fence,'settle_if_enrolled',original)
    completed_paypal_webhook(ref);completed_paypal_webhook(ref)
    assert resources.state(account)['credits_micro']==5_000_000
    assert len([call for call in provider[1] if call[0]=='POST' and call[1]=='/v2/checkout/orders'])==1


def test_concurrent_paypal_webhooks_recover_one_reference_and_one_credit(account,provider,monkeypatch):
    local,ref,_=unknown_paypal(account,provider,monkeypatch)
    paypal._api({},'POST','/v2/checkout/orders/'+ref+'/capture')
    with ThreadPoolExecutor(max_workers=4) as pool:
        results=list(pool.map(lambda _:completed_paypal_webhook(ref),range(8)))
    assert all(result=={'received':True} for result in results)
    assert resources.state(account)['credits_micro']==5_000_000
    with auth.db() as c:
        assert c.execute('SELECT count(*) FROM paypal_captures WHERE order_id=?',(local,)).fetchone()[0]==1
        assert c.execute("SELECT count(*) FROM paypal_events WHERE id='evt_lost_paypal_creation'").fetchone()[0]==1


def test_lost_paypal_repayment_creation_closes_original_debt_once(account,provider,debt,monkeypatch):
    fees=resources.transactions(account)['subscription_fees']
    body={'kind':'subscription_reversal','refund_id':'REFUND111','expected_due_micro':3_000_000,'request_id':'lost-repayment-creation'}
    local,ref,_=unknown_paypal(account,provider,monkeypatch,body=body)
    paypal._api({},'POST','/v2/checkout/orders/'+ref+'/capture')
    completed_paypal_webhook(ref);completed_paypal_webhook(ref)
    assert balance(account)['due_micro']==0
    assert resources.transactions(account)['subscription_fees']==fees
    assert resources.state(account)['credits_micro']==0
    with auth.db() as c:
        assert c.execute('SELECT count(*) FROM subscription_repayment_allocations WHERE order_id=?',(local,)).fetchone()[0]==1


def test_unverified_webhook_cannot_start_unknown_paypal_order_discovery(account,provider,monkeypatch):
    local,ref,_=unknown_paypal(account,provider,monkeypatch)
    paypal._api({},'POST','/v2/checkout/orders/'+ref+'/capture')
    original=paypal._api;reads=[]
    def api(cfg,method,path,*args):
        if path.endswith('/verify-webhook-signature'):return {'verification_status':'FAILURE'}
        if method=='GET':reads.append(path)
        return original(cfg,method,path,*args)
    monkeypatch.setattr(paypal,'_api',api)
    with pytest.raises(ValueError,match='Invalid PayPal signature'):completed_paypal_webhook(ref)
    assert not reads and resources.state(account)['credits_micro']==0
    with auth.db() as c:assert c.execute('SELECT provider_order FROM paypal_orders WHERE id=?',(local,)).fetchone()[0] is None


def test_http_webhook_recovers_lost_paypal_creation_after_credit_service_disabled(account,provider,monkeypatch):
    import json
    from app import main
    from test_r210_paypal_reconciliation_e2e import HEADERS
    local,ref,_=unknown_paypal(account,provider,monkeypatch)
    paypal._api({},'POST','/v2/checkout/orders/'+ref+'/capture')
    resources.configure({'credits_enabled':False});paypal.settings({'enabled':False})
    monkeypatch.setattr(main,'NATIVE_SINGLE_USER',False);monkeypatch.setattr(main,'check_basic_auth',lambda _:False)
    monkeypatch.delenv('MTA_ALLOW_INSECURE_NO_AUTH',raising=False)
    payload={'id':'http-lost-payment-completed','event_type':'PAYMENT.CAPTURE.COMPLETED',
             'resource':{'supplementary_data':{'related_ids':{'order_id':ref}}}}
    web=TestClient(main.app)
    for _ in range(2):
        response=web.post('/api/billing/paypal/webhook',content=json.dumps(payload).encode(),headers=HEADERS)
        assert response.status_code==200,response.text
    assert resources.state(account)['credits_micro']==5_000_000
    with auth.db() as c:assert c.execute('SELECT status FROM paypal_orders WHERE id=?',(local,)).fetchone()[0]=='paid'


@pytest.mark.timeout(20)
def test_killed_paypal_webhook_can_resume_after_reference_binding(account,provider,monkeypatch):
    import os
    import signal
    from app import regime_checkout_fence
    if not hasattr(os,'fork'):pytest.skip('Real process interruption requires POSIX fork')
    local,ref,_=unknown_paypal(account,provider,monkeypatch)
    paypal._api({},'POST','/v2/checkout/orders/'+ref+'/capture')
    original=regime_checkout_fence.settle_if_enrolled
    def kill_after_staged_credit(*args):os.kill(os.getpid(),signal.SIGKILL)
    monkeypatch.setattr(regime_checkout_fence,'settle_if_enrolled',kill_after_staged_credit)
    pid=os.fork()
    if pid==0:
        signal.alarm(10)
        try:completed_paypal_webhook(ref)
        except BaseException:os._exit(3)
        os._exit(4)
    _,status=os.waitpid(pid,0)
    assert os.WIFSIGNALED(status) and os.WTERMSIG(status)==signal.SIGKILL
    assert resources.state(account)['credits_micro']==0
    with auth.db() as c:
        assert tuple(c.execute('SELECT provider_order,status FROM paypal_orders WHERE id=?',(local,)).fetchone())==(ref,'pending')
        assert c.execute("SELECT 1 FROM paypal_events WHERE id='evt_lost_paypal_creation'").fetchone() is None
    monkeypatch.setattr(regime_checkout_fence,'settle_if_enrolled',original)
    completed_paypal_webhook(ref);completed_paypal_webhook(ref)
    assert resources.state(account)['credits_micro']==5_000_000


def test_lost_paypal_creation_binds_and_owner_capture_funds_once(account,provider,monkeypatch):
    local,ref,_=unknown_paypal(account,provider,monkeypatch)
    assert recovery.recover('paypal',local,ref)['reference_confirmed']
    assert resources.state(account)['credits_micro']==0
    paypal.capture(account,local);assert recovery.recover('paypal',local,ref)['duplicate']
    assert resources.state(account)['credits_micro']==5_000_000
    assert len([call for call in provider[1] if call[0]=='POST' and call[1]=='/v2/checkout/orders'])==1


@pytest.mark.parametrize('links', [None, 'bad', {}, [None], ['bad'],
    [{'rel':'approve','href':'https://www.sandbox.paypal.com/ok'}, {'rel':'payer-action','href':'https://www.sandbox.paypal.com/other'}],
    [{'rel':'approve','href':'https://attacker.example/'}],
    [{'rel':'approve','href':'https://www.sandbox.paypal.com:444/'}],
    [{'rel':'approve','href':'https://user@www.sandbox.paypal.com/'}],
    [{'rel':'approve','href':'https://www.sandbox.paypal.com/\npath'}],
    [{'rel':'approve','href':42}], [{'rel':'approve','href':''}], [{'rel':'approve'}], [{'rel':'approve','href':None}]])
def test_paypal_recovery_rejects_malformed_or_ambiguous_links_without_binding(account,provider,monkeypatch,links):
    local,ref,doc=unknown_paypal(account,provider,monkeypatch)
    doc['links']=links
    with pytest.raises(recovery.ProviderProbeError):
        recovery.recover('paypal',local,ref)
    with auth.db() as c:
        assert c.execute('SELECT provider_order FROM paypal_orders WHERE id=?',(local,)).fetchone()[0] is None
        assert tuple(c.execute('SELECT state,attempts,provider_reference FROM regime_payment_outbox').fetchone())==('uncertain',1,None)
    assert len([x for x in provider[1] if x[0]=='POST' and x[1]=='/v2/checkout/orders'])==1


@pytest.mark.parametrize('links', [[], [{'rel':'self','href':'https://api.example.test/order'}]])
def test_paypal_recovery_can_bind_without_approval_link(account,provider,monkeypatch,links):
    local,ref,doc=unknown_paypal(account,provider,monkeypatch)
    doc['links']=links
    assert recovery.recover('paypal',local,ref)['reference_confirmed']
    with auth.db() as c:
        row=c.execute('SELECT provider_order,checkout_url FROM paypal_orders WHERE id=?',(local,)).fetchone()
        assert tuple(row)==(ref,None)


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
