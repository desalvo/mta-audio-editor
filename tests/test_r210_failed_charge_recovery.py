"""Canonical GET failed-charge history -> immutable terminal proof -> admission."""
import copy
import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor

import httpx
import pytest
from app import auth, credit_purchases as shop, resource_accounts as resources
from app import payment_reconcile_service as service
from app.regime_operation_fence import FenceBlocked
from test_r210_subscriptions import account as account  # noqa: F401
from test_r210_payment_reconciliation_e2e import purchase
from test_r210_terminal_checkout_e2e import assert_closed
from test_r210_owner_payments import client


def failed_history(account, monkeypatch, *, count=2, complete=False):
    local=purchase(account,monkeypatch)
    session={'id':'cs_test_'+local,'mode':'payment','status':'complete' if complete else 'expired','payment_status':'unpaid',
             'amount_total':500,'currency':'eur','client_reference_id':local,'metadata':{'mta_order':local},'payment_intent':'pi_failed'}
    intent={'id':'pi_failed','status':'canceled','amount':500,'currency':'eur','amount_received':0,
            'amount_capturable':0,'latest_charge':'ch_failed_0','livemode':False,'client_secret':'PRIVATE_SECRET'}
    charges=[{'id':'ch_failed_'+str(i),'payment_intent':'pi_failed','amount':500,'currency':'eur','status':'failed',
              'paid':False,'captured':False,'amount_captured':0,'amount_refunded':0,'refunded':False,'disputed':False,
              'balance_transaction':None,'failure_balance_transaction':None,'livemode':False,
              'failure_message':'PRIVATE_DECLINE','billing_details':{'email':'private@example.test'}} for i in range(count)]
    state={'session':session,'intent':intent,'charges':charges,'mutation':None,'page_size':1};calls=[]
    def handle(request):
        assert request.method=='GET' and request.headers['authorization']=='Bearer sk_test_test'
        calls.append(str(request.url));path=request.url.path
        if path.endswith('/'+session['id']):document=state['session']
        elif path.endswith('/pi_failed'):document=state['intent']
        elif path=='/v1/charges':
            assert request.url.params['payment_intent']=='pi_failed'
            after=request.url.params.get('starting_after');start=0 if not after else next(i+1 for i,x in enumerate(charges) if x['id']==after)
            end=start+state['page_size'];document={'data':charges[start:end],'has_more':end<len(charges)}
        else:
            identifier=path.rsplit('/',1)[1];document=next(x for x in charges if x['id']==identifier)
        document=copy.deepcopy(document)
        if state['mutation']:document=state['mutation'](request,document,calls)
        return httpx.Response(200,json=document)
    return local,state,httpx.MockTransport(handle),calls


@pytest.mark.parametrize('complete',[False,True])
def test_paginated_failed_charges_close_idempotently_without_money(account,monkeypatch,complete):
    local,state,mock,calls=failed_history(account,monkeypatch,complete=complete)
    with httpx.Client(transport=mock) as remote:
        first=service.reconcile_stripe(local,client=remote,expected_owner=account)
        assert service.reconcile_stripe(local,client=remote,expected_owner=account)['duplicate']
    assert first['checkout_closed'] and first['outcome']==('canceled_intent' if complete else 'expired')
    assert any('starting_after=ch_failed_0' in call for call in calls)
    assert_closed(local,'stripe',account)
    with auth.db() as c:
        encoded=c.execute("SELECT normalized_json FROM payment_reconciliation_events WHERE event_id LIKE 'terminal:%'").fetchone()[0]
        proof=json.loads(encoded)['failed_charge_proof'];assert len(proof['charges'])==2
        assert all(value not in encoded for value in ('PRIVATE_SECRET','PRIVATE_DECLINE','private@example.test'))
        assert c.execute("SELECT count(*) FROM payment_reconciliation_objects WHERE provider='stripe'").fetchone()[0]==4
    assert shop.checkout(account,500,'next-after-failed-closure')['checkout_url']


@pytest.mark.parametrize('field,value',[
    ('status','pending'),('status','succeeded'),('paid',True),('paid',0),('captured',True),('captured',0),
    ('amount_captured',1),('amount_captured',False),('amount_refunded',1),('amount_refunded',False),
    ('refunded',True),('disputed',True),('balance_transaction','txn_money'),('failure_balance_transaction','txn_failed'),
    ('amount',499),('amount',True),('currency','usd'),('payment_intent','pi_other'),('livemode',True),('id','pi_not_charge')])
def test_nonempty_ambiguous_or_monetary_history_stays_blocked(account,monkeypatch,field,value):
    local,state,mock,_=failed_history(account,monkeypatch);state['charges'][0][field]=value
    with httpx.Client(transport=mock) as remote,pytest.raises(ValueError):service.reconcile_stripe(local,client=remote)
    pending(local,account)


def pending(local,uid,*,guard=True):
    with auth.db() as c:
        assert c.execute('SELECT status FROM credit_purchase_orders WHERE id=?',(local,)).fetchone()[0]=='pending'
        assert c.execute('SELECT status FROM regime_fence_operations WHERE operation_id=?',('checkout:stripe:'+local,)).fetchone()[0]=='open'
        assert c.execute("SELECT name FROM sqlite_master WHERE name='checkout_terminal_receipts'").fetchone() is None
    assert resources.state(uid)['credits_micro']==0
    if guard:
        with pytest.raises(FenceBlocked):shop.checkout(uid,500,'fresh-while-proof-blocked')


@pytest.mark.parametrize('field',['id','status','paid','captured','amount_captured','amount_refunded','balance_transaction','failure_balance_transaction','refunded','disputed','livemode'])
def test_missing_evidence_is_not_zero(account,monkeypatch,field):
    local,state,mock,_=failed_history(account,monkeypatch);state['charges'][0].pop(field)
    with httpx.Client(transport=mock) as remote,pytest.raises((ValueError,KeyError)):service.reconcile_stripe(local,client=remote)
    pending(local,account)


@pytest.mark.parametrize('failure',['canonical','second_list','intent','owner','config','duplicate','latest_missing','intent_environment','truncated','timeout','not_found','over_bound'])
def test_changed_incomplete_or_unavailable_snapshots_never_clear(account,monkeypatch,failure):
    local,state,mock,_=failed_history(account,monkeypatch);reads=[]
    if failure=='latest_missing':state['intent']['latest_charge']='ch_unknown'
    if failure=='intent_environment':state['intent']['livemode']=True
    if failure=='duplicate':state['charges'][1]=copy.deepcopy(state['charges'][0])
    if failure=='over_bound':state['page_size']=100;state['charges'][:]=[dict(state['charges'][0],id='ch_failed_'+str(i)) for i in range(101)]
    def mutate(request,document,calls):
        path=request.url.path
        if path=='/v1/charges':
            reads.append(path)
            if failure=='second_list' and len(reads)==3:document['data'][0]['amount_captured']=1
            if failure=='truncated':return {'data':[],'has_more':True}
        if path.endswith('/ch_failed_0'):
            if failure=='canonical':document['amount_captured']=1
            if failure=='owner':
                with auth.db() as c:c.execute('UPDATE credit_purchase_orders SET user_id=1 WHERE id=?',(local,))
            if failure=='config':shop.settings({'secret_key':'sk_test_rotated'})
            if failure=='timeout':raise httpx.ReadTimeout('test timeout')
            if failure=='not_found':raise httpx.HTTPStatusError('test 404',request=request,response=httpx.Response(404))
        if failure=='intent' and path.endswith('/pi_failed') and len(reads)>0:document['amount_received']=1
        return document
    state['mutation']=mutate
    with httpx.Client(transport=mock) as remote,pytest.raises((ValueError,FenceBlocked,httpx.HTTPError)):
        service.reconcile_stripe(local,client=remote,expected_owner=account)
    pending(local,account,guard=failure!='owner')


def test_owner_http_confirm_get_proof_and_atomic_rollback_retry(account,monkeypatch):
    from app import regime_checkout_fence
    local,_,mock,calls=failed_history(account,monkeypatch);api=client(account,monkeypatch)
    def reconcile(provider,order_id,*,expected_owner):
        with httpx.Client(transport=mock) as remote:return service.reconcile_stripe(order_id,client=remote,expected_owner=expected_owner)
    monkeypatch.setattr(service,'reconcile_checkout',reconcile)
    url='/api/account/payments/stripe/'+local+'/verify';headers={'X-MTA-Request':'1'}
    assert api.post(url,headers=headers,json={'confirm':False}).status_code==422 and not calls
    original=regime_checkout_fence.settle_if_enrolled
    def crash(*args):raise RuntimeError('test transaction failure')
    monkeypatch.setattr(regime_checkout_fence,'settle_if_enrolled',crash)
    with pytest.raises(RuntimeError):api.post(url,headers=headers,json={'confirm':True})
    pending(local,account)
    monkeypatch.setattr(regime_checkout_fence,'settle_if_enrolled',original)
    assert api.post(url,headers=headers,json={'confirm':True}).json()=={'verified':True}
    assert_closed(local,'stripe',account)
    data=api.get('/api/account/payments').json();assert not data['credit_checkout_pending']
    assert data['items'][0]['status']=='cancelled' and data['items'][0]['checkout_url'] is None


def test_concurrent_readbacks_commit_one_private_proof(account,monkeypatch):
    local,_,mock,_=failed_history(account,monkeypatch)
    def verify(_):
        with httpx.Client(transport=mock) as remote:return service.reconcile_stripe(local,client=remote,expected_owner=account)
    with ThreadPoolExecutor(max_workers=3) as pool:results=list(pool.map(verify,range(3)))
    assert all(result['checkout_closed'] for result in results)
    with auth.db() as c:
        assert c.execute('SELECT count(*) FROM checkout_terminal_receipts').fetchone()[0]==1
        assert c.execute("SELECT count(*) FROM payment_reconciliation_events WHERE event_id LIKE 'terminal:%'").fetchone()[0]==1


@pytest.mark.parametrize('tamper',['object','amount','journal'])
def test_readiness_detects_broken_private_failed_proof(account,monkeypatch,tamper):
    from app import payment_reconciliation as journal
    local,_,mock,_=failed_history(account,monkeypatch)
    with httpx.Client(transport=mock) as remote:service.reconcile_stripe(local,client=remote)
    with auth.db() as c:
        assert journal.report(c)['verified']
        if tamper=='object':c.execute("DELETE FROM payment_reconciliation_objects WHERE object_id='ch_failed_0'")
        elif tamper=='amount':c.execute('UPDATE credit_purchase_orders SET amount_cents=1000 WHERE id=?',(local,))
        else:
            with pytest.raises(sqlite3.IntegrityError,match='Immutable'):
                c.execute("UPDATE payment_reconciliation_events SET normalized_json='{}' WHERE event_id LIKE 'terminal:%'")
            # Simulate a corrupted imported database after proving the live guard.
            c.execute('DROP TRIGGER payment_events_immutable_payload')
            c.execute("UPDATE payment_reconciliation_events SET normalized_json='{}' WHERE event_id LIKE 'terminal:%'")
        report=journal.report(c)
        assert not report['verified'] and 'terminal_checkout_receipt_mismatch' in report['issues']


def test_late_authenticated_payment_stays_pending_and_cannot_overwrite_proof(account,monkeypatch):
    from test_r210_credit_checkout import signed,paid_event
    from app import payment_reconciliation as journal
    local,_,mock,_=failed_history(account,monkeypatch)
    with httpx.Client(transport=mock) as remote:service.reconcile_stripe(local,client=remote)
    result=shop.event(*signed(paid_event(local)))
    assert result['pending'] and result['conflict'] and resources.state(account)['credits_micro']==0
    with auth.db() as c:
        assert journal.report(c)['pending']==1
        assert c.execute('SELECT status FROM credit_purchase_orders WHERE id=?',(local,)).fetchone()[0]=='cancelled'
    with httpx.Client(transport=mock) as remote,pytest.raises(FenceBlocked):service.reconcile_stripe(local,client=remote)


def test_failed_proof_cannot_adopt_another_orders_charge_binding(account,monkeypatch):
    from app import payment_reconciliation as journal
    local,_,mock,_=failed_history(account,monkeypatch)
    with auth.db() as c:
        c.execute('BEGIN IMMEDIATE');journal.initialize(c)
        journal.bind_object(c,'stripe','ch_failed_0','legacy-other-order')
    with httpx.Client(transport=mock) as remote,pytest.raises(FenceBlocked):service.reconcile_stripe(local,client=remote)
    pending(local,account)


def test_signed_async_failure_resolves_only_with_canonical_complete_history(account,monkeypatch):
    from test_r210_credit_checkout import signed
    from app import payment_reconciliation as journal
    local,state,mock,_=failed_history(account,monkeypatch,complete=True)
    payload={'id':'evt_failed_before_terminal','type':'checkout.session.async_payment_failed','data':{'object':state['session']}}
    assert shop.event(*signed(payload))['pending']
    with auth.db() as c:assert journal.report(c)['pending']==1
    with httpx.Client(transport=mock) as remote:service.reconcile_stripe(local,client=remote)
    assert_closed(local,'stripe',account)


def test_admin_reconciliation_uses_same_private_failed_charge_proof(account,monkeypatch):
    local,_,mock,reads=failed_history(account,monkeypatch)
    def reconcile(provider,order_id,*,expected_owner=None):
        assert provider=='stripe' and order_id==local and expected_owner is None
        with httpx.Client(transport=mock) as remote:return service.reconcile_stripe(order_id,client=remote)
    monkeypatch.setattr(service,'reconcile_checkout',reconcile)
    url='/api/admin/service-regime/reconcile-payment';headers={'X-MTA-Request':'1'}
    body={'provider':'stripe','order_id':local}
    assert client(account,monkeypatch).post(url,headers=headers,json=body).status_code==403
    admin=client(1,monkeypatch)
    assert admin.post(url,json=body).status_code==403
    assert admin.post(url,headers=headers,json={**body,'observation':{}}).status_code==422
    assert not reads
    response=admin.post(url,headers=headers,json=body)
    assert response.status_code==200 and response.json()['checkout_closed']
    assert 'failed_charge_proof' not in response.json() and 'PRIVATE_' not in response.text
    assert_closed(local,'stripe',account)
