"""Authenticated unpaid terminal proof -> atomic order/fence/journal closure."""
import copy
from concurrent.futures import ThreadPoolExecutor

import httpx
import pytest
from app import auth,credit_purchases as stripe,paypal_payments as paypal,resource_accounts as resources
from app import payment_reconcile_service as service,payment_reconciliation as journal
from app.regime_operation_fence import FenceBlocked
from test_r210_subscriptions import account as account,plan  # noqa: F401
from test_r210_paypal import provider as provider  # noqa: F401
from test_r210_payment_reconciliation_e2e import purchase
from test_r210_credit_checkout import signed,paid_event


def stripe_fixture(account,monkeypatch,*,intent=False):
    local=purchase(account,monkeypatch)
    session={'id':'cs_test_'+local,'mode':'payment','status':'expired','payment_status':'unpaid',
             'amount_total':500,'currency':'eur','client_reference_id':local,'metadata':{'mta_order':local},
             'payment_intent':'pi_terminal' if intent else None}
    pi={'id':'pi_terminal','status':'canceled','amount':500,'currency':'eur','amount_received':0,'amount_capturable':0,'latest_charge':None}
    calls=[]
    def handle(request):
        assert request.method=='GET' and request.headers['authorization']=='Bearer sk_test_test'
        path=request.url.path;calls.append(path)
        if path.endswith(session['id']):obj=session
        elif path.endswith('/pi_terminal'):obj=pi
        elif path.endswith('/charges'):obj={'data':[],'has_more':False}
        else:raise AssertionError(path)
        return httpx.Response(200,json=copy.deepcopy(obj))
    return local,session,pi,httpx.MockTransport(handle),calls


def assert_closed(local,provider,uid):
    with auth.db() as c:
        if provider=='stripe':row=c.execute('SELECT status,paid_at,checkout_url FROM credit_purchase_orders WHERE id=?',(local,)).fetchone()
        else:row=c.execute('SELECT status,paid_at,checkout_url FROM paypal_orders WHERE id=?',(local,)).fetchone()
        assert tuple(row)==('cancelled',None,None)
        assert c.execute('SELECT status FROM regime_fence_operations WHERE operation_id=?',('checkout:'+provider+':'+local,)).fetchone()[0]=='closed'
        assert tuple(c.execute('SELECT state,attempts FROM regime_payment_outbox WHERE operation_id=?',('checkout:'+provider+':'+local,)).fetchone())==('confirmed',1)
        report=journal.report(c);assert report['verified'] and report['pending']==0
        assert report['positions'][0]['funded']==0 and report['positions'][0]['net_micro']==0
    assert resources.state(uid)['credits_micro']==0


@pytest.mark.parametrize('intent',[False,True])
def test_stripe_expired_checkout_readback_closes_exactly_once(account,monkeypatch,intent):
    local,_,_,mock,calls=stripe_fixture(account,monkeypatch,intent=intent)
    with httpx.Client(transport=mock) as client:
        first=service.reconcile_stripe(local,client=client)
        again=service.reconcile_stripe(local,client=client)
    assert first['checkout_closed'] and again['duplicate'] and first['outcome']=='expired'
    assert_closed(local,'stripe',account)
    assert len(calls)==(8 if intent else 4)
    assert stripe.checkout(account,500,'reconciliation-e2e-123')=={'status':'cancelled','order_id':local}


def test_canceled_intent_after_async_failure_resolves_pending_signed_event(account,monkeypatch):
    local,session,_,mock,_=stripe_fixture(account,monkeypatch,intent=True);session['status']='complete'
    event={'id':'evt_async_failed','type':'checkout.session.async_payment_failed','data':{'object':copy.deepcopy(session)}}
    assert stripe.event(*signed(event))['pending']
    with httpx.Client(transport=mock) as client:assert service.reconcile_stripe(local,client=client)['outcome']=='canceled_intent'
    assert_closed(local,'stripe',account)


def test_signed_expiration_without_intent_closes_without_network(account,monkeypatch):
    local,session,_,_,_=stripe_fixture(account,monkeypatch)
    event={'id':'evt_expired','type':'checkout.session.expired','data':{'object':session}}
    assert stripe.event(*signed(event))['checkout_closed']
    assert stripe.event(*signed(event))['duplicate']
    assert_closed(local,'stripe',account)


@pytest.mark.parametrize('state',['requires_payment_method','processing','requires_capture'])
def test_nonterminal_failed_or_processing_intent_stays_open(account,monkeypatch,state):
    local,session,pi,mock,_=stripe_fixture(account,monkeypatch,intent=True);session['status']='complete';pi['status']=state
    with httpx.Client(transport=mock) as client:result=service.reconcile_stripe(local,client=client)
    assert result['status']=='pending' and not result['checkout_closed'] and not result['ledger_reconciled']
    with auth.db() as c:assert c.execute('SELECT status FROM regime_fence_operations WHERE operation_id=?',('checkout:stripe:'+local,)).fetchone()[0]=='open'


@pytest.mark.parametrize('failure',['wrong_id','wrong_owner','wrong_amount','wrong_currency','paid','wrong_mode','missing_intent','captured','charge','changed','config','epoch','drain','mirror'])
def test_stripe_terminal_proof_fails_closed(account,monkeypatch,failure):
    local,session,pi,mock,_=stripe_fixture(account,monkeypatch,intent=failure in ('captured','charge'))
    if failure=='wrong_id':session['id']='cs_other'
    if failure=='wrong_owner':session['client_reference_id']='other'
    if failure=='wrong_amount':session['amount_total']=1
    if failure=='wrong_currency':session['currency']='usd'
    if failure=='paid':session['payment_status']='paid'
    if failure=='wrong_mode':session['mode']='subscription'
    if failure=='missing_intent':session.pop('payment_intent')
    if failure=='captured':pi['amount_received']=1
    if failure=='charge':pi['latest_charge']='ch_failed'
    if failure in ('epoch','drain'):
        with auth.db() as c:c.execute('UPDATE regime_fence_state SET revision=1' if failure=='epoch' else 'UPDATE regime_fence_state SET transitioning=1')
    if failure=='mirror':(auth.data_root()/'service-regime.json').write_text('{"regime":"NON_COMMERCIAL","revision":0}')
    if failure in ('changed','config'):
        original=mock.handler;count=[]
        def handle(request):
            result=original(request);count.append(1)
            if len(count)==2:
                if failure=='changed':return httpx.Response(200,json={**session,'status':'open'})
                stripe.settings({'secret_key':'sk_test_rotated'})
            return result
        mock=httpx.MockTransport(handle)
    with httpx.Client(transport=mock) as client,pytest.raises((ValueError,FenceBlocked,AssertionError)):service.reconcile_stripe(local,client=client)
    with auth.db() as c:
        assert c.execute('SELECT status FROM credit_purchase_orders WHERE id=?',(local,)).fetchone()[0]=='pending'
        assert c.execute('SELECT status FROM regime_fence_operations WHERE operation_id=?',('checkout:stripe:'+local,)).fetchone()[0]=='open'
    assert resources.state(account)['credits_micro']==0


def test_terminal_transaction_rolls_back_and_retries(account,monkeypatch):
    local,_,_,mock,_=stripe_fixture(account,monkeypatch)
    from app import regime_checkout_fence
    original=regime_checkout_fence.settle_if_enrolled
    monkeypatch.setattr(regime_checkout_fence,'settle_if_enrolled',lambda *a:(_ for _ in ()).throw(RuntimeError('before fence commit')))
    with httpx.Client(transport=mock) as client,pytest.raises(RuntimeError):service.reconcile_stripe(local,client=client)
    with auth.db() as c:
        assert c.execute('SELECT status FROM credit_purchase_orders WHERE id=?',(local,)).fetchone()[0]=='pending'
        assert not c.execute("SELECT 1 FROM sqlite_master WHERE name='checkout_terminal_receipts'").fetchone()
    monkeypatch.setattr(regime_checkout_fence,'settle_if_enrolled',original)
    with httpx.Client(transport=mock) as client:service.reconcile_stripe(local,client=client)
    assert_closed(local,'stripe',account)


def test_concurrent_signed_expiration_and_canonical_readback(account,monkeypatch):
    local,session,_,mock,_=stripe_fixture(account,monkeypatch)
    event={'id':'evt_expired_race','type':'checkout.session.expired','data':{'object':session}}
    def run(i):
        if i%2:return stripe.event(*signed(event))
        with httpx.Client(transport=mock) as client:return service.reconcile_stripe(local,client=client)
    with ThreadPoolExecutor(max_workers=4) as pool:list(pool.map(run,range(4)))
    assert_closed(local,'stripe',account)
    with auth.db() as c:assert c.execute('SELECT count(*) FROM checkout_terminal_receipts').fetchone()[0]==1


def test_paid_notification_after_terminal_is_durable_conflict_not_credit(account,monkeypatch):
    local,_,_,mock,_=stripe_fixture(account,monkeypatch)
    with httpx.Client(transport=mock) as client:service.reconcile_stripe(local,client=client)
    assert stripe.event(*signed(paid_event(local,'evt_contradiction')))['conflict']
    with auth.db() as c:
        report=journal.report(c);assert report['pending']==1 and report['positions'][0]['funded']==0
    assert resources.state(account)['credits_micro']==0


def paypal_unpaid(account,provider,*,state='VOIDED'):
    plan(account)
    local=paypal.checkout(account,{'kind':'credits','amount_cents':500,'request_id':'terminal-paypal-123'})['order_id']
    order=next(iter(provider[0].values()));order.update(status=state,intent='CAPTURE')
    return local,order


def test_paypal_paid_after_terminal_keeps_conflict_without_wallet_credit(account,provider):
    local,document=paypal_unpaid(account,provider)
    service.reconcile_paypal(local)
    document['status']='COMPLETED'
    document['purchase_units'][0]['payments']={'captures':[{'id':'LATECAPTURE111','status':'COMPLETED','amount':{'currency_code':'EUR','value':'5.00'}}]}
    result=paypal.fulfill(local,document)
    assert result['status']=='pending' and result['conflict']
    with auth.db() as c:
        report=journal.report(c)
        assert report['pending']==1 and report['positions'][0]['funded']==0
    assert resources.state(account)['credits_micro']==0


def test_terminal_receipt_audit_detects_reopened_fence(account,monkeypatch):
    local,_,_,mock,_=stripe_fixture(account,monkeypatch)
    with httpx.Client(transport=mock) as client:service.reconcile_stripe(local,client=client)
    with auth.db() as c:
        c.execute("UPDATE regime_fence_operations SET status='open' WHERE operation_id=?",('checkout:stripe:'+local,))
        assert 'terminal_checkout_receipt_mismatch' in journal.report(c)['issues']


@pytest.mark.parametrize('evidence',['wallet','funded_position','pending_paid','wrong_pending_identity'])
def test_terminal_proof_cannot_erase_existing_financial_evidence(account,monkeypatch,evidence):
    local,_,_,mock,_=stripe_fixture(account,monkeypatch)
    if evidence=='wallet':
        with auth.db() as c:c.execute('INSERT INTO resource_credits VALUES(?,?,1,1,?,1)',('purchase:'+local,account,'conflicting source'))
    else:
        with auth.db() as c:
            c.execute('BEGIN IMMEDIATE');journal.initialize(c)
            if evidence=='funded_position':
                c.execute("INSERT INTO payment_reconciliation_positions VALUES('stripe',?,?,500,'EUR',0,0,5000000,1)",(local,account))
            else:
                data=journal.stripe_normalize(paid_event(local,'evt_pending_evidence'))
                if evidence=='wrong_pending_identity':data.update(payment_status='unpaid',id='cs_other_session')
                journal.record_event(c,'stripe','evt_pending_evidence','a'*64,data)
    with httpx.Client(transport=mock) as client,pytest.raises(FenceBlocked):service.reconcile_stripe(local,client=client)
    with auth.db() as c:
        assert c.execute('SELECT status FROM credit_purchase_orders WHERE id=?',(local,)).fetchone()[0]=='pending'
        assert c.execute('SELECT status FROM regime_fence_operations WHERE operation_id=?',('checkout:stripe:'+local,)).fetchone()[0]=='open'


def test_paypal_voided_empty_order_closes_and_stale_retry_never_captures(account,provider):
    local,_=paypal_unpaid(account,provider)
    assert service.reconcile_paypal(local)['outcome']=='voided'
    assert service.reconcile_paypal(local)['duplicate']
    assert_closed(local,'paypal',account)
    assert paypal.checkout(account,{'kind':'credits','amount_cents':500,'request_id':'terminal-paypal-123'})=={'status':'cancelled','order_id':local}
    before=len(provider[1])
    with pytest.raises(ValueError,match='closed'):paypal.capture(account,local)
    assert len(provider[1])==before


@pytest.mark.parametrize('state',['CREATED','APPROVED','PAYER_ACTION_REQUIRED','PENDING_APPROVAL'])
def test_paypal_nonterminal_browser_cancel_is_not_financial_cancellation(account,provider,state):
    local,_=paypal_unpaid(account,provider,state=state)
    assert service.reconcile_paypal(local)['status']=='pending'
    with auth.db() as c:assert c.execute('SELECT status FROM paypal_orders WHERE id=?',(local,)).fetchone()[0]=='pending'


@pytest.mark.parametrize('mode',['erase','privacy_purge'])
def test_terminal_financial_graph_erasure_preserves_other_owner(account,monkeypatch,tmp_path,mode):
    from app import account_lifecycle as life,account_erasure,ai_arranger_runtime
    from app import checkout_reference_recovery as recovery
    from test_r210_checkout_reference_recovery import unknown_stripe
    monkeypatch.setattr(ai_arranger_runtime,'_ROOT',tmp_path/'private-queue')
    monkeypatch.setattr(auth,'send_mail',lambda *a,**kw:None)
    local,ref,_,mock,_=unknown_stripe(account,monkeypatch)
    with httpx.Client(transport=mock) as client:
        recovery.recover('stripe',local,ref,client=client)
        service.reconcile_stripe(local,client=client)
    with auth.db() as c:
        c.execute("INSERT INTO users(username,email,password_hash,role,active,email_confirmed,created_at,updated_at) VALUES('retained-owner','retained@example.test','unused','user',1,1,1,1)")
        other=c.execute("SELECT id FROM users WHERE username='retained-owner'").fetchone()[0]
        c.execute("INSERT INTO credit_purchase_orders(id,user_id,request_id,amount_cents,credit_value_micro,status,created_at) VALUES('other-order',?,'other-request',500,5000000,'pending',1)",(other,))
        journal.record_event(c,'stripe','other-retained-event','b'*64,{'type':'private.other'})
        journal.mark_applied(c,'stripe','other-retained-event','other-order')
        journal.record_event(c,'stripe','owned-pending-event','c'*64,{'type':'checkout.session.completed','order_id':local})
        journal.record_event(c,'stripe','unattributed-pending-event','d'*64,{'type':'unknown'})
    admin=auth.find_user('admin')['id'];life.register(account);life.retire(account,admin)
    if mode=='privacy_purge':life.purge(account,admin,True)
    assert account_erasure.erase(account,admin,confirmed=True)['done']
    assert not auth.get_user(account) and auth.get_user(other)
    with auth.db() as c:
        assert {r[0] for r in c.execute('SELECT event_id FROM payment_reconciliation_events')}=={'other-retained-event','unattributed-pending-event'}
        assert c.execute('SELECT count(*) FROM checkout_terminal_receipts').fetchone()[0]==0
        assert not c.execute('SELECT 1 FROM regime_payment_outbox WHERE operation_id=?',('checkout:stripe:'+local,)).fetchone()
        assert not c.execute('SELECT 1 FROM regime_fence_operations WHERE operation_id=?',('checkout:stripe:'+local,)).fetchone()


@pytest.mark.parametrize('failure',['capture','refund','authorization','amount','identity','intent','changed','config'])
def test_paypal_voided_incomplete_or_changed_history_is_blocked(account,provider,monkeypatch,failure):
    local,order=paypal_unpaid(account,provider);unit=order['purchase_units'][0]
    if failure in ('capture','refund','authorization'):unit['payments']={failure+'s':[{'id':'OBJECT111'}]}
    if failure=='amount':unit['amount']['value']='0.01'
    if failure=='identity':unit['custom_id']='other'
    if failure=='intent':order['intent']='AUTHORIZE'
    if failure in ('changed','config'):
        original=paypal._api;calls=[]
        def api(*args):
            result=original(*args);calls.append(1)
            if len(calls)==2:
                if failure=='changed':result['status']='APPROVED'
                else:paypal.settings({'client_secret':'rotated'})
            return result
        monkeypatch.setattr(paypal,'_api',api)
    with pytest.raises((ValueError,FenceBlocked)):service.reconcile_paypal(local)
    with auth.db() as c:assert c.execute('SELECT status FROM paypal_orders WHERE id=?',(local,)).fetchone()[0]=='pending'
