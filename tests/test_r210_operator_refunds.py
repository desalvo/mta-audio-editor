"""Actual refund services, authenticated provider contracts and durable SQLite.

No real merchant network or actual money movement. Provider transport is fake;
reconciliation, wallet/refund/receivable journals and operation fences are real.
"""
import copy
import json
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import parse_qs

import httpx
import pytest

from app import auth, operator_refunds as refunds, resource_accounts as resources
from app.regime_operation_fence import FenceBlocked
from test_r210_subscriptions import account as account, plan  # noqa: F401
from test_r210_payment_reconciliation_e2e import purchase
from test_r210_paypal import provider as provider  # noqa: F401


@pytest.fixture
def stripe_env(account,monkeypatch):
    order=purchase(account,monkeypatch);client_class=httpx.Client
    state={'order':order,'refunds':{},'posts':[],'gets':[],'post_status':'succeeded','timeout':False,'get_error':False,'post_error':False,'after_post':None}
    def handle(request):
        assert request.url.host=='api.stripe.com'
        assert request.headers['authorization']=='Bearer sk_test_test'
        path=request.url.path
        if request.method=='POST':
            assert path=='/v1/refunds';state['posts'].append(request)
            if state['post_error']:return httpx.Response(503,json={'error':{}})
            body=parse_qs(request.content.decode());assert set(body)=={'payment_intent','amount','metadata[mta_refund]'}
            token=body['metadata[mta_refund]'][0];assert request.headers['idempotency-key']==token
            doc={'id':'re_operator'+str(len(state['refunds'])+1),'object':'refund','payment_intent':body['payment_intent'][0],'charge':'ch_test','currency':'eur','amount':int(body['amount'][0]),'metadata':{'mta_refund':token},'status':state['post_status']}
            state['refunds'][doc['id']]=doc
            if state['after_post']:state['after_post'](doc)
            if state['timeout']:raise httpx.ReadTimeout('fake POST lost after remote execution')
            return httpx.Response(200,json=copy.deepcopy(doc))
        assert request.method=='GET';state['gets'].append(path)
        total=sum(x['amount'] for x in state['refunds'].values() if x['status']=='succeeded')
        if path.startswith('/v1/refunds/'):
            if state['get_error']:return httpx.Response(503,json={})
            body=state['refunds'].get(path.rsplit('/',1)[1]);return httpx.Response(200 if body else 404,json=copy.deepcopy(body or {}))
        if path.endswith('/cs_test_'+order):body={'id':'cs_test_'+order,'status':'complete','payment_status':'paid','amount_total':500,'currency':'eur','client_reference_id':order,'metadata':{'mta_order':order},'payment_intent':'pi_test'}
        elif path.endswith('/pi_test'):body={'id':'pi_test','status':'succeeded','amount':500,'amount_received':500,'currency':'eur','latest_charge':'ch_test'}
        elif path.endswith('/ch_test'):body={'id':'ch_test','payment_intent':'pi_test','amount':500,'currency':'eur','paid':True,'captured':True,'amount_refunded':total}
        elif path.endswith('/refunds'):body={'data':list(state['refunds'].values()),'has_more':False}
        elif path.endswith('/disputes'):body={'data':[],'has_more':False}
        else:raise AssertionError(path)
        return httpx.Response(200,json=copy.deepcopy(body))
    monkeypatch.setattr(refunds.httpx,'Client',lambda **kw:client_class(transport=httpx.MockTransport(handle),**kw))
    return state


def actor():return auth.find_user('admin')['id']


def body(order,*,provider='stripe',target='pi_test',amount=200,key='operator-refund-request-123'):
    return {'provider':provider,'order_id':order,'target':target,'amount_cents':amount,'reason':'Customer requested partial refund','request_id':key}


def create(env,**kw):return refunds.prepare(actor(),body(env['order'],**kw))


def audit():
    with auth.db() as c:return refunds.audit(c)


def current(identifier):return next(x for x in refunds.overview()['items'] if x['id']==identifier)


def test_actual_stripe_two_step_full_or_partial_funds_and_durable_fence(stripe_env,account):
    item=create(stripe_env);assert item['state']=='prepared' and not stripe_env['posts']
    assert resources.state(account)['credits_micro']==5_000_000
    assert audit()['pending']==1
    result=refunds.execute(actor(),item['id'],item['revision'])
    assert result['state']=='settled' and len(stripe_env['posts'])==1
    assert resources.state(account)['credits_micro']==3_000_000
    assert audit()=={'verified':True,'pending':0,'settled':1,'issues':[]}
    assert refunds.verify(actor(),item['id'],result['revision'])==result
    assert create(stripe_env)['state']=='settled' and len(stripe_env['posts'])==1
    second=create(stripe_env,amount=300,key='second-refund-request');assert refunds.execute(actor(),second['id'],0)['state']=='settled'
    assert resources.state(account)['credits_micro']==0 and audit()['settled']==2


@pytest.mark.parametrize('field,value',[('amount_cents',True),('amount_cents',0),('amount_cents',-1),('amount_cents',1.2),('amount_cents',1_000_000_001),('provider','other'),('order_id','../x'),('target',None),('reason','x'),('reason','bad\nreason'),('request_id','tiny')])
def test_bad_inputs_never_dispatch(stripe_env,field,value):
    bad=body(stripe_env['order']);bad[field]=value
    with pytest.raises(ValueError):refunds.prepare(actor(),bad)
    assert stripe_env['posts']==[]


@pytest.mark.parametrize('failure',['overamount','wrongtarget','unknownorder','extra','nonadmin','drain'])
def test_invalid_preparation_cannot_reserve_or_send(stripe_env,account,failure):
    bad=body(stripe_env['order']);uid=actor()
    if failure=='overamount':bad['amount_cents']=501
    if failure=='wrongtarget':bad['target']='pi_other'
    if failure=='unknownorder':bad['order_id']='missing'
    if failure=='extra':bad['currency']='EUR'
    if failure=='nonadmin':uid=account
    if failure=='drain':
        with auth.db() as c:c.execute('UPDATE regime_fence_state SET transitioning=1')
    with pytest.raises((ValueError,FenceBlocked)):refunds.prepare(uid,bad)
    assert stripe_env['posts']==[]


def test_cancel_only_prepared_and_conflicting_idempotency_rejected(stripe_env):
    item=create(stripe_env);assert create(stripe_env)==item
    with pytest.raises(FenceBlocked):create(stripe_env,amount=100)
    with pytest.raises(FenceBlocked):create(stripe_env,key='different-refund-key')
    cancelled=refunds.cancel(actor(),item['id'],0);assert cancelled['state']=='cancelled' and audit()['pending']==0
    with pytest.raises(FenceBlocked):refunds.execute(actor(),item['id'],cancelled['revision'])
    assert create(stripe_env,key='after-cancel-refund')['state']=='prepared'


@pytest.mark.parametrize('value',[None,True,-1,'0',1.2])
@pytest.mark.parametrize('action',['execute','verify','cancel'])
def test_exact_revision_required_before_action(stripe_env,value,action):
    item=create(stripe_env)
    with pytest.raises(ValueError):getattr(refunds,action)(actor(),item['id'],value)
    assert not stripe_env['posts']


def test_concurrent_preparations_reserve_once_and_concurrent_execution_sends_once(stripe_env):
    def prepare_one(i):
        try:return create(stripe_env,key='concurrent-request-'+str(i))
        except FenceBlocked:return None
    with ThreadPoolExecutor(max_workers=3) as pool:items=[x for x in pool.map(prepare_one,range(3)) if x]
    assert len(items)==1;item=items[0]
    def execute_one(_):
        try:return refunds.execute(actor(),item['id'],0)
        except FenceBlocked:return None
    with ThreadPoolExecutor(max_workers=3) as pool:results=list(pool.map(execute_one,range(3)))
    assert sum(x is not None for x in results)==1
    assert len(stripe_env['posts'])==1 and audit()['pending']==0


def test_timeout_and_process_restart_recover_by_exact_get_without_repost(stripe_env,account,monkeypatch):
    item=create(stripe_env);stripe_env['timeout']=True
    result=refunds.execute(actor(),item['id'],0);assert result['state']=='uncertain'
    # No timer, process/module reload, new request key or cancellation can undo uncertainty.
    monkeypatch.setattr(refunds.time,'time',lambda:4_000_000_000)
    with pytest.raises(FenceBlocked):refunds.execute(actor(),item['id'],result['revision'])
    with pytest.raises(FenceBlocked):refunds.cancel(actor(),item['id'],result['revision'])
    with pytest.raises(FenceBlocked):create(stripe_env,key='retry-with-new-key')
    with pytest.raises((ValueError,FenceBlocked)):refunds.verify(actor(),item['id'],result['revision'],'re_unknown')
    assert current(item['id'])['state']=='uncertain'
    rid=next(iter(stripe_env['refunds']))
    final=refunds.verify(actor(),item['id'],result['revision'],rid)
    assert final['state']=='settled' and len(stripe_env['posts'])==1
    assert resources.state(account)['credits_micro']==3_000_000


@pytest.mark.parametrize('status',['pending','requires_action','failed','canceled'])
def test_pending_and_failed_refunds_need_authenticated_terminal_outcome(stripe_env,account,status):
    item=create(stripe_env);stripe_env['post_status']=status
    result=refunds.execute(actor(),item['id'],0)
    assert result['state']==('failed' if status in ('failed','canceled') else 'pending')
    assert resources.state(account)['credits_micro']==5_000_000
    if result['state']=='pending':
        stripe_env['refunds'][result['provider_reference']]['status']='succeeded'
        result=refunds.verify(actor(),item['id'],result['revision']);assert result['state']=='settled'
        assert resources.state(account)['credits_micro']==3_000_000
    assert len(stripe_env['posts'])==1


@pytest.mark.parametrize('fault',['amount','currency','intent','metadata','status','id','object'])
def test_unrelated_or_malformed_provider_receipt_keeps_operation_open(stripe_env,fault):
    item=create(stripe_env);stripe_env['timeout']=True;result=refunds.execute(actor(),item['id'],0)
    rid=next(iter(stripe_env['refunds']));doc=stripe_env['refunds'][rid]
    key={'intent':'payment_intent'}.get(fault,fault)
    doc[key]={'amount':201,'currency':'usd','intent':'pi_other','metadata':{'mta_refund':'different'},'status':'unknown','id':'re_different','object':'charge'}[fault]
    with pytest.raises((ValueError,FenceBlocked)):refunds.verify(actor(),item['id'],result['revision'],rid)
    assert current(item['id'])['state']=='uncertain' and audit()['pending']==1
    assert len(stripe_env['posts'])==1


def test_quote_balance_and_merchant_changes_prevent_dispatch(stripe_env):
    from app import credit_purchases
    item=create(stripe_env);credit_purchases.settings({'secret_key':'sk_test_rotated'})
    with pytest.raises((ValueError,FenceBlocked)):refunds.execute(actor(),item['id'],0)
    assert stripe_env['posts']==[] and current(item['id'])['state']=='prepared'


def test_post_error_stays_uncertain_and_get_failure_stays_pending(stripe_env):
    item=create(stripe_env);stripe_env['post_error']=True
    result=refunds.execute(actor(),item['id'],0);assert result['state']=='uncertain' and len(stripe_env['posts'])==1
    assert audit()['pending']==1


def test_get_unavailable_after_post_does_not_repost_or_settle(stripe_env):
    item=create(stripe_env);stripe_env['get_error']=True
    with pytest.raises(ValueError):refunds.execute(actor(),item['id'],0)
    result=current(item['id']);assert result['state']=='pending' and result['provider_reference']
    stripe_env['get_error']=False
    assert refunds.verify(actor(),item['id'],result['revision'])['state']=='settled'
    assert len(stripe_env['posts'])==1


@pytest.mark.parametrize('tamper',['fence','event','state'])
def test_readiness_detects_inconsistent_refund_journal(stripe_env,tamper):
    item=create(stripe_env)
    from app.regime_reconciliation import combined_readiness
    with auth.db() as c:
        before=combined_readiness(c,current='COMMERCIAL',target='NON_COMMERCIAL')
        assert 'operator_refunds_pending' in before['unresolved']
        if tamper=='fence':c.execute('UPDATE regime_fence_operations SET status=? WHERE operation_id=?',('closed','operator-refund:'+item['id']))
        if tamper=='event':
            c.create_function('mta_operator_refund_erasure',1,lambda _:1)  # Explicit privileged fault injection.
            c.execute('DELETE FROM operator_refund_audit')
        if tamper=='state':c.execute("UPDATE operator_refunds SET state='failed' WHERE id=?",(item['id'],))
    assert not audit()['verified']


@pytest.fixture
def paypal_env(account,provider,monkeypatch):
    from app import paypal_payments as paypal
    plan(account);order=paypal.checkout(account,{'kind':'credits','amount_cents':500,'request_id':'refund-paypal-credit'})
    paypal.capture(account,order['order_id']);orders,_=provider;canonical=next(iter(orders.values()))
    capture=canonical['purchase_units'][0]['payments']['captures'][0]
    state={'order':order['order_id'],'target':capture['id'],'canonical':canonical,'refunds':{},'posts':[],'status':'COMPLETED','timeout':False}
    def api(cfg,method,path,payload=None,request_id=None):
        if method=='GET' and path.startswith('/v1/customer/disputes?'):return {'items':[],'links':[]}
        if method=='POST':
            assert path=='/v2/payments/captures/'+capture['id']+'/refund';state['posts'].append((path,payload,request_id));assert request_id==payload['custom_id'].removeprefix('mta-refund-')
            total=sum(paypal._cents(x['amount']) for x in state['refunds'].values() if x['status']=='COMPLETED')+paypal._cents(payload['amount'])
            rid='REFUND000'+str(len(state['refunds'])+1)
            doc={'id':rid,'status':state['status'],'amount':copy.deepcopy(payload['amount']),'custom_id':payload['custom_id'],'seller_payable_breakdown':{'total_refunded_amount':{'value':f'{total/100:.2f}','currency_code':'EUR'}},'links':[{'rel':'up','href':paypal.BASES['sandbox']+'/v2/payments/captures/'+capture['id']}]}
            state['refunds'][rid]=doc
            if doc['status']=='COMPLETED':capture['status']='REFUNDED' if total==500 else 'PARTIALLY_REFUNDED'
            canonical['purchase_units'][0]['payments']['refunds']=list(state['refunds'].values())
            if state['timeout']:raise ValueError('fake lost POST response')
            return copy.deepcopy(doc)
        assert method=='GET'
        if '/payments/refunds/' in path:return copy.deepcopy(state['refunds'][path.rsplit('/',1)[1]])
        if '/payments/captures/' in path:return copy.deepcopy(capture)
        assert path=='/v2/checkout/orders/'+canonical['id'];return copy.deepcopy(canonical)
    monkeypatch.setattr(paypal,'_api',api)
    return state


@pytest.mark.parametrize('amount',[200,500])
def test_paypal_canonical_refund_moves_real_wallet_once(paypal_env,account,amount):
    item=create(paypal_env,provider='paypal',target=paypal_env['target'],amount=amount)
    result=refunds.execute(actor(),item['id'],0);assert result['state']=='settled'
    assert resources.state(account)['credits_micro']==(500-amount)*10000
    assert len(paypal_env['posts'])==1 and audit()['pending']==0
    refunds.verify(actor(),item['id'],result['revision']);assert len(paypal_env['posts'])==1


def test_paypal_timeout_then_get_only_recovery(paypal_env):
    item=create(paypal_env,provider='paypal',target=paypal_env['target']);paypal_env['timeout']=True
    result=refunds.execute(actor(),item['id'],0);assert result['state']=='uncertain'
    result=refunds.verify(actor(),item['id'],result['revision'],next(iter(paypal_env['refunds'])))
    assert result['state']=='settled' and len(paypal_env['posts'])==1


@pytest.mark.parametrize('fault',['capture','custom_id','currency','amount','status','merchant'])
def test_paypal_wrong_receipt_or_merchant_never_closes(paypal_env,fault):
    from app import paypal_payments as paypal
    item=create(paypal_env,provider='paypal',target=paypal_env['target']);paypal_env['timeout']=True
    result=refunds.execute(actor(),item['id'],0);rid=next(iter(paypal_env['refunds']));doc=paypal_env['refunds'][rid]
    if fault=='capture':doc['links'][0]['href']=doc['links'][0]['href'].replace(paypal_env['target'],'WRONGCAPTURE')
    if fault=='custom_id':doc['custom_id']='wrong'
    if fault=='currency':doc['amount']['currency_code']='USD'
    if fault=='amount':doc['amount']['value']='3.00'
    if fault=='status':doc['status']='UNKNOWN'
    if fault=='merchant':paypal.settings({'client_secret':'rotated-secret'})
    with pytest.raises((ValueError,FenceBlocked)):refunds.verify(actor(),item['id'],result['revision'],rid)
    assert current(item['id'])['state']=='uncertain' and len(paypal_env['posts'])==1


def test_owner_history_privacy_and_admin_reason_not_disclosed(stripe_env,account):
    item=create(stripe_env);view=refunds.overview(owner=account)
    assert view['items'][0]['id']==item['id'] and view['total']==1
    assert refunds.overview(owner=actor())['items']==[]
    text=json.dumps(view);assert all(x not in text for x in ('Customer requested','mta-refund-','sk_test','context_json','actor_id','pi_test','provider_reference'))
