"""Partial multicapture recovery uses exact reports, never gross proportions."""
import copy
import json
from concurrent.futures import ThreadPoolExecutor

import pytest
from app import auth,paypal_payments as paypal,resource_accounts as resources
from app import paypal_settlement_reports as reports,payment_reconcile_service as service
from app import payment_reconciliation as journal
from app.regime_operation_fence import FenceBlocked
from test_r210_subscriptions import account as account  # noqa: F401
from test_r210_paypal import provider as provider  # noqa: F401
from test_r210_paypal_dispute_history import fixture
from test_r210_paypal_settlement_reports import ACCOUNT,ACM,STL,documents,encode_rows,apply


def setup(account,provider,monkeypatch,*,paid=True,subscription=False,items=False):
    local,order,docs,calls,hook=fixture(account,provider,monkeypatch,paid=paid,multi=True,subscription=subscription)
    order['purchase_units'][0]['payee']={'merchant_id':ACCOUNT}
    doc=docs['PP-D-123']
    doc.update(status='RESOLVED',create_time='2026-10-23T00:00:00Z',
               dispute_outcome={'outcome_code':'RESOLVED_WITH_PAYOUT'})
    doc['dispute_amount']['value']='4.00'
    if items:
        for index,tx in enumerate(doc['disputed_transactions']):
            tx['items']=[{'item_id':'ITEM'+str(index),'dispute_amount':{'value':'2.00','currency_code':'EUR'}}]
    paypal.settings({'environment':'live'})
    with auth.db() as c:c.execute("UPDATE paypal_orders SET environment='live' WHERE id=?",(local,))
    raw=encode_rows(*documents(multi=True))
    provenance={'host':'reports.paypal.com','known_hosts_sha256':'a'*64,'acm_file':ACM,'stl_file':STL,
                'acm_sha256':reports.digest(raw[0]),'stl_sha256':reports.digest(raw[1])}
    monkeypatch.setattr(reports,'fetch',lambda *args:(raw,provenance))
    return {'local':local,'order':order,'docs':docs,'raw':raw,'calls':calls,'hook':hook,
            'admin':auth.find_user('admin')['id']}


def position(local):
    with auth.db() as c:
        result=journal.report(c)
        return next(p for p in result['positions'] if p['order_id']==local),result['pending']


@pytest.mark.parametrize('paid',[False,True])
@pytest.mark.parametrize('subscription',[False,True])
def test_exact_partial_allocation_funds_once_and_ordinary_replay_needs_no_reports(account,provider,monkeypatch,paid,subscription):
    data=setup(account,provider,monkeypatch,paid=paid,subscription=subscription)
    with pytest.raises(ValueError):service.reconcile_paypal(data['local'])
    assert apply(data)['settlement_report_resolutions']==2
    expected=0 if subscription else 5_000_000
    assert resources.state(account)['credits_micro']==expected
    monkeypatch.setattr(reports,'fetch',lambda *a:pytest.fail('Replay must not fetch reports'))
    with ThreadPoolExecutor(max_workers=3) as pool:
        results=list(pool.map(lambda _:service.reconcile_paypal(data['local']),range(3)))
    assert all(r['ledger_reconciled'] and not r['financial_review_pending'] for r in results)
    assert resources.state(account)['credits_micro']==expected
    p,pending=position(data['local']);assert pending==0 and p['held_minor']==0
    with auth.db() as c:
        assert [tuple(r) for r in c.execute('SELECT capture_id,amount_cents,status FROM paypal_financial_holds ORDER BY capture_id')]==[
            ('CAPTURE111',200,'released'),('CAPTURE222',200,'released')]
        assert c.execute("SELECT count(*) FROM payment_reconciliation_events WHERE event_id LIKE 'reconcile:report-movement:%'").fetchone()[0]==2
        if subscription:
            assert journal.report(c)['subscription_reversal_due_micro']==0


def test_partial_report_release_restores_only_original_held_amounts(account,provider,monkeypatch):
    data=setup(account,provider,monkeypatch,items=True)
    assert service.reconcile_paypal(data['local'])['financial_review_pending']
    assert resources.state(account)['credits_micro']==1_000_000
    assert apply(data)['settlement_report_resolutions']==2
    assert resources.state(account)['credits_micro']==5_000_000
    assert not service.reconcile_paypal(data['local'])['financial_review_pending']
    assert resources.state(account)['credits_micro']==5_000_000


@pytest.mark.parametrize('defect',['missing_capture','extra_capture','wrong_gross','sum','zero','wrong_case',
                                  'not_resolved','foreign_capture','items_conflict','items_incomplete'])
def test_partial_or_conflicting_allocations_cannot_grant_money(account,provider,monkeypatch,defect):
    data=setup(account,provider,monkeypatch,paid=False)
    cases,money=documents(multi=True)
    doc=data['docs']['PP-D-123']
    if defect=='missing_capture':cases.pop();money.pop()
    if defect=='extra_capture':cases[1]['Original Transaction ID']=money[1]['paypal_reference_id']='CAPTURE999'
    if defect=='wrong_gross':cases[1]['Original Gross Amount']='300'
    if defect=='sum':doc['dispute_amount']['value']='3.99'
    if defect=='zero':cases[1]['Disputed Gross Amount']=money[1]['gross_transaction_amount']='0'
    if defect=='wrong_case':cases[1]['Dispute Case ID']='PP-D-OTHER'
    if defect=='not_resolved':doc['status']='UNDER_REVIEW'
    if defect=='foreign_capture':doc['disputed_transactions'][1]['seller_transaction_id']='CAPTURE999'
    if defect.startswith('items_'):
        doc['disputed_transactions'][0]['items']=[{'item_id':'FIRST','dispute_amount':{'value':'1.00','currency_code':'EUR'}}]
        if defect=='items_conflict':
            doc['disputed_transactions'][1]['items']=[{'item_id':'SECOND','dispute_amount':{'value':'3.00','currency_code':'EUR'}}]
    data['raw'][:]=encode_rows(cases,money)
    with pytest.raises((ValueError,FenceBlocked)):apply(data)
    assert resources.state(account)['credits_micro']==0
    with auth.db() as c:
        exists=c.execute("SELECT 1 FROM sqlite_master WHERE name='payment_reconciliation_events'").fetchone()
        if exists:
            assert c.execute("SELECT count(*) FROM payment_reconciliation_events WHERE event_id LIKE 'reconcile:report-movement:%'").fetchone()[0]==0


@pytest.mark.parametrize('change',['timestamp','case','amount','capture','gross','opened'])
def test_applied_report_does_not_allocate_changed_canonical_document(account,provider,monkeypatch,change):
    data=setup(account,provider,monkeypatch);apply(data)
    doc=data['docs']['PP-D-123']
    if change=='timestamp':doc['update_time']='2026-10-25T03:00:00Z'
    if change=='case':doc['dispute_id']='PP-D-CHANGED'
    if change=='amount':doc['dispute_amount']['value']='3.00'
    if change=='capture':doc['disputed_transactions'][1]['seller_transaction_id']='CAPTURE999'
    if change=='gross':doc['disputed_transactions'][0]['gross_amount']['value']='2.50'
    if change=='opened':doc['create_time']='2026-10-24T00:00:00Z'
    with pytest.raises((ValueError,FenceBlocked)):service.reconcile_paypal(data['local'])
    assert resources.state(account)['credits_micro']==5_000_000
    assert position(data['local'])[1]>0


@pytest.mark.parametrize('missing',['claim','binding','receipt','hold'])
def test_replay_requires_complete_original_applied_claims_and_holds(account,provider,monkeypatch,missing):
    data=setup(account,provider,monkeypatch);apply(data)
    # Destructive corruption in an isolated fixture, never an operational repair.
    with auth.db() as c:
        if missing=='claim':c.execute("DELETE FROM payment_reconciliation_events WHERE event_id='reconcile:report-movement:MOVEMENT1'")
        if missing=='binding':c.execute("DELETE FROM payment_reconciliation_objects WHERE object_id='report-movement:MOVEMENT1'")
        if missing=='receipt':
            for event,raw in c.execute("SELECT event_id,normalized_json FROM payment_reconciliation_events WHERE provider='paypal'").fetchall():
                obj=json.loads(raw)
                if obj.get('settlement_report_proof',{}).get('capture_id')=='CAPTURE111':
                    c.execute("DELETE FROM payment_reconciliation_events WHERE provider='paypal' AND event_id=?",(event,))
        if missing=='hold':c.execute("DELETE FROM paypal_financial_holds WHERE capture_id='CAPTURE111'")
    with pytest.raises((ValueError,FenceBlocked)):service.reconcile_paypal(data['local'])
    assert resources.state(account)['credits_micro']==5_000_000


def test_failure_after_first_partial_release_rolls_back_both_claims_and_ledger(account,provider,monkeypatch):
    data=setup(account,provider,monkeypatch,items=True)
    service.reconcile_paypal(data['local'])
    original=paypal._apply_risk;seen=[]
    def fail(c,row,event):
        result=original(c,row,event);seen.append(event)
        if len(seen)==2:raise RuntimeError('second capture before commit')
        return result
    monkeypatch.setattr(paypal,'_apply_risk',fail)
    with pytest.raises(RuntimeError):apply(data)
    assert resources.state(account)['credits_micro']==1_000_000
    with auth.db() as c:
        assert c.execute("SELECT count(*) FROM payment_reconciliation_events WHERE event_id LIKE 'reconcile:report-movement:%'").fetchone()[0]==0
    monkeypatch.setattr(paypal,'_apply_risk',original)
    apply(data);assert resources.state(account)['credits_micro']==5_000_000


def test_report_replay_keeps_original_admin_audit_after_role_revocation(account,provider,monkeypatch):
    data=setup(account,provider,monkeypatch);apply(data)
    with auth.db() as c:c.execute('UPDATE users SET active=0 WHERE id=?',(data['admin'],))
    assert not service.reconcile_paypal(data['local'])['financial_review_pending']
    with pytest.raises(FenceBlocked):apply(data)
    assert resources.state(account)['credits_micro']==5_000_000


@pytest.mark.parametrize('paid',[False,True])
@pytest.mark.parametrize('subscription',[False,True])
@pytest.mark.parametrize('amount',['1.00','3.00'])
def test_partial_release_and_refund_conserve_wallet_or_exact_subscription_debt(account,provider,monkeypatch,paid,subscription,amount):
    data=setup(account,provider,monkeypatch,paid=paid,subscription=subscription,items=True)
    service.reconcile_paypal(data['local'])
    payments=data['order']['purchase_units'][0]['payments']
    payments['captures'][0]['status']='REFUNDED' if amount=='3.00' else 'PARTIALLY_REFUNDED'
    refund={'id':'REFUND333','status':'COMPLETED','amount':{'value':amount,'currency_code':'EUR'},
            'seller_payable_breakdown':{'total_refunded_amount':{'value':amount,'currency_code':'EUR'}},
            'links':[{'rel':'up','href':'https://api-m.paypal.com/v2/payments/captures/CAPTURE111'}]}
    payments['refunds']=[copy.deepcopy(refund)]
    original=paypal._api
    def api(cfg,method,path,*args):
        assert method=='GET'
        if path=='/v2/payments/refunds/REFUND333':return copy.deepcopy(refund)
        if path=='/v2/payments/captures/CAPTURE111':return copy.deepcopy(payments['captures'][0])
        return original(cfg,method,path,*args)
    monkeypatch.setattr(paypal,'_api',api)
    assert apply(data)['settlement_report_resolutions']==2
    assert not service.reconcile_paypal(data['local'])['financial_review_pending']
    cents=100 if amount=='1.00' else 300
    assert resources.state(account)['credits_micro']==(0 if subscription else (500-cents)*10000)
    p,pending=position(data['local'])
    assert pending==0 and p['refunded_minor']==cents and p['held_minor']==0
    if subscription:
        with auth.db() as c:assert journal.report(c)['subscription_reversal_due_micro']==cents*10000


def test_partial_replay_rechecks_original_claim_inside_financial_transaction(account,provider,monkeypatch):
    data=setup(account,provider,monkeypatch);apply(data)
    original=paypal.fulfill
    def race(*args,**kwargs):
        with auth.db() as c:c.execute("DELETE FROM payment_reconciliation_objects WHERE object_id='report-movement:MOVEMENT1'")
        return original(*args,**kwargs)
    monkeypatch.setattr(paypal,'fulfill',race)
    with pytest.raises(FenceBlocked,match='claim unavailable'):service.reconcile_paypal(data['local'])
    assert resources.state(account)['credits_micro']==5_000_000


def test_report_does_not_ignore_a_third_capture_for_the_same_case(account,provider,monkeypatch):
    data=setup(account,provider,monkeypatch,paid=False)
    cases,money=documents(multi=True)
    case=copy.deepcopy(cases[0]);movement=copy.deepcopy(money[0])
    case['Original Transaction ID']=movement['paypal_reference_id']='CAPTURE999'
    case['Dispute Transaction ID']=movement['transaction_id']='MOVEMENT3'
    data['raw'][:]=encode_rows(cases+[case],money+[movement])
    with pytest.raises((ValueError,FenceBlocked)):apply(data)
    assert resources.state(account)['credits_micro']==0


@pytest.mark.parametrize('defect',['digest','shape','hold_changed'])
def test_corrupt_applied_evidence_cannot_authorize_partial_replay(account,provider,monkeypatch,defect):
    data=setup(account,provider,monkeypatch);apply(data)
    with auth.db() as c:
        if defect=='hold_changed':
            c.execute("UPDATE paypal_financial_holds SET status='uncertain' WHERE capture_id='CAPTURE111'")
        else:
            for raw,order_id in c.execute("SELECT normalized_json,order_id FROM payment_reconciliation_events WHERE provider='paypal' AND state='applied'").fetchall():
                if json.loads(raw).get('settlement_report_proof'):
                    if defect=='shape':raw='[]'
                    c.execute("INSERT INTO payment_reconciliation_events VALUES('paypal','corrupt-receipt','invalid',?,?,'applied',0)",(raw,order_id))
                    break
    with pytest.raises((ValueError,FenceBlocked)):service.reconcile_paypal(data['local'])
    assert resources.state(account)['credits_micro']==5_000_000
