"""Original partial loss -> exact cash proof -> repayment -> excess refund."""
import copy
from datetime import datetime,timezone
import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import parse_qs,urlsplit

import pytest
from app import auth,paypal_payments as paypal,resource_accounts as resources
from app import payment_reconcile_service as service,subscription_receivables as debts
from app import subscription_cash_reconciliation as cash
from app.regime_operation_fence import FenceBlocked
from test_r210_subscriptions import account as account,plan  # noqa: F401
from test_r210_paypal import provider as provider  # noqa: F401
from test_r210_paypal_reconciliation_e2e import HEADERS
from test_r210_original_subscription_loss import reverse,repay,rows


def stamp(value):return datetime.fromtimestamp(value,timezone.utc).isoformat(timespec='seconds').replace('+00:00','Z')


@pytest.fixture
def cash_state(account,provider,monkeypatch,request):
    options=getattr(request,'param',{});clock=[1802822400]
    monkeypatch.setattr(cash.time,'time',lambda:clock[0])
    kind=options.get('kind','subscription')
    initial=plan(account,**({'price_micro':options.get('fee',5_000_000)} if kind=='subscription' else {}))
    body={'kind':'subscription','period_start':initial['period']['start']} if kind=='subscription' else {'kind':'credits','amount_cents':500}
    local=paypal.checkout(account,{**body,'request_id':'cash-original-quote'})['order_id']
    pid=next(iter(provider[0]));doc=paypal._api({},'POST','/v2/checkout/orders/'+pid+'/capture')
    if options.get('multi'):
        doc['purchase_units'][0]['payments']['captures']=[{'id':'CAPTURE111','status':'COMPLETED','amount':{'value':'3.00','currency_code':'EUR'}},
                                                       {'id':'CAPTURE222','status':'COMPLETED','amount':{'value':'2.00','currency_code':'EUR'}}]
    if not options.get('pending'):paypal.fulfill(local,copy.deepcopy(doc))
    doc['purchase_units'][0]['payee']={'merchant_id':'MERCHANT123'}
    captures=doc['purchase_units'][0]['payments']['captures'];cid=captures[0]['id']
    start=clock[0]
    def movement(identifier,code,value,reference=None):
        return {'transaction_info':{'transaction_id':identifier,'transaction_event_code':code,'transaction_status':'S',
            'transaction_amount':{'currency_code':'EUR','value':value},'paypal_reference_id':reference or cid,
            'paypal_reference_id_type':'ODR' if identifier in {x['id'] for x in captures} else 'TXN',
            'transaction_initiation_date':stamp(start+1),'transaction_updated_date':stamp(start+2),
            'transaction_subject':'PRIVATE SUBJECT','fee_amount':{'currency_code':'EUR','value':'-9.99'}}}
    records=[movement(x['id'],'T0006',x['amount']['value'],pid) for x in captures]
    state={'order':local,'pid':pid,'doc':doc,'cid':cid,'clock':clock,'rows':records,'movement':movement,'reads':[],
           'hook':None,'refunds':{},'start':start,'concurrent':False}
    original=paypal._api
    def api(cfg,method,path,*args):
        if path.startswith('/v2/payments/refunds/') and path.rsplit('/',1)[1] in state['refunds']:
            return copy.deepcopy(state['refunds'][path.rsplit('/',1)[1]])
        if path.startswith('/v1/reporting/transactions?'):
            assert method=='GET'
            if not state['concurrent']:
                # A competing transaction may own a lock in the concurrency
                # test. Serial tests prove this call owns none during I/O.
                with sqlite3.connect(auth.db_path(),timeout=0) as connection:
                    connection.execute('BEGIN IMMEDIATE');connection.rollback()
            query=parse_qs(urlsplit(path).query);state['reads'].append(query)
            assert set(query)=={'start_date','end_date','fields','balance_affecting_records_only','page_size','page'}
            assert query['fields']==['transaction_info'] and query['balance_affecting_records_only']==['Y']
            page=int(query['page'][0]);left=cash._instant(query['start_date'][0]);right=cash._instant(query['end_date'][0])
            selected=[x for x in state['rows'] if left<=cash._instant(x['transaction_info']['transaction_initiation_date'])<=right]
            response={'page':page,'total_pages':max(1,(len(selected)+99)//100),'total_items':len(selected),
                'transaction_details':copy.deepcopy(selected[(page-1)*100:page*100]),'account_number':'MERCHANT123',
                'start_date':query['start_date'][0],'end_date':query['end_date'][0],
                'last_refreshed_datetime':stamp(clock[0])}
            if state['hook']:state['hook'](response,query)
            return response
        return original(cfg,method,path,*args)
    monkeypatch.setattr(paypal,'_api',api)
    return state


def lose(state,amount='1.00'):
    reverse(state['cid'],amount,'cash-partial-reversal')
    state['rows'].append(state['movement']('LOSSMOVEMENT111','T1106','-'+amount))
    state['clock'][0]+=4*3600


def reconcile(state,account):return service.reconcile_checkout('paypal',state['order'],expected_owner=account)


def completed_refund(state,amount='1.00',identifier='CASHREFUND111'):
    obj={'id':identifier,'status':'COMPLETED','amount':{'currency_code':'EUR','value':amount},
         'seller_payable_breakdown':{'total_refunded_amount':{'currency_code':'EUR','value':amount}},
         'links':[{'rel':'up','href':'https://api-m.sandbox.paypal.com/v2/payments/captures/'+state['cid']}]}
    state['refunds'][identifier]=obj
    payments=state['doc']['purchase_units'][0]['payments'];payments['refunds']=[copy.deepcopy(obj)]
    payments['captures'][0]['status']='PARTIALLY_REFUNDED'
    state['rows'].append(state['movement'](identifier,'T1107','-'+amount))
    event={'id':'cash-refund-event-'+identifier,'event_type':'PAYMENT.CAPTURE.REFUNDED','resource':obj}
    return paypal.webhook(json.dumps(event).encode(),HEADERS)


@pytest.mark.parametrize('cash_state',[{}, {'multi':True}],indirect=True)
def test_partial_loss_cash_proof_creates_exact_original_debt_and_repayment(cash_state,account,provider):
    state=cash_state;fees=resources.transactions(account)['subscription_fees'];lose(state)
    assert rows(account)==[]
    result=reconcile(state,account)
    assert result['original_subscription_loss_reconciled'] and result['fee_loss_micro']==1_000_000
    source=rows(account)[0];assert source['due_micro']==source['amount_micro']==1_000_000
    repay(account,source,'cash-partial-repayment')
    assert rows(account)[0]['due_micro']==0 and resources.state(account)['credits_micro']==0
    assert resources.transactions(account)['subscription_fees']==fees
    with auth.db() as c:
        assert debts.original_loss_review(c)['verified']
        receipt=cash.position(c,c.execute('SELECT * FROM paypal_orders WHERE id=?',(state['order'],)).fetchone())
        assert 'PRIVATE' not in json.dumps(receipt) and '9.99' not in json.dumps(receipt)


def test_cash_reimbursement_makes_already_paid_repayment_refundable(cash_state,account,provider):
    state=cash_state;lose(state);reconcile(state,account)
    paid=repay(account,rows(account)[0],'cash-before-reimbursement')['order_id']
    state['rows'].append(state['movement']('CREDITMOVEMENT111','T1202','1.00'))
    state['clock'][0]+=4*3600;reconcile(state,account)
    source=rows(account)[0]
    assert source['original_amount_micro']==1_000_000 and source['amount_micro']==source['due_micro']==0
    assert source['payments'][0]['refund_due_micro']==1_000_000
    with auth.db() as c:
        assert c.execute('SELECT refund_due_micro FROM paypal_orders WHERE id=?',(paid,)).fetchone()[0]==1_000_000
    assert resources.state(account)['credits_micro']==0


def test_partial_loss_and_separate_refund_use_exact_distinct_cash_movements(cash_state,account,provider):
    state=cash_state;lose(state);reconcile(state,account)
    assert rows(account)[0]['due_micro']==1_000_000
    assert completed_refund(state)['received']
    with pytest.raises(ValueError,match='verified original evidence'):
        paypal.checkout(account,{'kind':'subscription_reversal','refund_id':rows(account)[0]['refund_id'],
                               'expected_due_micro':1_000_000,'request_id':'stale-cash-cannot-collect'})
    state['clock'][0]+=4*3600;reconcile(state,account)
    assert sum(x['due_micro'] for x in rows(account))==2_000_000
    for index,source in enumerate(rows(account)):repay(account,source,'cash-overlap-repay-'+str(index))
    assert sum(x['due_micro'] for x in rows(account))==0
    assert sum(x['amount_micro'] for x in rows(account))==2_000_000
    assert resources.state(account)['credits_micro']==0


def test_reduced_loss_preserves_already_paid_second_source_without_new_collection(cash_state,account,provider):
    state=cash_state;lose(state);reconcile(state,account)
    state['rows'].append(state['movement']('LOSSMOVEMENT222','T1201','-1.00'))
    state['clock'][0]+=4*3600;reconcile(state,account)
    assert len(rows(account))==2
    repay(account,rows(account)[1],'second-source-paid-first')
    state['rows'].append(state['movement']('CREDITMOVEMENT222','T1202','1.00'))
    state['clock'][0]+=4*3600;reconcile(state,account)
    assert sum(x['due_micro'] for x in rows(account))==0
    assert sum(x['covered_micro'] for x in rows(account))==1_000_000
    assert sum(p['refund_due_micro'] for x in rows(account) for p in x['payments'])==0


@pytest.mark.parametrize('cash_state',[{'fee':5_000_001}],indirect=True)
def test_partial_cash_loss_preserves_micro_fee_and_both_refund_surpluses(cash_state,account,provider):
    state=cash_state;lose(state,'0.01');reconcile(state,account)
    assert rows(account)[0]['due_micro']==1
    paid=repay(account,rows(account)[0],'cash-micro-original-fee')['order_id']
    state['rows'].append(state['movement']('CREDITMOVEMENT111','T1202','0.01'))
    state['clock'][0]+=4*3600;reconcile(state,account)
    assert rows(account)[0]['due_micro']==0
    with auth.db() as c:
        assert c.execute('SELECT refund_due_micro FROM paypal_orders WHERE id=?',(state['order'],)).fetchone()[0]==9999
        assert c.execute('SELECT refund_due_micro FROM paypal_orders WHERE id=?',(paid,)).fetchone()[0]==10000


def test_provider_fees_never_increase_customer_principal(cash_state,account):
    state=cash_state;lose(state)
    state['rows'].append(state['movement']('FEE111','T0106','-9.99'))
    reconcile(state,account)
    assert rows(account)[0]['due_micro']==1_000_000


@pytest.mark.parametrize('lost_response',[False,True])
def test_reimbursed_original_loss_excess_is_refunded_once_through_operator_flow(cash_state,account,provider,monkeypatch,lost_response):
    from app import operator_refunds as refunds
    state=cash_state;lose(state);reconcile(state,account)
    paid=repay(account,rows(account)[0],'cash-excess-final-refund')['order_id']
    state['rows'].append(state['movement']('CREDITMOVEMENT111','T1202','1.00'))
    state['clock'][0]+=4*3600;reconcile(state,account)
    with auth.db() as c:
        pid=c.execute('SELECT provider_order FROM paypal_orders WHERE id=?',(paid,)).fetchone()[0]
        cid=c.execute('SELECT id FROM paypal_captures WHERE order_id=?',(paid,)).fetchone()[0]
        assert c.execute('SELECT refund_due_micro FROM paypal_orders WHERE id=?',(paid,)).fetchone()[0]==1_000_000
    doc=provider[0][pid];doc['intent']='CAPTURE';original=paypal._api;posts=[]
    def api(cfg,method,path,payload=None,request_id=None):
        if method=='POST' and path=='/v2/payments/captures/'+cid+'/refund':
            posts.append(path)
            receipt={'id':'EXCESSREFUND111','status':'COMPLETED','amount':copy.deepcopy(payload['amount']),
                'custom_id':payload['custom_id'],'seller_payable_breakdown':{'total_refunded_amount':copy.deepcopy(payload['amount'])},
                'links':[{'rel':'up','href':'https://api-m.sandbox.paypal.com/v2/payments/captures/'+cid}]}
            state['refunds'][receipt['id']]=receipt
            doc['purchase_units'][0]['payments']['captures'][0]['status']='REFUNDED'
            doc['purchase_units'][0]['payments']['refunds']=[copy.deepcopy(receipt)]
            if lost_response:raise ValueError('Lost excess refund POST response')
            return receipt
        return original(cfg,method,path,payload,request_id)
    monkeypatch.setattr(paypal,'_api',api)
    actor=auth.find_user('admin')['id']
    item=refunds.prepare(actor,{'provider':'paypal','order_id':paid,'target':cid,'amount_cents':100,
         'reason':'Return repayment after original principal reimbursed','request_id':'cash-excess-operator-refund'})
    result=refunds.execute(actor,item['id'],item['revision'])
    if lost_response:
        assert result['state']=='uncertain'
        result=refunds.verify(actor,item['id'],result['revision'])
    assert result['state']=='settled' and len(posts)==1
    assert refunds.verify(actor,item['id'],result['revision'])['state']=='settled' and len(posts)==1
    assert rows(account)[0]['due_micro']==0
    assert rows(account)[0]['payments'][0]['refund_due_micro']==0
    assert resources.state(account)['credits_micro']==0


def test_exact_repeated_cash_scan_is_economically_and_journal_idempotent(cash_state,account):
    state=cash_state;lose(state);reconcile(state,account)
    with auth.db() as c:before=[tuple(x) for x in c.execute("SELECT * FROM payment_reconciliation_events ORDER BY provider,event_id")]
    state['clock'][0]+=3600;reconcile(state,account)
    with auth.db() as c:
        assert [tuple(x) for x in c.execute("SELECT * FROM payment_reconciliation_events ORDER BY provider,event_id")]==before
    assert len(rows(account))==1 and rows(account)[0]['due_micro']==1_000_000


@pytest.mark.parametrize('problem',['permission','account','stale','missing','duplicate','pagination','changed','currency','pending','unknown_code','wrong_reference_type','positive_loss','over_loss','temporary_hold'])
def test_unverified_cash_never_creates_a_partial_loss_debt(cash_state,account,problem):
    state=cash_state;lose(state)
    if problem=='currency':state['rows'][1]['transaction_info']['transaction_amount']['currency_code']='USD'
    if problem=='pending':state['rows'][1]['transaction_info']['transaction_status']='P'
    if problem=='unknown_code':state['rows'][1]['transaction_info']['transaction_event_code']='T9999'
    if problem=='wrong_reference_type':state['rows'][1]['transaction_info']['paypal_reference_id_type']='ODR'
    if problem=='positive_loss':state['rows'][1]['transaction_info']['transaction_amount']['value']='1.00'
    if problem=='over_loss':state['rows'][1]['transaction_info']['transaction_amount']['value']='-6.00'
    if problem=='temporary_hold':state['rows'][1]['transaction_info']['transaction_event_code']='T1110'
    def hook(response,query):
        if problem=='permission':raise ValueError('Reporting permission denied')
        if problem=='account':response['account_number']='FOREIGN'
        if problem=='stale':response['last_refreshed_datetime']=stamp(state['start'])
        if problem=='missing':response['transaction_details'].pop();response['total_items']-=1
        if problem=='duplicate':response['transaction_details'].append(copy.deepcopy(response['transaction_details'][0]));response['total_items']+=1
        if problem=='pagination':response['total_items']+=1
        if problem=='changed' and len(state['reads'])==2:response['transaction_details'][1]['transaction_info']['transaction_amount']['value']='-2.00'
    state['hook']=hook
    with pytest.raises((ValueError,FenceBlocked)):reconcile(state,account)
    assert rows(account)==[] and resources.state(account)['credits_micro']==0


def test_reporting_lag_cannot_collect_recently_observed_loss(cash_state,account):
    state=cash_state;lose(state);state['clock'][0]-=3*3600
    with pytest.raises(ValueError,match='freshness'):reconcile(state,account)
    assert not state['reads'] and rows(account)==[]


def test_owner_http_can_resolve_partial_loss_without_cross_owner_or_csrf_access(cash_state,account,monkeypatch):
    from fastapi.testclient import TestClient
    from app import main,owner_payments
    from test_r210_legal_documents import cookie
    state=cash_state;lose(state)
    assert owner_payments.history(account)['items'][0]['financial_review_pending']
    monkeypatch.setattr(main,'NATIVE_SINGLE_USER',False);monkeypatch.setattr(main,'check_basic_auth',lambda _:False)
    monkeypatch.delenv('MTA_ALLOW_INSECURE_NO_AUTH',raising=False)
    web=TestClient(main.app);url='/api/account/payments/paypal/'+state['order']+'/verify';body={'confirm':True};headers={'X-MTA-Request':'1'}
    assert web.post(url,json=body,headers=headers).status_code==401
    web.cookies.update(cookie(auth.find_user('admin')['id']))
    assert web.post(url,json=body,headers=headers).status_code in (400,409,422)
    assert not state['reads']
    web.cookies.update(cookie(account));assert web.post(url,json=body).status_code==403
    response=web.post(url,json=body,headers=headers)
    assert response.status_code==200,response.text
    assert rows(account)[0]['due_micro']==1_000_000
    assert not owner_payments.history(account)['items'][0]['financial_review_pending']


def test_concurrent_original_cash_recovery_only_creates_one_debt(cash_state,account):
    state=cash_state;lose(state);state['concurrent']=True
    with ThreadPoolExecutor(max_workers=4) as pool:
        results=list(pool.map(lambda _:reconcile(state,account),range(4)))
    assert all(x['original_subscription_loss_reconciled'] for x in results)
    assert len(rows(account))==1 and rows(account)[0]['due_micro']==1_000_000


@pytest.mark.parametrize('change',['owner','merchant','journal','basis'])
def test_identity_or_evidence_drift_during_cash_readback_cannot_collect(cash_state,account,change):
    state=cash_state;lose(state)
    def hook(response,query):
        if len(state['reads'])!=2:return
        with auth.db() as c:
            if change=='owner':c.execute('UPDATE paypal_orders SET user_id=1 WHERE id=?',(state['order'],))
            if change=='merchant':paypal.settings({'client_secret':'rotated-during-cash-history'})
            if change=='journal':
                from app.payment_reconciliation import record_event
                c.execute('BEGIN IMMEDIATE')
                record_event(c,'paypal','concurrent-cash-gap','b'*64,{'type':'paypal_history_gap','order_id':state['order']})
                c.execute("UPDATE payment_reconciliation_events SET order_id=? WHERE event_id='concurrent-cash-gap'",(state['order'],))
            if change=='basis':
                c.execute('DROP TRIGGER subscription_payment_basis_immutable_update')
                c.execute('UPDATE subscription_payment_basis SET fee_micro=fee_micro-1,surplus_micro=surplus_micro+1 WHERE order_id=?',(state['order'],))
    state['hook']=hook
    with pytest.raises((ValueError,FenceBlocked)):reconcile(state,account)
    with auth.db() as c:assert c.execute('SELECT count(*) FROM paypal_subscription_reversals').fetchone()[0]==0


def test_failure_after_cash_claim_rolls_back_receipt_and_debt(cash_state,account,monkeypatch):
    state=cash_state;lose(state);original=debts.accrue_original_loss
    def fail(*args):original(*args);raise RuntimeError('after cash-backed allocation')
    monkeypatch.setattr(debts,'accrue_original_loss',fail)
    with pytest.raises(RuntimeError,match='after cash-backed allocation'):reconcile(state,account)
    with auth.db() as c:
        assert c.execute('SELECT count(*) FROM paypal_subscription_reversals').fetchone()[0]==0
        assert not cash.has_receipt(c,state['order'])
    monkeypatch.setattr(debts,'accrue_original_loss',original);reconcile(state,account)
    assert rows(account)[0]['due_micro']==1_000_000


def final_dispute(state,monkeypatch):
    captures=state['doc']['purchase_units'][0]['payments']['captures']
    doc={'dispute_id':'PP-D-CASH-123','status':'RESOLVED','update_time':stamp(state['start']+10),
         'dispute_amount':{'value':str(2*len(captures))+'.00','currency_code':'EUR'},
         'dispute_outcome':{'outcome_code':'RESOLVED_BUYER_FAVOUR'},
         'disputed_transactions':[{'seller_transaction_id':x['id'],'gross_amount':x['amount'],
            'items':[{'item_id':'item-'+x['id'],'dispute_amount':{'value':'2.00','currency_code':'EUR'}}]} for x in captures]}
    original=paypal._api
    def api(cfg,method,path,*args):
        if path.startswith('/v1/customer/disputes?'):
            cid=parse_qs(urlsplit(path).query)['disputed_transaction_id'][0]
            items=[{k:copy.deepcopy(doc[k]) for k in ('dispute_id','status','update_time','dispute_amount')}] if cid in {x['id'] for x in captures} else []
            return {'items':items,'links':[]}
        if path=='/v1/customer/disputes/'+doc['dispute_id']:return copy.deepcopy(doc)
        return original(cfg,method,path,*args)
    monkeypatch.setattr(paypal,'_api',api)
    for index,x in enumerate(captures):state['rows'].append(state['movement']('CASECASH'+str(index),'T1201','-2.00',x['id']))
    state['clock'][0]+=4*3600
    return doc


@pytest.mark.parametrize('cash_state',[{}, {'multi':True}],indirect=True)
def test_final_buyer_case_requires_cash_and_exact_per_capture_items(cash_state,account,provider,monkeypatch):
    state=cash_state;final_dispute(state,monkeypatch)
    result=reconcile(state,account);expected=2_000_000*len(state['doc']['purchase_units'][0]['payments']['captures'])
    assert result['fee_loss_micro']==expected
    assert sum(x['due_micro'] for x in rows(account))==expected
    for index,source in enumerate(rows(account)):repay(account,source,'final-cash-case-'+str(index))
    assert sum(x['due_micro'] for x in rows(account))==0
    with auth.db() as c:assert debts.original_loss_review(c)['verified']


def test_contradictory_final_case_finance_resolves_only_with_actual_cash(cash_state,account,provider,monkeypatch):
    from app import payment_reconciliation as journal
    state=cash_state;doc=final_dispute(state,monkeypatch);reconcile(state,account)
    repay(account,rows(account)[0],'cash-final-case-repayment')
    doc['dispute_outcome']['outcome_code']='RESOLVED_SELLER_FAVOUR';doc['update_time']=stamp(state['start']+20)
    service.reconcile_paypal(state['order'],expected_owner=account)
    with auth.db() as c:assert journal.report(c)['pending']>0
    state['rows'].append(state['movement']('CASEACTUALREIMBURSE','T1202','2.00'))
    state['clock'][0]+=4*3600;reconcile(state,account)
    with auth.db() as c:
        report=journal.report(c)
        assert report['pending']==0 and report['subscription_risk_micro']==0
        assert c.execute("SELECT status FROM paypal_financial_holds WHERE order_id=?",(state['order'],)).fetchone()[0]=='permanent'
    assert rows(account)[0]['due_micro']==0 and rows(account)[0]['payments'][0]['refund_due_micro']==2_000_000
    reconcile(state,account)
    with auth.db() as c:assert journal.report(c)['pending']==0


@pytest.mark.parametrize('problem',['unknown_case','wrong_amount','future_case'])
def test_cash_proof_cannot_waive_unmatched_pending_risk(cash_state,account,monkeypatch,problem):
    from app.payment_reconciliation import record_event
    state=cash_state;final_dispute(state,monkeypatch)
    with auth.db() as c:
        c.execute('BEGIN IMMEDIATE')
        data={'type':'risk','kind':'dispute','hold_id':'dispute:PP-D-CASH-123','capture_id':state['cid'],
              'amount_minor':200,'updated_ms':(state['start']+10)*1000,'status':'uncertain',
              'environment':'sandbox','merchant_fingerprint':c.execute('SELECT client_fingerprint FROM paypal_orders WHERE id=?',(state['order'],)).fetchone()[0]}
        if problem=='unknown_case':data['hold_id']='dispute:FOREIGN'
        if problem=='wrong_amount':data['amount_minor']=201
        if problem=='future_case':data['updated_ms']+=100000
        record_event(c,'paypal','unmatched-pending-risk',cash._sha(data),data)
        c.execute("UPDATE payment_reconciliation_events SET order_id=? WHERE event_id='unmatched-pending-risk'",(state['order'],))
    with pytest.raises((ValueError,FenceBlocked)):reconcile(state,account)
    with auth.db() as c:
        assert not cash.has_receipt(c,state['order'])
        assert c.execute("SELECT state FROM payment_reconciliation_events WHERE event_id='unmatched-pending-risk'").fetchone()[0]=='pending'


def test_cash_proof_sigkill_is_atomic_and_recoverable(cash_state,account,monkeypatch):
    import os
    import signal
    if not hasattr(os,'fork'):pytest.skip('Requires actual POSIX SIGKILL')
    state=cash_state;lose(state);original=debts.accrue_original_loss
    def crash(*args):original(*args);os.kill(os.getpid(),signal.SIGKILL)
    child=os.fork()
    if child==0:
        try:
            debts.accrue_original_loss=crash
            reconcile(state,account)
        finally:os._exit(17)
    _,status=os.waitpid(child,0)
    assert os.WIFSIGNALED(status) and os.WTERMSIG(status)==signal.SIGKILL
    with auth.db() as c:
        assert not cash.has_receipt(c,state['order'])
        assert c.execute('SELECT count(*) FROM paypal_subscription_reversals').fetchone()[0]==0
        assert c.execute("SELECT count(*) FROM payment_reconciliation_objects WHERE object_id LIKE 'cash-movement:%'").fetchone()[0]==0
    reconcile(state,account)
    assert len(rows(account))==1 and rows(account)[0]['due_micro']==1_000_000


def test_cash_receipts_and_claims_erased_with_retired_owner(cash_state,account,provider,monkeypatch,tmp_path):
    from app import account_lifecycle as life,account_erasure,ai_arranger_runtime
    monkeypatch.setattr(ai_arranger_runtime,'_ROOT',tmp_path/'private-cash-queue')
    monkeypatch.setattr(auth,'send_mail',lambda *a,**kw:None)
    state=cash_state;lose(state);reconcile(state,account);repay(account,rows(account)[0],'cash-erasure-repayment')
    admin=auth.find_user('admin')['id'];life.register(account);life.retire(account,admin)
    assert account_erasure.erase(account,admin,confirmed=True)['done']
    with auth.db() as c:
        assert c.execute('SELECT count(*) FROM payment_reconciliation_events WHERE order_id=?',(state['order'],)).fetchone()[0]==0
        assert c.execute('SELECT count(*) FROM payment_reconciliation_objects WHERE order_id=?',(state['order'],)).fetchone()[0]==0
        assert c.execute('SELECT count(*) FROM subscription_payment_basis WHERE user_id=?',(account,)).fetchone()[0]==0


@pytest.mark.parametrize('problem',['root_missing','root_amount','root_order','root_reversed','fee_adjustment','missing_refund'])
def test_principal_requires_full_original_and_refund_cash_identity(cash_state,account,problem):
    state=cash_state;lose(state)
    if problem=='root_missing':state['rows'].pop(0)
    if problem=='root_amount':state['rows'][0]['transaction_info']['transaction_amount']['value']='4.00'
    if problem=='root_order':state['rows'][0]['transaction_info']['paypal_reference_id']='FOREIGNORDER'
    if problem=='root_reversed':
        state['rows'][0]['transaction_info']['transaction_status']='V'
        state['rows'].append(state['movement']('RETURNEDLOSS','T1202','1.00'))
    if problem=='fee_adjustment':
        state['rows'].append(state['movement']('FEE111','T0106','-0.50'))
        state['rows'].append(state['movement']('FEEADJUST111','T1208','0.50','FEE111'))
    if problem=='missing_refund':
        completed_refund(state);state['rows'].pop();state['clock'][0]+=4*3600
    with pytest.raises((ValueError,FenceBlocked)):reconcile(state,account)
    with auth.db() as c:assert not cash.has_receipt(c,state['order'])


@pytest.mark.parametrize('corruption',['claim_binding','claim_digest','receipt_digest'])
def test_corrupted_cash_proof_cannot_collect_again(cash_state,account,corruption):
    state=cash_state;lose(state);reconcile(state,account)
    source=rows(account)[0]
    with auth.db() as c:
        if corruption=='claim_binding':c.execute("UPDATE payment_reconciliation_objects SET order_id='FOREIGN' WHERE object_id=?",('cash-movement:LOSSMOVEMENT111',))
        else:
            target='reconcile:subscription-movement:LOSSMOVEMENT111' if corruption=='claim_digest' else c.execute("SELECT event_id FROM payment_reconciliation_events WHERE normalized_json LIKE '%mta-subscription-cash-position-1%'").fetchone()[0]
            # SQL writes are fenced too; only simulate corruption after proving it.
            with pytest.raises(sqlite3.IntegrityError,match='Immutable financial event payload'):
                c.execute('UPDATE payment_reconciliation_events SET digest=? WHERE event_id=?',('0'*64,target))
            c.execute('DROP TRIGGER payment_events_immutable_payload')
            c.execute('UPDATE payment_reconciliation_events SET digest=? WHERE event_id=?',('0'*64,target))
    with pytest.raises(FenceBlocked,match='cash (receipt|movement claim) cannot be verified'):
        paypal.checkout(account,{'kind':'subscription_reversal','refund_id':source['refund_id'],
                                'expected_due_micro':source['due_micro'],'request_id':'corrupt-cash-proof'})


def test_complete_paginated_multiwindow_cash_history_is_bounded(cash_state,account):
    state=cash_state;lose(state)
    for n in range(120):state['rows'].append(state['movement']('UNRELATED'+str(n),'T0006','9.00','OTHERORDER'))
    state['clock'][0]+=32*86400
    reconcile(state,account)
    assert len(state['reads'])==6  # two pages plus the empty next window, twice
    assert rows(account)[0]['due_micro']==1_000_000


@pytest.mark.parametrize('bound',['reads','windows','rows','deadline'])
def test_cash_history_resource_bound_does_not_collect(cash_state,account,monkeypatch,bound):
    state=cash_state;lose(state)
    if bound=='reads':monkeypatch.setattr(cash,'MAX_READS',1)
    if bound=='windows':monkeypatch.setattr(cash,'MAX_WINDOWS',1);state['clock'][0]+=32*86400
    if bound=='rows':monkeypatch.setattr(cash,'MAX_ROWS',1)
    if bound=='deadline':monkeypatch.setattr(cash,'MAX_SECONDS',0)
    with pytest.raises(ValueError):reconcile(state,account)
    assert rows(account)==[]


@pytest.mark.parametrize('case_loss',[False,True])
def test_completed_temporary_hold_cancellation_does_not_block_final_principal(cash_state,account,monkeypatch,case_loss):
    state=cash_state
    if case_loss:final_dispute(state,monkeypatch)
    else:lose(state)
    state['rows'].extend([state['movement']('TEMPORARYHOLD111','T1110','-2.00'),
                          state['movement']('TEMPORARYRELEASE111','T1111','2.00')])
    assert reconcile(state,account)['fee_loss_micro']==(2_000_000 if case_loss else 1_000_000)
    assert sum(x['due_micro'] for x in rows(account))==(2_000_000 if case_loss else 1_000_000)


@pytest.mark.parametrize('code',['T1108','T1109'])
def test_provider_fee_returns_do_not_reduce_original_fee_loss(cash_state,account,code):
    state=cash_state;lose(state)
    state['rows'].append(state['movement']('FEERETURN111',code,'1.00'))
    assert reconcile(state,account)['fee_loss_micro']==1_000_000
    assert rows(account)[0]['due_micro']==1_000_000


@pytest.mark.parametrize('amount',['1.00','5.00'])
def test_final_loss_can_subsume_completed_refund_without_duplicate_principal(cash_state,account,amount):
    state=cash_state;lose(state,amount);completed_refund(state)
    # PayPal's actual debit is only the part not already returned by refund.
    state['rows']=[x for x in state['rows'] if x['transaction_info']['transaction_id']!='LOSSMOVEMENT111']
    if amount=='5.00':state['rows'].append(state['movement']('NETREMAININGLOSS','T1106','-4.00'))
    state['clock'][0]+=4*3600
    assert reconcile(state,account)['fee_loss_micro']==int(float(amount)*1_000_000)
    assert sum(x['due_micro'] for x in rows(account))==int(float(amount)*1_000_000)


def test_full_signed_reversal_is_also_read_back_for_later_cash_reimbursement(cash_state,account,provider):
    state=cash_state;lose(state,'5.00')
    # The full signed loss already has a valid receivable, so no unproved-partial gap exists.
    with auth.db() as c:assert debts.original_loss_review(c)['verified']
    assert reconcile(state,account)['fee_loss_micro']==5_000_000
    repay(account,rows(account)[0],'full-signed-loss-repayment')
    state['rows'].append(state['movement']('FULLREIMBURSE111','T1202','5.00'))
    state['clock'][0]+=4*3600
    assert reconcile(state,account)['fee_loss_micro']==0
    assert rows(account)[0]['due_micro']==0 and rows(account)[0]['payments'][0]['refund_due_micro']==5_000_000
