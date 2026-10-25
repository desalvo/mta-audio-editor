"""Authenticated contradictory final risk evidence must not restore lost funds."""
import copy
import json

import pytest
from app import auth, paypal_payments as paypal, resource_accounts as resources, owner_payments
from app import payment_reconciliation as journal
from test_r210_subscriptions import account as account  # noqa: F401
from test_r210_paypal import provider as provider  # noqa: F401
from test_r210_paypal_reconciliation_e2e import setup_order, HEADERS
from test_r210_subscription_repayment_e2e import debt as debt, checkout, balance  # noqa: F401


@pytest.fixture
def risk_source(account,provider,monkeypatch,request,kind):
    if kind=='repayment':
        request.getfixturevalue('debt')
        local=checkout(account)['order_id'];paypal.capture(account,local)
        with auth.db() as c:capture=c.execute('SELECT id FROM paypal_captures WHERE order_id=?',(local,)).fetchone()[0]
    else:
        local,_,_,_=setup_order(account,provider,monkeypatch,subscription=kind=='subscription');capture='CAPTURE111'
    original=paypal._api
    canonical={'dispute_id':'PP-D-FINAL','update_time':'2026-10-23T01:00:00Z','status':'UNDER_REVIEW',
               'disputed_transactions':[{'seller_transaction_id':capture}],
               'dispute_amount':{'value':'2.00','currency_code':'EUR'}}
    def api(cfg,method,path,*args):
        if path=='/v1/customer/disputes/PP-D-FINAL':
            assert method=='GET';return copy.deepcopy(canonical)
        return original(cfg,method,path,*args)
    monkeypatch.setattr(paypal,'_api',api)
    def emit(status,number):
        canonical['update_time']=f'2026-10-23T0{number}:00:00Z'
        canonical['status']='RESOLVED' if status in ('permanent','released','uncertain') else 'UNDER_REVIEW'
        canonical['dispute_outcome']={'outcome_code':{'permanent':'RESOLVED_BUYER_FAVOUR','released':'RESOLVED_SELLER_FAVOUR','uncertain':'RESOLVED_WITH_PAYOUT'}.get(status,'')}
        body={'id':f'event_{status}_{number}','event_type':'CUSTOMER.DISPUTE.UPDATED','resource':{'dispute_id':'PP-D-FINAL'}}
        return paypal.webhook(json.dumps(body).encode(),HEADERS)
    return local,emit


def snapshot(uid,kind):
    with auth.db() as c:
        values=[tuple(row) for row in c.execute('SELECT held_minor,net_micro FROM payment_reconciliation_positions ORDER BY order_id')]
    return resources.state(uid)['credits_micro'],values,balance(uid)['due_micro'] if kind=='repayment' else None


@pytest.mark.parametrize('kind',['credits','subscription','repayment'])
@pytest.mark.parametrize('terminal',['permanent','released'])
def test_opposite_final_outcome_stays_pending_after_later_same_final_confirmation(account,risk_source,kind,terminal):
    local,emit=risk_source;emit('held',1);emit(terminal,2)
    frozen=snapshot(account,kind)
    opposite='released' if terminal=='permanent' else 'permanent'
    assert emit(opposite,3)['pending']
    assert snapshot(account,kind)==frozen
    assert emit(opposite,3)['pending'] and snapshot(account,kind)==frozen
    emit(terminal,4)
    assert snapshot(account,kind)==frozen
    with auth.db() as c:
        assert c.execute('SELECT status FROM paypal_financial_holds WHERE hold_id=?',('dispute:PP-D-FINAL',)).fetchone()[0]==terminal
        report=journal.report(c);assert report['pending']==1 and not report['transition_safe']
        event=c.execute("SELECT order_id,state FROM payment_reconciliation_events WHERE event_id=?",(f'event_{opposite}_3',)).fetchone()
        assert tuple(event)==(local,'pending')
    item=next(x for x in owner_payments.history(account)['items'] if x['id']==local)
    assert item['financial_review_pending']
    assert owner_payments.history(999)['items']==[]
    assert resources.state(account)['credits_micro']==(3_000_000 if kind=='credits' and terminal=='permanent' else 5_000_000 if kind=='credits' else 0)


@pytest.mark.parametrize('kind',['credits','subscription','repayment'])
@pytest.mark.parametrize('terminal',['permanent','released'])
@pytest.mark.parametrize('provisional',['held','uncertain'])
def test_new_provisional_result_waits_for_matching_final_evidence(account,risk_source,kind,terminal,provisional):
    local,emit=risk_source;emit(terminal,2);frozen=snapshot(account,kind)
    assert emit(provisional,3)['pending'] and snapshot(account,kind)==frozen
    assert next(x for x in owner_payments.history(account)['items'] if x['id']==local)['financial_review_pending']
    emit(terminal,4)
    assert snapshot(account,kind)==frozen
    with auth.db() as c:assert journal.report(c)['pending']==0
    assert not next(x for x in owner_payments.history(account)['items'] if x['id']==local)['financial_review_pending']


@pytest.mark.parametrize('kind',['credits','subscription','repayment'])
@pytest.mark.parametrize('terminal',['permanent','released'])
def test_older_provisional_evidence_cannot_reopen_terminal_result(account,risk_source,kind,terminal):
    local,emit=risk_source;emit(terminal,2);frozen=snapshot(account,kind)
    assert not emit('held',1).get('pending') and snapshot(account,kind)==frozen
    with auth.db() as c:assert journal.report(c)['pending']==0
    assert not next(x for x in owner_payments.history(account)['items'] if x['id']==local)['financial_review_pending']
