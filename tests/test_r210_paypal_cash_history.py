"""Actual DB/ledger and owner recovery; provider responses are isolated fixtures."""
import json

import pytest
from app import auth,paypal_payments as paypal,resource_accounts as resources
from app import paypal_cash_history as history,payment_reconcile_service as service,payment_reconciliation as journal
from app.regime_operation_fence import FenceBlocked
from test_r210_subscriptions import account as account  # noqa: F401
from test_r210_paypal import provider as provider  # noqa: F401
from test_r210_subscription_cash_lifecycle import cash_state as cash_state,final_dispute,rows,repay,stamp  # noqa: F401


def payout(state,monkeypatch,*,credit='1.00',items=True):
    doc=final_dispute(state,monkeypatch)
    doc['dispute_outcome']['outcome_code']='RESOLVED_WITH_PAYOUT'
    doc['money_movements']=[{'affected_party':'SELLER','type':'CREDIT','reason':'DISPUTE_SETTLEMENT',
        'amount':{'value':'2.00','currency_code':'EUR'},'initiated_time':stamp(state['start']+10)}]
    if not items:
        for tx in doc['disputed_transactions']:tx.pop('items',None)
    if credit:
        for index,cap in enumerate(state['doc']['purchase_units'][0]['payments']['captures']):
            state['rows'].append(state['movement']('ACTUALPAYOUT'+str(index),'T1202',credit,cap['id']))
    return doc


@pytest.mark.parametrize('cash_state',[{'kind':'credits'},{'kind':'credits','pending':True},{'kind':'credits','multi':True,'pending':True},{'kind':'credits','multi':True}],indirect=True)
def test_payout_cash_funds_exact_original_net_and_replays(cash_state,account,monkeypatch):
    state=cash_state;payout(state,monkeypatch,items=False)
    expected=3_000_000 if len(state['doc']['purchase_units'][0]['payments']['captures'])==2 else 4_000_000
    result=service.reconcile_checkout('paypal',state['order'],expected_owner=account)
    assert result['cash_net_minor']*10000==expected and not result['financial_review_pending']
    assert resources.state(account)['credits_micro']==expected
    for _ in range(2):service.reconcile_checkout('paypal',state['order'],expected_owner=account)
    assert resources.state(account)['credits_micro']==expected
    with auth.db() as c:
        report=journal.report(c)
        assert report['verified'] and report['pending']==0 and report['active_disputes']==0,report
        assert 'PRIVATE' not in json.dumps(history.position(c,c.execute('SELECT * FROM paypal_orders WHERE id=?',(state['order'],)).fetchone()))


@pytest.mark.parametrize('cash_state',[{}, {'pending':True}, {'multi':True,'pending':True}],indirect=True)
def test_payout_cash_allocates_original_fee_and_repayment_without_wallet(cash_state,account,provider,monkeypatch):
    state=cash_state;payout(state,monkeypatch,items=False)
    result=service.reconcile_checkout('paypal',state['order'],expected_owner=account)
    expected=(500-result['cash_net_minor'])*10000
    assert sum(x['due_micro'] for x in rows(account))==expected
    for index,source in enumerate(rows(account)):repay(account,source,'cash-payout-repayment-'+str(index))
    assert sum(x['due_micro'] for x in rows(account))==0 and resources.state(account)['credits_micro']==0


@pytest.mark.parametrize('problem',['pending_case','unknown_outcome','missing_debit','unsupported_movement','foreign_case','wrong_item_total','missing_case','changed_case','wrong_owner'])
@pytest.mark.parametrize('cash_state',[{'kind':'credits','pending':True,'multi':True}],indirect=True)
def test_unproved_cash_never_funds_or_clears_gap(cash_state,account,monkeypatch,problem):
    state=cash_state;doc=payout(state,monkeypatch,items=False)
    if problem=='pending_case':doc['status']='UNDER_REVIEW'
    if problem=='unknown_outcome':doc['dispute_outcome']['outcome_code']='NONE'
    if problem=='missing_debit':state['rows']=[x for x in state['rows'] if x['transaction_info']['transaction_event_code']!='T1201']
    if problem=='unsupported_movement':state['rows'][-1]['transaction_info']['transaction_event_code']='T9999'
    if problem=='foreign_case':doc['disputed_transactions'][0]['seller_transaction_id']='FOREIGN111'
    if problem=='wrong_item_total':
        for tx in doc['disputed_transactions']:tx['items']=[{'item_id':tx['seller_transaction_id'],'dispute_amount':{'value':'0.01','currency_code':'EUR'}}]
    if problem=='missing_case':
        from app.paypal_dispute_history import record_gap
        with auth.db() as c:order=dict(c.execute('SELECT * FROM paypal_orders WHERE id=?',(state['order'],)).fetchone());cfg=paypal._keys(c)
        record_gap(order,cfg,{'UNSEENCASE'})
    if problem=='changed_case':
        def hook(response,query):
            if len(state['reads'])==2:doc['dispute_amount']['value']='3.99'
        state['hook']=hook
    expected_owner=1 if problem=='wrong_owner' else account
    with pytest.raises((ValueError,FenceBlocked,KeyError)):service.reconcile_checkout('paypal',state['order'],expected_owner=expected_owner)
    assert resources.state(account)['credits_micro']==0
    with auth.db() as c:assert not history.has_receipt(c,state['order'])


@pytest.mark.parametrize('cash_state',[{'kind':'credits','pending':True},{'kind':'credits'}],indirect=True)
@pytest.mark.parametrize('credit',[None,'2.00'])
def test_final_payout_debit_or_complete_reimbursement_is_not_a_decision_guess(cash_state,account,monkeypatch,credit):
    state=cash_state;payout(state,monkeypatch,credit=credit)
    service.reconcile_checkout('paypal',state['order'],expected_owner=account)
    assert resources.state(account)['credits_micro']==(3_000_000 if credit is None else 5_000_000)


@pytest.mark.parametrize('problem',['permission','account','stale','duplicate','paging','currency','pending_movement','root_missing','fee_parent','temporary_hold','changed_scan'])
@pytest.mark.parametrize('cash_state',[{'kind':'credits','pending':True}],indirect=True)
def test_incomplete_reporting_does_not_expose_gross_wallet(cash_state,account,monkeypatch,problem):
    state=cash_state;payout(state,monkeypatch)
    if problem=='currency':state['rows'][-1]['transaction_info']['transaction_amount']['currency_code']='USD'
    if problem=='pending_movement':state['rows'][-1]['transaction_info']['transaction_status']='P'
    if problem=='root_missing':state['rows'].pop(0)
    if problem=='fee_parent':
        state['rows'].append(state['movement']('PROCESSORFEE111','T0106','-0.50'))
        state['rows'][-2]['transaction_info']['paypal_reference_id']='PROCESSORFEE111'
    if problem=='temporary_hold':state['rows'].append(state['movement']('OPENHOLD111','T1110','-1.00'))
    def hook(response,query):
        if problem=='permission':raise ValueError('Missing reporting permission')
        if problem=='account':response['account_number']='FOREIGN'
        if problem=='stale':response['last_refreshed_datetime']=stamp(state['start'])
        if problem=='duplicate':response['transaction_details'].append(response['transaction_details'][0]);response['total_items']+=1
        if problem=='paging':response['total_pages']+=1
        if problem=='changed_scan' and len(state['reads'])==2:response['transaction_details'][-1]['transaction_info']['transaction_amount']['value']='1.01'
    state['hook']=hook
    with pytest.raises((ValueError,FenceBlocked)):service.reconcile_checkout('paypal',state['order'],expected_owner=account)
    assert resources.state(account)['credits_micro']==0
    with auth.db() as c:assert not history.has_receipt(c,state['order'])


@pytest.mark.parametrize('drift',['owner','merchant','admission','journal'])
@pytest.mark.parametrize('cash_state',[{'kind':'credits','pending':True}],indirect=True)
def test_original_identity_and_evidence_checked_after_cash_io(cash_state,account,monkeypatch,drift):
    state=cash_state;payout(state,monkeypatch)
    def hook(response,query):
        if len(state['reads'])!=2:return
        with auth.db() as c:
            if drift=='owner':c.execute('UPDATE paypal_orders SET user_id=1 WHERE id=?',(state['order'],))
            if drift=='merchant':paypal.settings({'client_secret':'changed-after-read'})
            if drift=='admission':c.execute("UPDATE regime_fence_operations SET regime='NON_COMMERCIAL' WHERE operation_id=?",('checkout:paypal:'+state['order'],))
            if drift=='journal':
                from app.payment_reconciliation import record_event
                c.execute('BEGIN IMMEDIATE');value={'type':'capture_observation','order_id':state['order']}
                record_event(c,'paypal','concurrent-observation',history.cash._sha(value),value)
                c.execute("UPDATE payment_reconciliation_events SET order_id=? WHERE event_id='concurrent-observation'",(state['order'],))
    state['hook']=hook
    with pytest.raises((ValueError,FenceBlocked)):service.reconcile_checkout('paypal',state['order'],expected_owner=account)
    assert resources.state(account)['credits_micro']==0


@pytest.mark.parametrize('cash_state',[{'kind':'credits','pending':True}],indirect=True)
def test_sigkill_cash_and_first_funding_are_one_transaction(cash_state,account,monkeypatch):
    import os
    import signal
    if not hasattr(os,'fork'):pytest.skip('Requires actual POSIX SIGKILL')
    state=cash_state;payout(state,monkeypatch);original=history.CashContext.finalize
    def crash(*args):original(*args);os.kill(os.getpid(),signal.SIGKILL)
    child=os.fork()
    if child==0:
        try:
            history.CashContext.finalize=crash
            service.reconcile_checkout('paypal',state['order'],expected_owner=account)
        finally:os._exit(17)
    _,status=os.waitpid(child,0)
    assert os.WIFSIGNALED(status) and os.WTERMSIG(status)==signal.SIGKILL
    assert resources.state(account)['credits_micro']==0
    with auth.db() as c:assert not history.has_receipt(c,state['order'])
    service.reconcile_checkout('paypal',state['order'],expected_owner=account)
    assert resources.state(account)['credits_micro']==4_000_000


@pytest.mark.parametrize('cash_state',[{'kind':'credits'}],indirect=True)
def test_later_reimbursement_updates_original_wallet_and_current_proof(cash_state,account,monkeypatch):
    state=cash_state;payout(state,monkeypatch);service.reconcile_checkout('paypal',state['order'],expected_owner=account)
    state['rows'].append(state['movement']('SECONDREIMBURSE111','T1205','1.00'));state['clock'][0]+=4*3600
    service.reconcile_checkout('paypal',state['order'],expected_owner=account)
    assert resources.state(account)['credits_micro']==5_000_000
    with auth.db() as c:assert journal.report(c)['verified']


@pytest.mark.parametrize('cash_state',[{'kind':'credits','pending':True}],indirect=True)
def test_cash_funding_concurrency_never_duplicates_wallet(cash_state,account,monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    state=cash_state;payout(state,monkeypatch);state['concurrent']=True
    def run(_):
        try:return service.reconcile_checkout('paypal',state['order'],expected_owner=account)
        except FenceBlocked:return None  # Original evidence changed; explicit retry is safe.
    with ThreadPoolExecutor(max_workers=4) as pool:results=list(pool.map(run,range(4)))
    assert any(results)
    service.reconcile_checkout('paypal',state['order'],expected_owner=account)
    assert resources.state(account)['credits_micro']==4_000_000
    with auth.db() as c:assert journal.report(c)['verified']


def test_partial_payout_on_paid_repayment_reopens_only_its_original_debt(cash_state,account,provider,monkeypatch):
    from test_r210_original_subscription_loss import reverse
    state=cash_state;reverse(state['cid'],'5.00','original-full-loss-for-payout')
    payment=repay(account,rows(account)[0],'payout-original-repayment')['order_id']
    with auth.db() as c:
        pid=c.execute('SELECT provider_order FROM paypal_orders WHERE id=?',(payment,)).fetchone()[0]
        cid=c.execute('SELECT id FROM paypal_captures WHERE order_id=?',(payment,)).fetchone()[0]
    doc=provider[0][pid];doc['purchase_units'][0]['payee']={'merchant_id':'MERCHANT123'}
    root=state['movement'](cid,'T0006','5.00',pid);root['transaction_info']['paypal_reference_id_type']='ODR'
    state['rows'][:]=[root]
    target={**state,'order':payment,'pid':pid,'doc':doc,'cid':cid}
    payout(target,monkeypatch)
    service.reconcile_checkout('paypal',payment,expected_owner=account)
    assert rows(account)[0]['due_micro']==1_000_000 and len(rows(account))==1
    assert resources.state(account)['credits_micro']==0
    repay(account,rows(account)[0],'remaining-debt-after-payout')
    assert rows(account)[0]['due_micro']==0 and len(rows(account))==1


@pytest.mark.parametrize('cash_state',[{'kind':'credits','pending':True}],indirect=True)
def test_owner_http_private_verify_closes_payout_and_hides_provider_data(cash_state,account,monkeypatch):
    from fastapi.testclient import TestClient
    from app import main,owner_payments
    from test_r210_legal_documents import cookie
    state=cash_state;payout(state,monkeypatch)
    monkeypatch.setattr(main,'NATIVE_SINGLE_USER',False);monkeypatch.setattr(main,'check_basic_auth',lambda _:False)
    monkeypatch.delenv('MTA_ALLOW_INSECURE_NO_AUTH',raising=False)
    web=TestClient(main.app);url='/api/account/payments/paypal/'+state['order']+'/verify';body={'confirm':True};headers={'X-MTA-Request':'1'}
    assert web.post(url,json=body,headers=headers).status_code==401
    web.cookies.update(cookie(auth.find_user('admin')['id']));assert web.post(url,json=body,headers=headers).status_code in (400,409,422)
    assert not state['reads']
    web.cookies.update(cookie(account));assert web.post(url,json=body).status_code==403
    response=web.post(url,json=body,headers=headers);assert response.status_code==200,response.text
    assert not owner_payments.history(account)['items'][0]['financial_review_pending']
    assert resources.state(account)['credits_micro']==4_000_000
    assert 'test-secret' not in response.text and 'PRIVATE' not in response.text


@pytest.mark.parametrize('cash_state',[{'kind':'credits'}],indirect=True)
def test_cash_case_and_movement_binding_corruption_cannot_refund_or_restore(cash_state,account,monkeypatch):
    state=cash_state;payout(state,monkeypatch);service.reconcile_checkout('paypal',state['order'],expected_owner=account)
    with auth.db() as c:c.execute("UPDATE payment_reconciliation_objects SET order_id='FOREIGN' WHERE object_id='cash-case:PP-D-CASH-123'")
    state['rows'].append(state['movement']('LATERPROTECTION111','T1202','1.00'));state['clock'][0]+=4*3600
    with pytest.raises((ValueError,FenceBlocked)):service.reconcile_checkout('paypal',state['order'],expected_owner=account)
    assert resources.state(account)['credits_micro']==4_000_000


@pytest.mark.parametrize('cash_state',[{'kind':'credits'}],indirect=True)
def test_authenticated_later_refund_invalidates_cash_until_complete_readback(cash_state,account,monkeypatch):
    from test_r210_subscription_cash_lifecycle import completed_refund
    state=cash_state;payout(state,monkeypatch);service.reconcile_checkout('paypal',state['order'],expected_owner=account)
    completed_refund(state);state['clock'][0]+=4*3600
    service.reconcile_checkout('paypal',state['order'],expected_owner=account)
    assert resources.state(account)['credits_micro']==3_000_000
    with auth.db() as c:assert journal.report(c)['verified']


@pytest.mark.parametrize('cash_state',[{'kind':'credits'}],indirect=True)
def test_cash_payment_graph_erasure_removes_proofs_and_unique_claims(cash_state,account,monkeypatch,tmp_path):
    from app import account_lifecycle as life,account_erasure,ai_arranger_runtime
    monkeypatch.setattr(ai_arranger_runtime,'_ROOT',tmp_path/'payout-private-queue')
    monkeypatch.setattr(auth,'send_mail',lambda *a,**kw:None)
    state=cash_state;payout(state,monkeypatch);service.reconcile_checkout('paypal',state['order'],expected_owner=account)
    actor=auth.find_user('admin')['id'];life.register(account);life.retire(account,actor)
    assert account_erasure.erase(account,actor,confirmed=True)['done']
    with auth.db() as c:
        for query in ('SELECT count(*) FROM payment_reconciliation_events WHERE order_id=?',
                      'SELECT count(*) FROM payment_reconciliation_objects WHERE order_id=?',
                      'SELECT count(*) FROM payment_reconciliation_positions WHERE order_id=?'):
            assert c.execute(query,(state['order'],)).fetchone()[0]==0


@pytest.mark.parametrize('lost_response',[False,True])
@pytest.mark.parametrize('cash_state',[{'kind':'credits'}],indirect=True)
def test_protected_payout_operator_refund_waits_for_cash_and_never_reposts(cash_state,account,monkeypatch,lost_response):
    import copy
    from app import operator_refunds as refunds
    state=cash_state;payout(state,monkeypatch,credit='2.00')
    service.reconcile_checkout('paypal',state['order'],expected_owner=account)
    state['doc']['intent']='CAPTURE';original=paypal._api;posts=[]
    def api(cfg,method,path,payload=None,request_id=None):
        if method=='POST' and path=='/v2/payments/captures/'+state['cid']+'/refund':
            posts.append(path)
            obj={'id':'PAYOUTREFUND111','status':'COMPLETED','amount':copy.deepcopy(payload['amount']),
                 'custom_id':payload['custom_id'],'seller_payable_breakdown':{'total_refunded_amount':copy.deepcopy(payload['amount'])},
                 'links':[{'rel':'up','href':'https://api-m.sandbox.paypal.com/v2/payments/captures/'+state['cid']}]}
            state['refunds'][obj['id']]=obj
            payments=state['doc']['purchase_units'][0]['payments'];payments['refunds']=[copy.deepcopy(obj)]
            payments['captures'][0]['status']='PARTIALLY_REFUNDED'
            row=state['movement'](obj['id'],'T1107','-1.00')
            row['transaction_info']['transaction_initiation_date']=stamp(state['clock'][0])
            row['transaction_info']['transaction_updated_date']=stamp(state['clock'][0]+1)
            state['rows'].append(row)
            if lost_response:raise ValueError('Lost real-test refund response')
            return obj
        return original(cfg,method,path,payload,request_id)
    monkeypatch.setattr(paypal,'_api',api);actor=auth.find_user('admin')['id']
    item=refunds.prepare(actor,{'provider':'paypal','order_id':state['order'],'target':state['cid'],
         'amount_cents':100,'reason':'Refund protected original payment','request_id':'payout-operator-once'})
    result=refunds.execute(actor,item['id'],item['revision'])
    assert result['state']==('uncertain' if lost_response else 'pending') and len(posts)==1
    state['clock'][0]+=4*3600
    result=refunds.verify(actor,item['id'],result['revision'])
    assert result['state']=='settled' and len(posts)==1
    assert refunds.verify(actor,item['id'],result['revision'])['state']=='settled' and len(posts)==1
    assert resources.state(account)['credits_micro']==4_000_000
    with auth.db() as c:assert journal.report(c)['verified']


@pytest.mark.parametrize('cash_state',[{'kind':'credits'}],indirect=True)
def test_later_signed_case_replay_requires_cash_refresh_without_duplicate_money(cash_state,account,monkeypatch):
    from test_r210_paypal_reconciliation_e2e import HEADERS
    state=cash_state;payout(state,monkeypatch);service.reconcile_checkout('paypal',state['order'],expected_owner=account)
    event={'id':'later-canonical-payout-event','event_type':'CUSTOMER.DISPUTE.UPDATED','resource':{'dispute_id':'PP-D-CASH-123'}}
    result=paypal.webhook(json.dumps(event).encode(),HEADERS)
    assert result.get('pending')
    with pytest.raises(ValueError,match='coverage is not yet fresh'):
        service.reconcile_checkout('paypal',state['order'],expected_owner=account)
    state['clock'][0]+=4*3600
    service.reconcile_checkout('paypal',state['order'],expected_owner=account)
    assert resources.state(account)['credits_micro']==4_000_000
    assert paypal.webhook(json.dumps(event).encode(),HEADERS).get('duplicate')
    assert resources.state(account)['credits_micro']==4_000_000


@pytest.mark.parametrize('cash_state',[{'kind':'credits'}],indirect=True)
def test_multiple_final_cases_conserve_original_cash_without_assigning_guessed_payouts(cash_state,account,monkeypatch):
    import copy
    from urllib.parse import urlsplit,parse_qs
    state=cash_state;first=payout(state,monkeypatch)
    second=copy.deepcopy(first);second['dispute_id']='PP-D-SECOND';second['dispute_amount']['value']='1.00'
    second['dispute_outcome']['outcome_code']='RESOLVED_BUYER_FAVOUR';second.pop('money_movements')
    second['disputed_transactions'][0]['items'][0]['dispute_amount']['value']='1.00'
    original=paypal._api
    def api(cfg,method,path,*args):
        if path=='/v1/customer/disputes/PP-D-SECOND':return copy.deepcopy(second)
        if path.startswith('/v1/customer/disputes?') and parse_qs(urlsplit(path).query)['disputed_transaction_id']==[state['cid']]:
            return {'items':[{k:copy.deepcopy(d[k]) for k in ('dispute_id','status','update_time','dispute_amount')} for d in (first,second)],'links':[]}
        return original(cfg,method,path,*args)
    monkeypatch.setattr(paypal,'_api',api)
    state['rows'].append(state['movement']('SECONDCASELOSS111','T1201','-1.00'))
    service.reconcile_checkout('paypal',state['order'],expected_owner=account)
    assert resources.state(account)['credits_micro']==3_000_000
    with auth.db() as c:
        report=journal.report(c);assert report['verified'] and report['active_disputes']==0
        proof=history.position(c,c.execute('SELECT * FROM paypal_orders WHERE id=?',(state['order'],)).fetchone())
        assert len(proof['cases'])==2 and proof['net_minor']==300


@pytest.mark.parametrize('cash_state',[{'kind':'credits','pending':True,'multi':True}],indirect=True)
def test_unallocated_case_cannot_disappear_after_exact_original_cash_proof(cash_state,account,monkeypatch):
    state=cash_state;payout(state,monkeypatch,items=False)
    service.reconcile_checkout('paypal',state['order'],expected_owner=account)
    original=paypal._api
    def api(cfg,method,path,*args):
        if path.startswith('/v1/customer/disputes?'):return {'items':[],'links':[]}
        return original(cfg,method,path,*args)
    monkeypatch.setattr(paypal,'_api',api)
    state['clock'][0]+=4*3600
    with pytest.raises(FenceBlocked,match='previously proved case'):
        service.reconcile_checkout('paypal',state['order'],expected_owner=account)
    assert resources.state(account)['credits_micro']==3_000_000
