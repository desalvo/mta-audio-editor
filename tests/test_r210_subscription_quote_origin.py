"""New commercial subscription quotes exist before the first provider request."""
import copy
import sqlite3

import pytest
from app import auth,paypal_payments as paypal,resource_accounts as resources
from app import checkout_reference_recovery as recovery,paypal_merchant_history as history
from app import paypal_merchant_reconcile as bridge
from app.regime_operation_fence import FenceBlocked
from test_r210_subscriptions import account as account,plan  # noqa:F401
from test_r210_paypal import provider as provider  # noqa:F401
from test_r210_checkout_reference_recovery import unknown_paypal
from test_r210_paypal_merchant_history import START,END
from test_r210_original_subscription_loss import paid as paid,reverse,rows  # noqa:F401


def create(account):
    state=plan(account,price_micro=5_000_001)
    return paypal.checkout(account,{'kind':'subscription','period_start':state['period']['start'],'request_id':'quote-before-dispatch-123'})['order_id']


def test_exact_quote_is_frozen_before_provider_can_observe_creation(account,provider,monkeypatch):
    original=paypal._api;quotes=[]
    def api(cfg,method,path,*args):
        if method=='POST' and path=='/v2/checkout/orders':
            with auth.db() as c:
                quote=c.execute('SELECT fee_micro,gross_micro,surplus_micro FROM subscription_payment_basis').fetchone()
                quotes.append(tuple(quote))
        return original(cfg,method,path,*args)
    monkeypatch.setattr(paypal,'_api',api)
    local=create(account)
    assert quotes==[(5_000_001,5_010_000,9999)]
    with auth.db() as c:
        assert c.execute('SELECT status FROM paypal_orders WHERE id=?',(local,)).fetchone()[0]=='pending'
        with pytest.raises(sqlite3.IntegrityError):c.execute('UPDATE subscription_payment_basis SET fee_micro=5000000')


def test_lost_response_preserves_quote_and_manual_reference_recovery_uses_it(account,provider,monkeypatch):
    state=plan(account,price_micro=5_000_001)
    local,pid,_=unknown_paypal(account,provider,monkeypatch,body={'kind':'subscription','period_start':state['period']['start'],'request_id':'quote-lost-create-123'})
    with auth.db() as c:
        assert c.execute('SELECT fee_micro FROM subscription_payment_basis').fetchone()[0]==5_000_001
    recovery.recover('paypal',local,pid)
    paypal.capture(account,local)
    with auth.db() as c:
        assert c.execute('SELECT refund_due_micro FROM paypal_orders').fetchone()[0]==9999
        assert c.execute('SELECT fee_micro FROM subscription_payment_basis').fetchone()[0]==5_000_001


def test_current_plan_price_does_not_change_original_order_quote(account,provider):
    local=create(account)
    with auth.db() as c:c.execute('UPDATE resource_plans SET price_micro=19000000')
    paypal.capture(account,local)
    with auth.db() as c:
        assert c.execute('SELECT fee_micro FROM subscription_payment_basis').fetchone()[0]==5_000_001
        assert c.execute('SELECT refund_due_micro FROM paypal_orders').fetchone()[0]==9999


@pytest.mark.parametrize('changed',[5_000_002,4_999_999])
def test_subcent_receivable_change_is_rejected_before_collecting_money(account,provider,changed):
    local=create(account);before=len(provider[1])
    with auth.db() as c:c.execute('UPDATE resource_plan_charges SET amount_micro=?',(changed,))
    with pytest.raises(ValueError):paypal.capture(account,local)
    assert not any(call[0]=='POST' and call[1].endswith('/capture') for call in provider[1][before:])
    assert resources.state(account)['credits_micro']==0


def test_already_completed_receipt_cannot_refreeze_a_changed_original_fee(account,provider):
    local=create(account);pid=next(iter(provider[0]))
    canonical=paypal._api({},'POST','/v2/checkout/orders/'+pid+'/capture')
    with auth.db() as c:c.execute('UPDATE resource_plan_charges SET amount_micro=5000002')
    with pytest.raises(ValueError,match='Original subscription receivable changed'):
        paypal.fulfill(local,canonical)
    with auth.db() as c:
        assert c.execute('SELECT status FROM paypal_orders').fetchone()[0]=='pending'
        assert c.execute('SELECT count(*) FROM paypal_captures').fetchone()[0]==0
        assert c.execute('SELECT fee_micro FROM subscription_payment_basis').fetchone()[0]==5_000_001


def test_missing_quote_is_not_backfilled_from_current_plan(account,provider):
    local=create(account);pid=next(iter(provider[0]))
    canonical=paypal._api({},'POST','/v2/checkout/orders/'+pid+'/capture')
    with auth.db() as c:c.execute('DROP TABLE subscription_payment_basis')
    with pytest.raises(FenceBlocked,match='Original subscription quote evidence'):
        paypal.fulfill(local,canonical)
    with auth.db() as c:
        assert c.execute('SELECT count(*) FROM subscription_payment_basis').fetchone()[0]==0
        assert c.execute('SELECT status FROM paypal_orders').fetchone()[0]=='pending'


def test_unpaid_and_voided_original_quotes_do_not_invent_a_legacy_payment_gap(account,provider):
    from app.subscription_basis_audit import review,original_basis_issue
    from app.payment_reconcile_service import reconcile_paypal
    local=create(account);pid=next(iter(provider[0]))
    with auth.db() as c:
        result=review(c)
        assert result['verified'] and result['total']==0 and result['unfunded_quotes']==1
        order=c.execute('SELECT * FROM paypal_orders WHERE id=?',(local,)).fetchone()
        assert original_basis_issue(c,order) is not None  # Quote cannot authorize a paid receivable.
    provider[0][pid].update(intent='CAPTURE',status='VOIDED')
    assert reconcile_paypal(local)['checkout_closed']
    with auth.db() as c:
        result=review(c)
        assert result['verified'] and result['total']==0 and result['unfunded_quotes']==1
        assert c.execute('SELECT fee_micro FROM subscription_payment_basis').fetchone()[0]==5_000_001


def test_merchant_discovery_of_new_subscription_uses_quote_from_original_create(account,provider,monkeypatch):
    state=plan(account,price_micro=5_000_000)
    local,pid,order=unknown_paypal(account,provider,monkeypatch,body={'kind':'subscription','period_start':state['period']['start'],'request_id':'quoted-merchant-create'})
    order['status']='COMPLETED'
    order['purchase_units'][0]['payments']={'captures':[{'id':'CAPTUREQUOTED','status':'COMPLETED',
        'amount':{'currency_code':'EUR','value':'5.00'},'supplementary_data':{'related_ids':{'order_id':pid}}}]}
    original=paypal._api
    item={'transaction_info':{'transaction_id':'CAPTUREQUOTED','transaction_event_code':'T0006','transaction_status':'S',
        'transaction_amount':{'currency_code':'EUR','value':'5.00'},'paypal_reference_id_type':'TXN','paypal_reference_id':'CAPTUREQUOTED',
        'transaction_initiation_date':'2026-09-01T01:00:00Z'}}
    def api(cfg,method,path,*args):
        assert method=='GET'
        if path.startswith('/v1/reporting/transactions?'):
            return {'page':1,'total_pages':1,'total_items':1,'transaction_details':[copy.deepcopy(item)]}
        return original(cfg,method,path,*args)
    monkeypatch.setattr(paypal,'_api',api)
    admin=auth.find_user('admin')['id'];snap=history.acquire(admin,START,END,confirm=True)['snapshot_id']
    sha=history.digest(history.details(admin,snap)['items'][0])
    assert bridge.reconcile(admin,snap,sha,confirm=True)['ledger_reconciled']
    with auth.db() as c:
        assert c.execute('SELECT status FROM resource_plan_charges').fetchone()[0]=='paid'
        assert c.execute('SELECT fee_micro FROM subscription_payment_basis').fetchone()[0]==5_000_000
        assert c.execute('SELECT provider_order FROM paypal_orders WHERE id=?',(local,)).fetchone()[0]==pid
    assert resources.state(account)['credits_micro']==0


def test_merchant_recovery_of_repayment_uses_immutable_original_target(paid,account,provider,monkeypatch):
    reverse();source=rows(account)[0]
    local,pid,order=unknown_paypal(account,provider,monkeypatch,body={'kind':'subscription_reversal',
        'refund_id':source['refund_id'],'expected_due_micro':source['due_micro'],'request_id':'repayment-lost-response'})
    order['status']='COMPLETED';amount=copy.deepcopy(order['purchase_units'][0]['amount'])
    order['purchase_units'][0]['payments']={'captures':[{'id':'CAPTUREREPAY','status':'COMPLETED',
        'amount':amount,'supplementary_data':{'related_ids':{'order_id':pid}}}]}
    original=paypal._api
    item={'transaction_info':{'transaction_id':'CAPTUREREPAY','transaction_event_code':'T0006','transaction_status':'S',
        'transaction_amount':amount,'paypal_reference_id_type':'TXN','paypal_reference_id':'CAPTUREREPAY',
        'transaction_initiation_date':'2026-09-01T01:00:00Z'}}
    def api(cfg,method,path,*args):
        assert method=='GET'
        if path.startswith('/v1/reporting/transactions?'):
            return {'page':1,'total_pages':1,'total_items':1,'transaction_details':[copy.deepcopy(item)]}
        return original(cfg,method,path,*args)
    monkeypatch.setattr(paypal,'_api',api)
    admin=auth.find_user('admin')['id'];snap=history.acquire(admin,START,END,confirm=True)['snapshot_id']
    sha=history.digest(history.details(admin,snap)['items'][0])
    assert bridge.reconcile(admin,snap,sha,confirm=True)['ledger_reconciled']
    assert rows(account)[0]['due_micro']==0 and resources.state(account)['credits_micro']==0
    with auth.db() as c:
        assert c.execute('SELECT amount_micro FROM subscription_repayment_allocations WHERE order_id=?',(local,)).fetchone()[0]==source['due_micro']
