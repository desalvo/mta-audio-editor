"""Authenticated subscription refund -> owner checkout -> cash repayment saga."""
import copy
import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient
from app import auth,paypal_payments as paypal,resource_accounts as resources
from app import payment_reconciliation as journal,subscription_receivables as debts
from app.regime_operation_fence import FenceBlocked
from test_r210_subscriptions import account as account,plan  # noqa: F401
from test_r210_paypal import provider as provider  # noqa: F401
from test_r210_paypal_reconciliation_e2e import setup_order,HEADERS
from test_r210_legal_documents import cookie


@pytest.fixture
def debt(account,provider,monkeypatch):
    local,order,event,_=setup_order(account,provider,monkeypatch,subscription=True)
    paypal.webhook(json.dumps(event).encode(),HEADERS)
    assert resources.transactions(account)['subscription_reversals'][0]['due_micro']==3_000_000
    return local,order


def checkout(uid,*,key='repayment-owner-123',due=3_000_000,rid='REFUND111'):
    return paypal.checkout(uid,{'kind':'subscription_reversal','refund_id':rid,'expected_due_micro':due,'request_id':key})


def balance(uid):return resources.transactions(uid)['subscription_reversals'][0]


def refund(monkeypatch,capture_id,*,rid='REFUND333',cents=100):
    original=paypal._api
    obj={'id':rid,'status':'COMPLETED','amount':{'currency_code':'EUR','value':f'{cents//100}.{cents%100:02d}'},
         'links':[{'rel':'up','href':'https://api-m.sandbox.paypal.com/v2/payments/captures/'+capture_id}]}
    def api(cfg,method,path,*args):
        if method=='GET' and path=='/v2/payments/refunds/'+rid:return copy.deepcopy(obj)
        return original(cfg,method,path,*args)
    monkeypatch.setattr(paypal,'_api',api)
    event={'id':'evt_'+rid,'event_type':'PAYMENT.CAPTURE.REFUNDED','resource':obj}
    return paypal.webhook(json.dumps(event).encode(),HEADERS)


def capture_id(local):
    with auth.db() as c:return c.execute('SELECT id FROM paypal_captures WHERE order_id=?',(local,)).fetchone()[0]


def risk(monkeypatch,local,*,resolved=False):
    original=paypal._api
    obj={'dispute_id':'PP-D-REPAY','update_time':'2026-10-23T02:00:00Z' if resolved else '2026-10-23T01:00:00Z',
         'status':'RESOLVED' if resolved else 'UNDER_REVIEW','disputed_transactions':[{'seller_transaction_id':capture_id(local)}],
         'dispute_amount':{'currency_code':'EUR','value':'3.00'}}
    if resolved:obj['dispute_outcome']={'outcome_code':'RESOLVED_SELLER_FAVOUR'}
    monkeypatch.setattr(paypal,'_api',lambda cfg,method,path,*args:copy.deepcopy(obj) if path=='/v1/customer/disputes/PP-D-REPAY' else original(cfg,method,path,*args))
    event={'id':'repay_dispute_resolved' if resolved else 'repay_dispute_held','event_type':'CUSTOMER.DISPUTE.UPDATED','resource':{'dispute_id':obj['dispute_id']}}
    paypal.webhook(json.dumps(event).encode(),HEADERS)


def test_exact_repayment_closes_debt_without_wallet_or_fee_mutation(account,provider,debt):
    original_fee=resources.transactions(account)['subscription_fees']
    with auth.db() as c:original_credits=[tuple(row) for row in c.execute('SELECT * FROM resource_credits ORDER BY id')]
    order=checkout(account);assert checkout(account)==order
    assert balance(account)['pending_order_id']==order['order_id'] and balance(account)['due_micro']==3_000_000
    paypal.capture(account,order['order_id']);paypal.capture(account,order['order_id'])
    assert checkout(account)['status']=='paid'
    assert balance(account)['due_micro']==0 and balance(account)['covered_micro']==3_000_000
    assert resources.transactions(account)['subscription_fees']==original_fee
    assert resources.state(account)['credits_micro']==0
    with auth.db() as c:
        report=journal.report(c);assert report['verified'] and report['subscription_reversal_due_micro']==0
        assert c.execute('SELECT count(*) FROM subscription_repayment_allocations').fetchone()[0]==1
        assert [tuple(row) for row in c.execute('SELECT * FROM resource_credits ORDER BY id')]==original_credits


def test_concurrent_checkout_only_one_provider_order_and_pending_target(account,provider,debt):
    def attempt(i):
        try:return checkout(account,key='concurrent-repayment-'+str(i))
        except ValueError:return None
    with ThreadPoolExecutor(max_workers=4) as pool:result=list(pool.map(attempt,range(4)))
    assert sum(item is not None for item in result)==1
    assert len(provider[0])==2


def test_concurrent_fulfillment_delivers_one_allocation(account,provider,debt):
    local=checkout(account)['order_id']
    with auth.db() as c:pid=c.execute('SELECT provider_order FROM paypal_orders WHERE id=?',(local,)).fetchone()[0]
    canonical=paypal._api({},'POST','/v2/checkout/orders/'+pid+'/capture')
    with ThreadPoolExecutor(max_workers=4) as pool:list(pool.map(lambda _:paypal.fulfill(local,copy.deepcopy(canonical)),range(4)))
    assert balance(account)['due_micro']==0
    with auth.db() as c:assert c.execute('SELECT count(*) FROM subscription_repayment_allocations').fetchone()[0]==1


def test_refund_reopens_same_debt_and_can_be_repaid_again(account,provider,debt,monkeypatch):
    local=checkout(account)['order_id'];paypal.capture(account,local)
    refund(monkeypatch,capture_id(local))
    assert balance(account)['due_micro']==1_000_000
    with auth.db() as c:assert c.execute('SELECT count(*) FROM paypal_subscription_reversals').fetchone()[0]==1
    newer=checkout(account,key='second-repayment-123',due=1_000_000)['order_id'];paypal.capture(account,newer)
    assert balance(account)['due_micro']==0 and resources.state(account)['credits_micro']==0


def test_dispute_release_after_second_repayment_creates_refund_liability(account,provider,debt,monkeypatch):
    first=checkout(account)['order_id'];paypal.capture(account,first)
    risk(monkeypatch,first);assert balance(account)['due_micro']==3_000_000
    second=checkout(account,key='held-repayment-123')['order_id'];paypal.capture(account,second)
    risk(monkeypatch,first,resolved=True)
    state=balance(account);assert state['due_micro']==0
    assert sum(p['refund_due_micro'] for p in state['payments'])==3_000_000
    with auth.db() as c:
        report=journal.report(c);assert report['verified'] and report['subscription_repayment_refund_due_micro']==3_000_000
        assert c.execute('SELECT refund_due_micro FROM paypal_orders WHERE id=?',(second,)).fetchone()[0]==3_000_000
    refund(monkeypatch,capture_id(second),cents=300)
    assert balance(account)['due_micro']==0 and sum(p['refund_due_micro'] for p in balance(account)['payments'])==0


def test_failure_rolls_back_capture_allocation_and_fence_then_retries(account,provider,debt,monkeypatch):
    local=checkout(account)['order_id'];original=debts.sync
    monkeypatch.setattr(debts,'sync',lambda c:(_ for _ in ()).throw(RuntimeError('after allocation')))
    with pytest.raises(RuntimeError):paypal.capture(account,local)
    with auth.db() as c:
        assert c.execute('SELECT count(*) FROM subscription_repayment_allocations').fetchone()[0]==0
        assert c.execute('SELECT status FROM paypal_orders WHERE id=?',(local,)).fetchone()[0]=='pending'
    assert balance(account)['due_micro']==3_000_000
    monkeypatch.setattr(debts,'sync',original);paypal.capture(account,local)
    assert balance(account)['due_micro']==0


def test_uncertain_create_stays_pending_without_second_provider_post(account,provider,debt,monkeypatch):
    original=paypal._api;calls=[]
    def api(cfg,method,path,*args):
        if method=='POST' and path=='/v2/checkout/orders':calls.append(path);raise ValueError('network timeout after submission')
        return original(cfg,method,path,*args)
    monkeypatch.setattr(paypal,'_api',api)
    with pytest.raises(ValueError):checkout(account)
    assert balance(account)['pending_order_id'] and balance(account)['pending_checkout_url'] is None
    with pytest.raises((ValueError,FenceBlocked)):checkout(account)
    with pytest.raises(ValueError):checkout(account,key='different-key-123')
    assert len(calls)==1


def test_cent_rounding_surplus_is_separate_and_refunded_first(account,provider,monkeypatch):
    state=plan(account,price_micro=5_000_001)
    local=paypal.checkout(account,{'kind':'subscription','period_start':state['period']['start'],'request_id':'subcent-source-123'})['order_id']
    paypal.capture(account,local)
    refund(monkeypatch,capture_id(local),rid='REFUND111',cents=300)
    assert balance(account)['due_micro']==2_990_001
    repayment=checkout(account,due=2_990_001)['order_id'];paypal.capture(account,repayment)
    assert balance(account)['due_micro']==0
    with auth.db() as c:assert c.execute('SELECT refund_due_micro FROM paypal_orders WHERE id=?',(repayment,)).fetchone()[0]==9999
    refund(monkeypatch,capture_id(repayment),rid='REFUND222',cents=1)
    assert balance(account)['due_micro']==1


def test_owner_api_quote_csrf_and_regime_guards(account,provider,debt,monkeypatch):
    from app import main
    monkeypatch.setattr(main,'NATIVE_SINGLE_USER',False);monkeypatch.setattr(main,'check_basic_auth',lambda request:False)
    monkeypatch.delenv('MTA_ALLOW_INSECURE_NO_AUTH',raising=False)
    body={'kind':'subscription_reversal','refund_id':'REFUND111','expected_due_micro':3_000_000,'request_id':'api-repayment-123'}
    client=TestClient(main.app);url='/api/account/paypal/checkout';headers={'X-MTA-Request':'1'}
    assert client.post(url,headers=headers,json=body).status_code==401
    client.cookies.update(cookie(auth.find_user('admin')['id']))
    assert client.get('/api/account/subscription').json()['transactions']['subscription_reversals']==[]
    assert client.post(url,headers=headers,json=body).status_code==422
    client.cookies.update(cookie(account))
    assert client.post(url,json=body).status_code==403
    assert client.post(url,headers=headers,json={**body,'expected_due_micro':1}).status_code==422
    assert client.post(url,headers=headers,json={**body,'amount_cents':1}).status_code==422
    result=client.post(url,headers=headers,json=body);assert result.status_code==200,result.text
    snapshot=client.get('/api/account/subscription').json();assert snapshot['repayment_available']
    assert snapshot['transactions']['subscription_reversals'][0]['pending_order_id']==result.json()['order_id']
    with auth.db() as c:c.execute("UPDATE regime_fence_state SET regime='NON_COMMERCIAL'")
    (auth.data_root()/'service-regime.json').write_text('{"regime":"NON_COMMERCIAL","revision":0}')
    assert client.post(url,headers=headers,json=body).status_code==403
    assert not client.get('/api/account/subscription').json()['repayment_available']


def test_allocations_are_immutable_and_missing_position_blocks_report(account,provider,debt):
    local=checkout(account)['order_id'];paypal.capture(account,local)
    with auth.db() as c:
        with pytest.raises(sqlite3.IntegrityError):c.execute('UPDATE subscription_repayment_allocations SET amount_micro=0')
    with auth.db() as c:
        with pytest.raises(sqlite3.IntegrityError):c.execute('DELETE FROM subscription_repayment_targets')
    with auth.db() as c:
        c.execute("DELETE FROM payment_reconciliation_positions WHERE order_id=?",(local,))
        result=journal.report(c);assert not result['verified'] and result['subscription_reversal_due_micro'] is None


def test_refund_before_repayment_fulfillment_is_atomic(account,provider,debt,monkeypatch):
    local=checkout(account)['order_id']
    with auth.db() as c:pid=c.execute('SELECT provider_order FROM paypal_orders WHERE id=?',(local,)).fetchone()[0]
    canonical=paypal._api({},'POST','/v2/checkout/orders/'+pid+'/capture')
    cid=canonical['purchase_units'][0]['payments']['captures'][0]['id']
    assert refund(monkeypatch,cid,cents=100)['pending']
    paypal.fulfill(local,canonical)
    assert balance(account)['due_micro']==1_000_000
    with auth.db() as c:
        assert journal.report(c)['pending']==0
        assert c.execute('SELECT count(*) FROM paypal_subscription_reversals').fetchone()[0]==1


def test_repayment_allowed_for_existing_debt_after_plan_service_disabled(account,provider,debt):
    resources.configure({'enabled':False,'credits_enabled':False})
    local=checkout(account)['order_id'];paypal.capture(account,local)
    assert balance(account)['due_micro']==0 and resources.state(account)['credits_micro']==0


def test_owner_quote_change_is_checked_before_provider_capture(account,provider,debt,monkeypatch):
    first=checkout(account)['order_id'];paypal.capture(account,first)
    risk(monkeypatch,first)
    local=checkout(account,key='new-quote-repayment-123')['order_id']
    # A held earlier payment is restored while the next checkout is approved.
    # No provider POST may collect the now-obsolete repayment quote.
    risk(monkeypatch,first,resolved=True)
    before=len([call for call in provider[1] if call[1].endswith('/capture')])
    with pytest.raises(ValueError,match='No unpaid|changed'):paypal.capture(account,local)
    assert len([call for call in provider[1] if call[1].endswith('/capture')])==before


def test_multiple_sources_are_bound_to_original_refund(account,provider,debt,monkeypatch):
    original_order=debt[0]
    with auth.db() as c:cid=c.execute("SELECT id FROM paypal_captures WHERE order_id=? AND id='CAPTURE222'",(original_order,)).fetchone()[0]
    refund(monkeypatch,cid,rid='REFUND222',cents=200)
    first=checkout(account)['order_id'];paypal.capture(account,first)
    sources=resources.transactions(account)['subscription_reversals']
    assert {s['refund_id']:s['due_micro'] for s in sources}=={'REFUND111':0,'REFUND222':2_000_000}
    second=checkout(account,key='second-source-payment',due=2_000_000,rid='REFUND222')['order_id'];paypal.capture(account,second)
    assert sum(s['due_micro'] for s in resources.transactions(account)['subscription_reversals'])==0


def test_already_captured_obsolete_quote_is_retained_as_refund_due(account,provider,debt,monkeypatch):
    first=checkout(account)['order_id'];paypal.capture(account,first);risk(monkeypatch,first)
    second=checkout(account,key='obsolete-captured-payment')['order_id'];risk(monkeypatch,first,resolved=True)
    with auth.db() as c:pid=c.execute('SELECT provider_order FROM paypal_orders WHERE id=?',(second,)).fetchone()[0]
    canonical=paypal._api({},'POST','/v2/checkout/orders/'+pid+'/capture')
    paypal.fulfill(second,copy.deepcopy(canonical));paypal.fulfill(second,copy.deepcopy(canonical))
    assert balance(account)['due_micro']==0
    with auth.db() as c:
        assert c.execute('SELECT refund_due_micro FROM paypal_orders WHERE id=?',(second,)).fetchone()[0]==3_000_000
        assert c.execute('SELECT amount_micro FROM subscription_repayment_allocations WHERE order_id=?',(second,)).fetchone()[0]==0
        assert journal.report(c)['subscription_repayment_refund_due_micro']==3_000_000


def test_verified_webhook_retries_allocate_once(account,provider,debt):
    local=checkout(account)['order_id']
    with auth.db() as c:pid=c.execute('SELECT provider_order FROM paypal_orders WHERE id=?',(local,)).fetchone()[0]
    paypal._api({},'POST','/v2/checkout/orders/'+pid+'/capture')
    event={'id':'repay_verified_completed','event_type':'PAYMENT.CAPTURE.COMPLETED',
           'resource':{'supplementary_data':{'related_ids':{'order_id':pid}}}}
    paypal.webhook(json.dumps(event).encode(),HEADERS);paypal.webhook(json.dumps(event).encode(),HEADERS)
    assert balance(account)['due_micro']==0
    with auth.db() as c:
        assert c.execute('SELECT count(*) FROM subscription_repayment_allocations').fetchone()[0]==1
        assert c.execute('SELECT count(*) FROM paypal_events WHERE id=?',(event['id'],)).fetchone()[0]==1


def test_authenticated_refunded_initial_repayment_reopens_original_debt(account,provider,debt,monkeypatch):
    from app import payment_reconcile_service
    local=checkout(account)['order_id']
    with auth.db() as c:pid=c.execute('SELECT provider_order FROM paypal_orders WHERE id=?',(local,)).fetchone()[0]
    canonical=paypal._api({},'POST','/v2/checkout/orders/'+pid+'/capture')
    capture=canonical['purchase_units'][0]['payments']['captures'][0];capture['status']='PARTIALLY_REFUNDED'
    rid='REFUND444';obj={'id':rid,'status':'COMPLETED','amount':{'currency_code':'EUR','value':'1.00'},
        'seller_payable_breakdown':{'total_refunded_amount':{'currency_code':'EUR','value':'1.00'}},
        'links':[{'rel':'up','href':'https://api-m.sandbox.paypal.com/v2/payments/captures/'+capture['id']}]}
    canonical['purchase_units'][0]['payments']['refunds']=[obj]
    original=paypal._api
    def api(cfg,method,path,*args):
        if path=='/v2/payments/captures/'+capture['id']:return copy.deepcopy(capture)
        if path=='/v2/payments/refunds/'+rid:return copy.deepcopy(obj)
        return original(cfg,method,path,*args)
    monkeypatch.setattr(paypal,'_api',api)
    payment_reconcile_service.reconcile_paypal(local);payment_reconcile_service.reconcile_paypal(local)
    assert balance(account)['due_micro']==1_000_000 and resources.state(account)['credits_micro']==0
    with auth.db() as c:
        assert c.execute('SELECT count(*) FROM paypal_subscription_reversals').fetchone()[0]==1
        assert journal.report(c)['verified']


def test_permanent_capture_reversal_reopens_original_receivable(account,provider,debt):
    local=checkout(account)['order_id'];paypal.capture(account,local)
    event={'id':'repay_capture_reversed','event_type':'PAYMENT.CAPTURE.REVERSED','resource':{
        'id':capture_id(local),'amount':{'currency_code':'EUR','value':'3.00'}}}
    paypal.webhook(json.dumps(event).encode(),HEADERS);paypal.webhook(json.dumps(event).encode(),HEADERS)
    assert balance(account)['due_micro']==3_000_000
    with auth.db() as c:
        assert c.execute('SELECT count(*) FROM paypal_subscription_reversals').fetchone()[0]==1
        assert journal.report(c)['subscription_reversal_due_micro']==3_000_000


@pytest.mark.parametrize('mode',['erase','privacy_purge'])
def test_authorized_account_erasure_preserves_other_owner_financial_records(account,provider,debt,monkeypatch,tmp_path,mode):
    from app import account_lifecycle as life,account_erasure,ai_arranger_runtime
    monkeypatch.setattr(ai_arranger_runtime,'_ROOT',tmp_path/'private-queue')
    monkeypatch.setattr(auth,'send_mail',lambda *a,**kw:None)
    local=checkout(account)['order_id'];paypal.capture(account,local)
    with auth.db() as c:
        c.execute("INSERT INTO users(username,email,password_hash,role,active,email_confirmed,created_at,updated_at) VALUES('other-owner','other@example.test','unused','user',1,1,1,1)")
        other=c.execute("SELECT id FROM users WHERE username='other-owner'").fetchone()[0]
    p=plan(other,price_micro=5_000_000)
    other_order=paypal.checkout(other,{'kind':'subscription','period_start':p['period']['start'],'request_id':'other-fee-payment'})['order_id'];paypal.capture(other,other_order)
    refund(monkeypatch,capture_id(other_order),rid='OTHER111',cents=100)
    admin=auth.find_user('admin')['id'];life.register(account);life.retire(account,admin)
    with pytest.raises(ValueError,match='contabili'):life.purge(account,admin,False)
    if mode=='erase':assert account_erasure.erase(account,admin,confirmed=True)['done']
    else:
        life.purge(account,admin,True)
        assert life.listings()['sandboxes']
        assert account_erasure.erase(account,admin,confirmed=True)['done']
    assert not auth.get_user(account) and auth.get_user(other)
    with auth.db() as c:
        assert c.execute('SELECT refund_id FROM paypal_subscription_reversals').fetchall()[0][0]=='OTHER111'
        assert c.execute('SELECT count(*) FROM subscription_repayment_allocations').fetchone()[0]==0
        assert c.execute('SELECT count(*) FROM subscription_repayment_targets').fetchone()[0]==0
        with pytest.raises(sqlite3.IntegrityError):c.execute('DELETE FROM paypal_subscription_reversals')


def test_erasure_authorization_is_retired_owner_scoped_and_connection_local(account,provider,debt,monkeypatch,tmp_path):
    from app import account_lifecycle as life,ai_arranger_runtime
    monkeypatch.setattr(ai_arranger_runtime,'_ROOT',tmp_path/'private-queue')
    monkeypatch.setattr(auth,'send_mail',lambda *a,**kw:None)
    admin=auth.find_user('admin')['id'];life.register(account)
    with auth.db() as c:
        c.execute('BEGIN IMMEDIATE')
        with pytest.raises(FenceBlocked):debts.authorize_account_erasure(c,account,admin)
    life.retire(account,admin)
    with auth.db() as c:
        c.execute('BEGIN IMMEDIATE')
        with pytest.raises(FenceBlocked):debts.authorize_account_erasure(c,account,account)
        debts.authorize_account_erasure(c,account,admin)
        assert c.execute("SELECT mta_subscription_erasure('paypal_subscription_reversals','REFUND111')").fetchone()[0]==1
        assert c.execute("SELECT mta_subscription_erasure('paypal_subscription_reversals','OTHER111')").fetchone()[0]==0
    with auth.db() as c:
        assert c.execute("SELECT mta_subscription_erasure('paypal_subscription_reversals','REFUND111')").fetchone()[0]==0
        with pytest.raises(sqlite3.IntegrityError):c.execute('DELETE FROM paypal_subscription_reversals')
