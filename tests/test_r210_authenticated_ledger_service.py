"""Authenticated MockTransport contract tests, not provider sandbox certification."""
import copy

import httpx
import pytest
from app import auth, resource_accounts as r
from app import payment_reconcile_service as service
from app.regime_operation_fence import FenceBlocked
from test_r210_subscriptions import account as account  # noqa: F401
from test_r210_payment_reconciliation_e2e import purchase, snapshot


def transport(order,*,refunds=True,mutate=None):
    session={'id':'cs_test_'+order,'mode':'payment','status':'complete','payment_status':'paid','amount_total':500,
             'currency':'eur','client_reference_id':order,'metadata':{'mta_order':order},'payment_intent':'pi_test','livemode':False}
    intent={'id':'pi_test','status':'succeeded','amount':500,'amount_received':500,'currency':'eur','latest_charge':'ch_test','amount_capturable':0,'livemode':False}
    charge={'id':'ch_test','payment_intent':'pi_test','amount':500,'currency':'eur','paid':True,'captured':True,'amount_refunded':200 if refunds else 0,
            'amount_captured':500,'status':'succeeded','refunded':False,'disputed':False,'balance_transaction':'txn_charge',
            'failure_balance_transaction':None,'livemode':False}
    refund={'id':'re_first','charge':'ch_test','payment_intent':'pi_test','amount':200,'currency':'eur','status':'succeeded'}
    calls=[]
    def handle(request):
        assert request.method=='GET'
        assert request.headers['authorization']=='Bearer sk_test_test'
        path=request.url.path;calls.append(str(request.url))
        if path.endswith('/'+session['id']):body=copy.deepcopy(session)
        elif path.endswith('/pi_test'):body=copy.deepcopy(intent)
        elif path.endswith('/ch_test'):body=copy.deepcopy(charge)
        elif path.endswith('/charges'):body={'data':[copy.deepcopy(charge)],'has_more':False}
        elif path.endswith('/refunds/re_first'):body=copy.deepcopy(refund)
        elif path.endswith('/refunds'):
            body={'data':[refund] if refunds and not request.url.params.get('starting_after') else [],'has_more':bool(refunds and not request.url.params.get('starting_after'))}
        elif path.endswith('/disputes'):body={'data':[],'has_more':False}
        else:raise AssertionError(path)
        if mutate:body=mutate(path,body,request)
        return httpx.Response(200,json=body)
    return httpx.MockTransport(handle),calls


def test_authenticated_snapshot_journal_and_ledger_commit_together(account,monkeypatch):
    order=purchase(account,monkeypatch);mock,calls=transport(order)
    with httpx.Client(transport=mock) as client:
        result=service.reconcile_stripe(order,client=client)
        again=service.reconcile_stripe(order,client=client)
    assert result['ledger_reconciled'] and not result['transition_authorized']
    assert result['snapshot_digest']==again['snapshot_digest']
    assert r.state(account)['credits_micro']==3_000_000
    assert any('starting_after=re_first' in call for call in calls)
    with auth.db() as c:
        assert c.execute('SELECT count(*) FROM regime_financial_evidence').fetchone()[0]==1
    assert snapshot()['verified']


@pytest.mark.parametrize('failure',['currency','refund_identity','truncated','network','changed_order'])
def test_incomplete_or_changed_authenticated_history_never_credits(account,monkeypatch,failure):
    order=purchase(account,monkeypatch)
    def change(path,body,request):
        if path.endswith('/refunds'):
            if failure=='currency' and body['data']:body['data'][0]['currency']='usd'
            if failure=='refund_identity' and body['data']:body['data'][0]['charge']='ch_other'
            if failure=='truncated':body['has_more']=True;body['data']=[]
            if failure=='network':raise httpx.ReadTimeout('test timeout')
            if failure=='changed_order':
                with auth.db() as c:c.execute('UPDATE credit_purchase_orders SET amount_cents=1000 WHERE id=?',(order,))
        return body
    mock,_=transport(order,mutate=change)
    with httpx.Client(transport=mock) as client,pytest.raises((ValueError,FenceBlocked)):
        service.reconcile_stripe(order,client=client)
    assert r.state(account)['credits_micro']==0
    with auth.db() as c:
        assert c.execute("SELECT name FROM sqlite_master WHERE name='payment_reconciliation_events'").fetchone() is None


def test_refunded_legacy_ledger_without_matching_credit_is_blocked(account,monkeypatch):
    order=purchase(account,monkeypatch)
    with auth.db() as c:c.execute("UPDATE credit_purchase_orders SET status='paid' WHERE id=?",(order,))
    mock,_=transport(order,refunds=False)
    with httpx.Client(transport=mock) as client,pytest.raises(FenceBlocked,match='Legacy'):
        service.reconcile_stripe(order,client=client)
    assert r.state(account)['credits_micro']==0
