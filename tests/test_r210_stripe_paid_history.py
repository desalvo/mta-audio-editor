"""Known paid intent: real ledger/API, bounded GET readback and webhook races."""
import copy
import json
import sqlite3
from collections import Counter

import httpx
import pytest

from app import auth, credit_purchases as shop, resource_accounts as resources
from app import payment_reconcile_service as service
from app.regime_operation_fence import FenceBlocked
from test_r210_subscriptions import account as account  # noqa: F401
from test_r210_payment_reconciliation_e2e import purchase, dispute
from test_r210_credit_checkout import signed, paid_event
from test_r210_owner_payments import client as web_client


@pytest.fixture
def history(account, monkeypatch):
    local = purchase(account, monkeypatch)
    session = {'id':'cs_test_'+local,'mode':'payment','status':'complete','payment_status':'paid','amount_total':500,
               'currency':'eur','client_reference_id':local,'metadata':{'mta_order':local,'private':'PRIVATE_METADATA'},
               'payment_intent':'pi_test','livemode':False,'customer_email':'PRIVATE_CUSTOMER'}
    intent = {'id':'pi_test','status':'succeeded','amount':500,'amount_received':500,'amount_capturable':0,
              'currency':'eur','latest_charge':'ch_test','livemode':False,'client_secret':'PRIVATE_SECRET'}
    charge = {'id':'ch_test','payment_intent':'pi_test','amount':500,'amount_captured':500,'currency':'eur',
              'status':'succeeded','paid':True,'captured':True,'amount_refunded':200,'refunded':False,
              'disputed':False,'balance_transaction':'txn_paid','failure_balance_transaction':None,'livemode':False}
    failed = {**charge,'id':'ch_prior','status':'failed','paid':False,'captured':False,'amount_captured':0,
              'amount_refunded':0,'balance_transaction':None,'billing_details':{'email':'PRIVATE_CUSTOMER'}}
    refund = {'id':'re_test','charge':'ch_test','payment_intent':'pi_test','amount':200,'currency':'eur','status':'succeeded'}
    state = {'session':session,'intent':intent,'charges':[charge,failed],'refunds':[refund],
             'disputes':[],'mutate':None,'calls':Counter(),'page_size':100}

    def handle(request):
        assert request.method=='GET' and request.url.host=='api.stripe.com'
        assert request.headers['authorization']=='Bearer sk_test_test'
        # Provider I/O never owns an accounting write transaction.
        with sqlite3.connect(auth.db_path(), timeout=0) as connection:
            connection.execute('BEGIN IMMEDIATE')
            connection.rollback()
        path=request.url.path;state['calls'][path]+=1
        if path=='/v1/checkout/sessions/'+session['id']:body=copy.deepcopy(state['session'])
        elif path=='/v1/payment_intents/pi_test':body=copy.deepcopy(state['intent'])
        else:
            parts=path.split('/');kind=parts[2]
            assert kind in ('charges','refunds','disputes'),path
            if len(parts)==4:
                body=copy.deepcopy(next(x for x in state[kind] if x['id']==parts[3]))
            else:
                expected={'payment_intent':'pi_test'} if kind=='charges' else {'charge':'ch_test'}
                for key,value in expected.items():assert request.url.params[key]==value
                rows=state[kind];cursor=request.url.params.get('starting_after')
                start=next(i+1 for i,x in enumerate(rows) if x['id']==cursor) if cursor else 0
                chunk=rows[start:start+state['page_size']]
                body={'data':copy.deepcopy(chunk),'has_more':start+len(chunk)<len(rows)}
        if state['mutate']:state['mutate'](path,body,state['calls'][path])
        return httpx.Response(200,json=body)
    state['transport']=httpx.MockTransport(handle)
    return local,state


def reconcile(history):
    local,state=history
    with httpx.Client(transport=state['transport']) as remote:
        return service.reconcile_stripe(local,client=remote)


def accounting():
    with auth.db() as c:
        names={x[0] for x in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        return {table:[tuple(x) for x in c.execute(query)] if table in names else None for table,query in {
            'resource_credits':'SELECT * FROM resource_credits ORDER BY id',
            'payment_reconciliation_events':'SELECT * FROM payment_reconciliation_events ORDER BY provider,event_id',
            'regime_financial_evidence':'SELECT * FROM regime_financial_evidence ORDER BY evidence_id',
            'credit_purchase_orders':'SELECT * FROM credit_purchase_orders ORDER BY id'}.items()}


def test_paginated_attempt_ancestry_refund_and_private_receipt_are_idempotent(history,account):
    history[1]['page_size']=1
    first=reconcile(history);before=accounting()
    assert reconcile(history)['snapshot_digest']==first['snapshot_digest']
    assert accounting()==before and resources.state(account)['credits_micro']==3_000_000
    assert first['ledger_reconciled'] and not first['transition_authorized']
    assert history[1]['calls']['/v1/charges']==8  # Two pages, two passes, two invocations.
    assert history[1]['calls']['/v1/charges/ch_prior']==4
    assert 'PRIVATE' not in json.dumps(before)
    with auth.db() as c:
        receipt=json.loads(c.execute('SELECT observed_json FROM regime_financial_evidence').fetchone()[0])
    assert receipt['known_paid_history']['failed_attempts'][0]['id']=='ch_prior'
    assert receipt['known_paid_history']['refunds'][0]['amount']==200


@pytest.mark.parametrize('status,expected',[('needs_response',2_000_000),('won',3_000_000),('lost',2_000_000)])
def test_exact_refund_and_dispute_preserve_actual_wallet(history,account,status,expected):
    state=history[1];state['charges'][0]['disputed']=True
    state['disputes']=[{'id':'dp_test','charge':'ch_test','payment_intent':'pi_test','amount':100,'currency':'eur','status':status}]
    reconcile(history)
    assert resources.state(account)['credits_micro']==expected
    before=accounting();reconcile(history);assert accounting()==before


@pytest.mark.parametrize('kind,field,value',[
    ('session','livemode',True),('session','amount_total',500.0),('session','payment_intent','ch_wrong'),
    ('intent','amount_received',True),('intent','amount_capturable',1),('intent','latest_charge','ch_missing'),
    ('intent','livemode',True),('charge','paid',1),('charge','amount_captured',499),('charge','refunded',True),
    ('charge','disputed',True),('charge','failure_balance_transaction','txn_failure'),
    ('charge','balance_transaction',None),('charge','livemode',True),
    ('prior','paid',True),('prior','status','pending'),('prior','amount_captured',1),
    ('prior','failure_balance_transaction','txn_failure'),('prior','payment_intent','pi_other'),
    ('refund','status','pending'),('refund','payment_intent','pi_other'),('refund','amount',True),
])
def test_contradictory_ancestry_never_changes_financial_records(history,kind,field,value):
    state=history[1]
    target={'session':state['session'],'intent':state['intent'],'charge':state['charges'][0],
            'prior':state['charges'][1],'refund':state['refunds'][0]}[kind]
    target[field]=value;before=accounting()
    with pytest.raises(ValueError):reconcile(history)
    assert accounting()==before


@pytest.mark.parametrize('change',['missing_success','duplicate_attempt','extra_success','missing_field','empty_disputed',
                                    'refund_missing','detail_conflict','timeout','second_pass','late_webhook'])
def test_changed_or_missing_provider_history_is_atomic(history,account,change):
    state=history[1]
    if change=='missing_success':state['charges'].pop(0)
    elif change=='duplicate_attempt':state['charges'].append(copy.deepcopy(state['charges'][0]))
    elif change=='extra_success':state['charges'][1].update(status='succeeded',paid=True)
    elif change=='missing_field':state['charges'][0].pop('amount_captured')
    elif change=='empty_disputed':state['charges'][0]['disputed']=True
    elif change=='refund_missing':state['refunds']=[]
    def mutate(path,body,count):
        if change=='detail_conflict' and path=='/v1/refunds/re_test':body['amount']=100
        if change=='timeout' and path=='/v1/refunds/re_test':raise httpx.ReadTimeout('isolated fixture')
        if change=='second_pass' and path=='/v1/charges/ch_prior' and count==2:body['status']='pending'
        if change=='late_webhook' and path=='/v1/refunds' and count==2:
            shop.event(*signed(dispute('lost',200,'evt_concurrent')))
    state['mutate']=mutate
    before=accounting()
    with pytest.raises((ValueError,httpx.HTTPError,FenceBlocked)):reconcile(history)
    after=accounting()
    if change=='late_webhook':
        assert after['resource_credits']==before['resource_credits']
        assert after['regime_financial_evidence']==before['regime_financial_evidence']
        assert len(after['payment_reconciliation_events'])==1
    else:assert after==before
    assert resources.state(account)['credits_micro']==0


@pytest.mark.parametrize('actor',['owner','admin'])
def test_actual_confirmed_api_refuses_unstable_then_recovers_original_payment(history,account,monkeypatch,actor):
    local,state=history;uid=account if actor=='owner' else auth.find_user('admin')['id']
    web=web_client(uid,monkeypatch)
    def invoke(provider,order_id,*,expected_owner=None):
        assert provider=='stripe' and order_id==local
        with httpx.Client(transport=state['transport']) as remote:
            return service.reconcile_stripe(order_id,client=remote,expected_owner=expected_owner)
    monkeypatch.setattr(service,'reconcile_checkout',invoke)
    path=('/api/account/payments/stripe/'+local+'/verify' if actor=='owner' else '/api/admin/service-regime/reconcile-payment')
    body={'confirm':True} if actor=='owner' else {'provider':'stripe','order_id':local}
    assert web.post(path,json=body).status_code==403
    state['charges'][1]['amount_captured']=1
    assert web.post(path,json=body,headers={'X-MTA-Request':'1'}).status_code==(409 if actor=='owner' else 422)
    assert resources.state(account)['credits_micro']==0
    state['charges'][1]['amount_captured']=0
    for _ in range(2):assert web.post(path,json=body,headers={'X-MTA-Request':'1'}).status_code==200
    assert resources.state(account)['credits_micro']==3_000_000


def test_signed_hold_during_readback_cannot_be_overwritten_by_old_won_snapshot(history,account):
    local,state=history;shop.event(*signed(paid_event(local)))
    state['charges'][0]['disputed']=True
    state['disputes']=[{'id':'dp_test','charge':'ch_test','payment_intent':'pi_test','amount':500,'currency':'eur','status':'won'}]
    def mutate(path,body,count):
        if path=='/v1/disputes/dp_test' and count==2:
            shop.event(*signed(dispute('under_review',200,'evt_hold_during_read')))
    state['mutate']=mutate
    with pytest.raises(FenceBlocked,match='journal changed'):reconcile(history)
    assert resources.state(account)['credits_micro']==0
    with auth.db() as c:
        assert c.execute("SELECT status FROM payment_reconciliation_disputes WHERE dispute_id='dp_test'").fetchone()[0]=='under_review'
        assert not c.execute("SELECT 1 FROM sqlite_master WHERE name='regime_financial_evidence'").fetchone()


def test_two_individually_valid_passes_with_different_money_are_refused(history):
    state=history[1]
    def mutate(path,body,count):
        if path.startswith('/v1/checkout/sessions/') and count==3:
            state['charges'][0]['amount_refunded']=100
            state['refunds'][0]['amount']=100
    state['mutate']=mutate;before=accounting()
    with pytest.raises(ValueError,match='history changed'):reconcile(history)
    assert accounting()==before


def test_nonfinancial_customer_changes_do_not_pollute_snapshot_or_block_replay(history):
    def mutate(path,body,count):
        body['unrelated_customer_note']='PRIVATE NOTE '+str(count)
        if path.startswith('/v1/checkout/sessions/'):
            body['metadata']['unrelated']='PRIVATE '+str(count)
    history[1]['mutate']=mutate
    first=reconcile(history);before=accounting()
    assert reconcile(history)['snapshot_digest']==first['snapshot_digest']
    assert accounting()==before and 'PRIVATE' not in json.dumps(before)


@pytest.mark.parametrize('change',['appearing_charge','changed_intent','environment','webhook'])
def test_empty_canceled_intent_requires_stable_readback_and_journal(account,monkeypatch,change):
    from test_r210_terminal_checkout_e2e import stripe_fixture, assert_closed
    local,session,intent,mock,calls=stripe_fixture(account,monkeypatch,intent=True)
    original=mock.handler
    counts=Counter()
    def handler(request):
        response=original(request);body=response.json();path=request.url.path;counts[path]+=1
        if change=='appearing_charge' and path=='/v1/charges' and counts[path]==2:
            body={'data':[{'id':'ch_appeared'}],'has_more':False}
        if change=='changed_intent' and path=='/v1/payment_intents/pi_terminal' and counts[path]==2:
            body['latest_charge']='ch_changed'
        if change=='environment' and path=='/v1/payment_intents/pi_terminal':body['livemode']=True
        if change=='webhook' and path.endswith(session['id']) and counts[path]==2:
            event=dispute('needs_response',200,'evt_empty_race')
            event['data']['object']['payment_intent']='pi_terminal'
            shop.event(*signed(event))
        return httpx.Response(200,json=body)
    with httpx.Client(transport=httpx.MockTransport(handler)) as remote,pytest.raises((ValueError,FenceBlocked)):
        service.reconcile_stripe(local,client=remote)
    with auth.db() as c:
        assert c.execute('SELECT status FROM credit_purchase_orders WHERE id=?',(local,)).fetchone()[0]=='pending'
        assert not c.execute("SELECT 1 FROM sqlite_master WHERE name='checkout_terminal_receipts'").fetchone()
    if change=='webhook':
        with httpx.Client(transport=mock) as remote,pytest.raises(FenceBlocked):
            service.reconcile_stripe(local,client=remote)
        return  # Signed conflicting risk must stay pending for independent review.
    with httpx.Client(transport=mock) as remote:
        assert service.reconcile_stripe(local,client=remote)['checkout_closed']
    assert_closed(local,'stripe',account)


@pytest.mark.parametrize('limit',['requests','deadline'])
def test_entire_readback_budget_stops_before_any_ledger_write(history,monkeypatch,limit):
    from app import stripe_paid_history as paid
    before=accounting()
    if limit=='requests':monkeypatch.setattr(paid.ReadbackBudget,'MAX_READS',3)
    else:
        clock=[0.0]
        monkeypatch.setattr(paid,'monotonic',lambda:clock[0])
        def expire(path,body,count):clock[0]=61.0
        history[1]['mutate']=expire
    with pytest.raises(ValueError):reconcile(history)
    assert accounting()==before
    assert sum(history[1]['calls'].values()) <= (3 if limit=='requests' else 1)


@pytest.mark.parametrize('mode',['subscription','setup'])
def test_wrong_checkout_mode_is_not_a_credit_purchase(history,mode):
    history[1]['session']['mode']=mode;before=accounting()
    with pytest.raises(ValueError):reconcile(history)
    assert accounting()==before


def test_paid_receipt_wallet_and_inbox_roll_back_together_after_local_failure(history,account,monkeypatch):
    from app import regime_checkout_fence
    original=regime_checkout_fence.settle_if_enrolled
    def fail(*args):raise RuntimeError('isolated post-credit failure')
    monkeypatch.setattr(regime_checkout_fence,'settle_if_enrolled',fail)
    before=accounting()
    with pytest.raises(RuntimeError):reconcile(history)
    assert accounting()==before
    monkeypatch.setattr(regime_checkout_fence,'settle_if_enrolled',original)
    assert reconcile(history)['ledger_reconciled']
    assert resources.state(account)['credits_micro']==3_000_000
