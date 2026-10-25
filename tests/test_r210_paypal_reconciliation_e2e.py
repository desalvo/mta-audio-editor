import copy
import json

import pytest
from app import auth, paypal_payments as paypal, resource_accounts as r
from app import payment_reconciliation as pr
from test_r210_paypal import provider as provider  # noqa: F401
from test_r210_subscriptions import account as account, plan  # noqa: F401

HEADERS={k:'test' for k in ['paypal-auth-algo','paypal-cert-url','paypal-transmission-id','paypal-transmission-sig','paypal-transmission-time']}


def setup_order(account,provider,monkeypatch,*,before_capture=False,subscription=False):
    state=plan(account,**({'price_micro':5_000_000} if subscription else {}))
    body={'kind':'subscription','period_start':state['period']['start'],'request_id':'refund-capture-e2e-123'} if subscription else {'kind':'credits','amount_cents':500,'request_id':'refund-capture-e2e-123'}
    local=paypal.checkout(account,body)['order_id'];orders,_=provider;pid=next(iter(orders))
    paypal._api({},'POST','/v2/checkout/orders/'+pid+'/capture')
    capture=orders[pid]['purchase_units'][0]['payments']['captures'][0]
    capture['id']='CAPTURE111';capture['amount']={'value':'3.00','currency_code':'EUR'}
    orders[pid]['purchase_units'][0]['payments']['captures'].append({'id':'CAPTURE222','status':'COMPLETED','amount':{'value':'2.00','currency_code':'EUR'}})
    if not before_capture:paypal.fulfill(local,copy.deepcopy(orders[pid]))
    original=paypal._api
    link={'rel':'up','href':'https://api-m.sandbox.paypal.com/v2/payments/captures/CAPTURE111'}
    canonical={'id':'REFUND111','status':'COMPLETED','amount':{'value':'3.00','currency_code':'EUR'},'links':[copy.deepcopy(link)]}
    def api(cfg,method,path,*args):
        if path=='/v2/payments/refunds/REFUND111':return copy.deepcopy(canonical)
        return original(cfg,method,path,*args)
    monkeypatch.setattr(paypal,'_api',api)
    event={'id':'evt_refund_capture','event_type':'PAYMENT.CAPTURE.REFUNDED','resource':{'id':'REFUND111','links':[link]}}
    return local,orders[pid],event,canonical


def test_multiple_capture_refund_before_fulfillment_replays_atomically(account,provider,monkeypatch):
    local,canonical,event,_=setup_order(account,provider,monkeypatch,before_capture=True)
    assert paypal.webhook(json.dumps(event).encode(),HEADERS)['pending']
    paypal.fulfill(local,canonical)
    assert r.state(account)['credits_micro']==2_000_000
    paypal.webhook(json.dumps(event).encode(),HEADERS)
    paypal.fulfill(local,canonical)
    assert r.state(account)['credits_micro']==2_000_000
    with auth.db() as c:
        report=pr.report(c)
        assert report['verified'] and report['pending']==0
        assert report['positions'][0]['refunded_minor']==300


def test_canonical_refund_cannot_be_attributed_to_other_capture(account,provider,monkeypatch):
    _,_,event,canonical=setup_order(account,provider,monkeypatch)
    canonical['links'][0]['href']='https://api-m.sandbox.paypal.com/v2/payments/captures/CAPTURE222'
    with pytest.raises(ValueError,match='mismatch'):paypal.webhook(json.dumps(event).encode(),HEADERS)
    assert r.state(account)['credits_micro']==5_000_000


def test_refund_cannot_cross_provider_environment(account,provider,monkeypatch):
    _,_,event,_=setup_order(account,provider,monkeypatch)
    event['resource']['links'][0]['href']='https://api-m.paypal.com/v2/payments/captures/CAPTURE111'
    with pytest.raises(ValueError):paypal.webhook(json.dumps(event).encode(),HEADERS)
    assert r.state(account)['credits_micro']==5_000_000


def test_failed_refund_replay_rolls_back_capture_and_wallet(account,provider,monkeypatch):
    local,canonical,event,_=setup_order(account,provider,monkeypatch,before_capture=True)
    paypal.webhook(json.dumps(event).encode(),HEADERS)
    original=paypal._apply_refund
    monkeypatch.setattr(paypal,'_apply_refund',lambda *a:(_ for _ in ()).throw(RuntimeError('crash')))
    with pytest.raises(RuntimeError):paypal.fulfill(local,canonical)
    assert r.state(account)['credits_micro']==0
    with auth.db() as c:assert c.execute('SELECT count(*) FROM paypal_captures').fetchone()[0]==0
    monkeypatch.setattr(paypal,'_apply_refund',original)
    paypal.fulfill(local,canonical);assert r.state(account)['credits_micro']==2_000_000


def test_subscription_refund_records_exact_receivable_without_wallet_credit(account,provider,monkeypatch):
    _,_,event,_=setup_order(account,provider,monkeypatch,subscription=True)
    paypal.webhook(json.dumps(event).encode(),HEADERS)
    assert r.state(account)['credits_micro']==0
    with auth.db() as c:assert pr.report(c)['subscription_reversal_due_micro']==3_000_000


def test_capture_reversal_and_refund_never_double_debit(account,provider,monkeypatch):
    _,_,refund,_=setup_order(account,provider,monkeypatch)
    reversal={'id':'evt_reversal','event_type':'PAYMENT.CAPTURE.REVERSED','resource':{
        'id':'CAPTURE111','amount':{'currency_code':'EUR','value':'3.00'}}}
    paypal.webhook(json.dumps(reversal).encode(),HEADERS)
    assert r.state(account)['credits_micro']==2_000_000
    paypal.webhook(json.dumps(refund).encode(),HEADERS)
    paypal.webhook(json.dumps(reversal).encode(),HEADERS)
    assert r.state(account)['credits_micro']==2_000_000
    with auth.db() as c:
        report=pr.report(c)
        assert report['verified'] and report['positions'][0]['held_minor']==0
        assert report['positions'][0]['refunded_minor']==300


def test_reversal_before_capture_is_replayed_in_capture_transaction(account,provider,monkeypatch):
    local,canonical,_,_=setup_order(account,provider,monkeypatch,before_capture=True)
    event={'id':'evt_reversal','event_type':'PAYMENT.CAPTURE.REVERSED','resource':{
        'id':'CAPTURE111','amount':{'currency_code':'EUR','value':'3.00'}}}
    assert paypal.webhook(json.dumps(event).encode(),HEADERS)['pending']
    paypal.fulfill(local,canonical)
    assert r.state(account)['credits_micro']==2_000_000
    with auth.db() as c:assert pr.report(c)['pending']==0


def test_dispute_readback_holds_then_releases_and_rejects_stale_updates(account,provider,monkeypatch):
    setup_order(account,provider,monkeypatch)
    original=paypal._api
    canonical={'dispute_id':'PP-D-123','update_time':'2026-10-22T01:00:00Z','status':'UNDER_REVIEW',
               'disputed_transactions':[{'seller_transaction_id':'CAPTURE111'}],
               'dispute_amount':{'value':'2.00','currency_code':'EUR'}}
    def api(cfg,method,path,*args):
        if path=='/v1/customer/disputes/PP-D-123':return copy.deepcopy(canonical)
        return original(cfg,method,path,*args)
    monkeypatch.setattr(paypal,'_api',api)
    def event(identifier):return {'id':identifier,'event_type':'CUSTOMER.DISPUTE.UPDATED','resource':{'dispute_id':'PP-D-123'}}
    first=event('evt_disputed');paypal.webhook(json.dumps(first).encode(),HEADERS)
    assert r.state(account)['credits_micro']==3_000_000
    canonical.update(status='RESOLVED',update_time='2026-10-23T01:00:00Z',dispute_outcome={'outcome_code':'RESOLVED_SELLER_FAVOUR'})
    paypal.webhook(json.dumps(event('evt_resolved')).encode(),HEADERS)
    assert r.state(account)['credits_micro']==5_000_000
    paypal.webhook(json.dumps(first).encode(),HEADERS)  # old event identity is immutable
    assert r.state(account)['credits_micro']==5_000_000
    canonical.update(status='UNDER_REVIEW',update_time='2026-10-22T01:00:00Z')
    paypal.webhook(json.dumps(event('evt_stale')).encode(),HEADERS)
    assert r.state(account)['credits_micro']==5_000_000


def test_ambiguous_paypal_payout_keeps_hold_and_pending_readiness(account,provider,monkeypatch):
    setup_order(account,provider,monkeypatch)
    original=paypal._api
    canonical={'dispute_id':'PP-D-123','update_time':'2026-10-22T01:00:00Z','status':'RESOLVED',
               'disputed_transactions':[{'seller_transaction_id':'CAPTURE111'}],
               'dispute_amount':{'value':'2.00','currency_code':'EUR'},
               'dispute_outcome':{'outcome_code':'RESOLVED_WITH_PAYOUT'}}
    monkeypatch.setattr(paypal,'_api',lambda cfg,method,path,*args:copy.deepcopy(canonical) if '/customer/disputes/' in path else original(cfg,method,path,*args))
    event={'id':'evt_payout','event_type':'CUSTOMER.DISPUTE.RESOLVED','resource':{'dispute_id':'PP-D-123'}}
    assert paypal.webhook(json.dumps(event).encode(),HEADERS)['pending']
    assert r.state(account)['credits_micro']==3_000_000
    with auth.db() as c:assert pr.report(c)['pending']==1
