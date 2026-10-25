"""Original fee loss -> exact existing repayment checkout; no wallet mutation."""
import copy
import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor
import pytest
from app import auth, paypal_payments as paypal, resource_accounts as resources
from app import subscription_receivables as debts
from test_r210_subscriptions import account as account, plan  # noqa: F401
from test_r210_paypal import provider as provider  # noqa: F401
from test_r210_paypal_reconciliation_e2e import setup_order, HEADERS


@pytest.fixture
def paid(account, provider, monkeypatch):
    local, canonical, refund, _ = setup_order(account, provider, monkeypatch, subscription=True)
    return local, canonical, refund


def reverse(capture='CAPTURE111', amount='3.00', event='loss-original-111'):
    return paypal.webhook(json.dumps({'id':event,'event_type':'PAYMENT.CAPTURE.REVERSED',
        'resource':{'id':capture,'amount':{'value':amount,'currency_code':'EUR'}}}).encode(),HEADERS)


def rows(uid):
    return resources.transactions(uid)['subscription_reversals']


def repay(uid, source, key):
    payment=paypal.checkout(uid,{'kind':'subscription_reversal','refund_id':source['refund_id'],
                               'expected_due_micro':source['due_micro'],'request_id':key})
    paypal.capture(uid,payment['order_id'])
    return payment


def test_original_permanent_loss_can_be_repaid_exactly(account, provider, paid):
    fees=resources.transactions(account)['subscription_fees']
    reverse(); source=rows(account)[0]
    assert source['amount_micro']==source['due_micro']==3_000_000
    assert source['refund_id'].startswith('LOSS')
    reverse(); assert len(rows(account))==1
    repay(account,source,'original-loss-repay-123')
    assert rows(account)[0]['due_micro']==0
    assert resources.state(account)['credits_micro']==0
    assert resources.transactions(account)['subscription_fees']==fees


@pytest.mark.parametrize('refund_first',[False,True])
def test_full_reversal_and_refund_of_same_capture_never_double_debt(account, provider, paid, refund_first):
    event=paid[2]
    if refund_first: paypal.webhook(json.dumps(event).encode(),HEADERS)
    reverse()
    if not refund_first: paypal.webhook(json.dumps(event).encode(),HEADERS)
    assert sum(r['amount_micro'] for r in rows(account))==3_000_000
    reverse('CAPTURE222','2.00','loss-original-222')
    assert sum(r['amount_micro'] for r in rows(account))==5_000_000


def test_duplicate_permanent_cases_on_same_capture_share_fee_cap(account, provider, paid, monkeypatch):
    reverse()
    with auth.db() as c:
        order=c.execute('SELECT * FROM paypal_orders WHERE id=?',(paid[0],)).fetchone()
        cfg=paypal._keys(c)
    # Authenticated canonical dispute reread, separate hold on same capture.
    original=paypal._api
    obj={'dispute_id':'PP-D-ORIGINAL','update_time':'2026-10-25T02:00:00Z','status':'RESOLVED',
         'disputed_transactions':[{'seller_transaction_id':'CAPTURE111'}],
         'dispute_amount':{'currency_code':'EUR','value':'3.00'},
         'dispute_outcome':{'outcome_code':'RESOLVED_BUYER_FAVOUR'}}
    monkeypatch.setattr(paypal,'_api',lambda cfg,method,path,*args:copy.deepcopy(obj) if path=='/v1/customer/disputes/PP-D-ORIGINAL' else original(cfg,method,path,*args))
    paypal.webhook(json.dumps({'id':'original-dispute-123','event_type':'CUSTOMER.DISPUTE.UPDATED','resource':{'dispute_id':obj['dispute_id']}}).encode(),HEADERS)
    assert sum(r['amount_micro'] for r in rows(account))==3_000_000
    assert order['kind']=='subscription' and cfg['environment']=='sandbox'


def test_partial_permanent_loss_stays_unallocated(account, provider, paid):
    reverse(amount='1.00')
    assert rows(account)==[]
    with auth.db() as c:
        assert c.execute('SELECT held_minor FROM payment_reconciliation_positions WHERE order_id=?',(paid[0],)).fetchone()[0]==100


def test_legacy_missing_original_basis_is_not_invented(account, provider, paid):
    with auth.db() as c:
        c.execute('DROP TABLE subscription_payment_basis')
    reverse()
    assert rows(account)==[]
    with auth.db() as c:
        assert c.execute('SELECT count(*) FROM subscription_payment_basis').fetchone()[0]==0


def test_payment_basis_is_immutable_and_failed_event_rolls_back(account, provider, paid, monkeypatch):
    with auth.db() as c:
        with pytest.raises(sqlite3.IntegrityError):
            c.execute('UPDATE subscription_payment_basis SET fee_micro=0')
    original=debts.accrue_original_loss
    monkeypatch.setattr(debts,'accrue_original_loss',lambda *a: (_ for _ in ()).throw(RuntimeError('transaction interrupted')))
    with pytest.raises(RuntimeError): reverse()
    assert rows(account)==[]
    monkeypatch.setattr(debts,'accrue_original_loss',original)
    reverse(); assert rows(account)[0]['due_micro']==3_000_000


def test_concurrent_verified_reversals_allocate_once(account, provider, paid):
    with ThreadPoolExecutor(3) as pool:
        result=list(pool.map(lambda _:reverse(),range(3)))
    assert all(r['received'] for r in result)
    assert len(rows(account))==1


def test_rounding_surplus_is_consumed_before_reopening_original_fee(account, provider):
    state=plan(account,price_micro=5_000_001)
    payment=paypal.checkout(account,{'kind':'subscription','period_start':state['period']['start'],'request_id':'original-rounded-fee'})
    paypal.capture(account,payment['order_id'])
    with auth.db() as c:
        capture=c.execute('SELECT id FROM paypal_captures WHERE order_id=?',(payment['order_id'],)).fetchone()[0]
        assert c.execute('SELECT refund_due_micro FROM paypal_orders WHERE id=?',(payment['order_id'],)).fetchone()[0]==9999
    reverse(capture,'5.01','rounded-original-reversal')
    assert rows(account)[0]['due_micro']==5_000_001
    with auth.db() as c:
        assert c.execute('SELECT refund_due_micro FROM paypal_orders WHERE id=?',(payment['order_id'],)).fetchone()[0]==0
    repay(account,rows(account)[0],'rounded-fee-repayment')
    assert rows(account)[0]['due_micro']==0
    assert rows(account)[0]['payments'][0]['refund_due_micro']==9999


def test_gap_review_distinguishes_legacy_and_unproved_partial_loss(account, provider, paid):
    reverse(amount='1.00')
    from app.payment_reconciliation import report
    with auth.db() as c:
        review=report(c)['subscription_original_loss_review']
        assert not review['verified']
        assert review['unresolved']==[{'order_id':paid[0],'reason':'partial_permanent_loss_allocation_unproved'}]
        c.execute('DROP TABLE subscription_payment_basis')
    with auth.db() as c:
        assert report(c)['subscription_original_loss_review']['unresolved'][0]['reason']=='original_payment_basis_missing'


def test_original_fee_basis_survives_later_subscription_price_change(account,provider,paid):
    with auth.db() as c:
        c.execute('UPDATE resource_plan_charges SET amount_micro=999999 WHERE user_id=?',(account,))
    reverse('CAPTURE111','3.00')
    reverse('CAPTURE222','2.00','second-original-capture-loss')
    assert sum(r['amount_micro'] for r in rows(account))==5_000_000


def test_actual_owner_api_repay_private_loss_obligation(account,provider,paid,monkeypatch):
    from fastapi.testclient import TestClient
    from app import main
    from test_r210_legal_documents import cookie
    monkeypatch.setattr(main,'NATIVE_SINGLE_USER',False)
    monkeypatch.setattr(main,'check_basic_auth',lambda _:False)
    monkeypatch.delenv('MTA_ALLOW_INSECURE_NO_AUTH',raising=False)
    reverse()
    source=rows(account)[0]
    client=TestClient(main.app)
    body={'kind':'subscription_reversal','refund_id':source['refund_id'],
          'expected_due_micro':source['due_micro'],'request_id':'owner-loss-api-123'}
    assert client.post('/api/account/paypal/checkout',json=body,headers={'X-MTA-Request':'1'}).status_code==401
    client.cookies.update(cookie(account))
    response=client.post('/api/account/paypal/checkout',json=body,headers={'X-MTA-Request':'1'})
    assert response.status_code==200,response.text
    payment=response.json()['order_id']
    assert client.post('/api/account/paypal/'+payment+'/capture',json={},headers={'X-MTA-Request':'1'}).status_code==200
    assert rows(account)[0]['due_micro']==0


def test_same_capture_refund_after_loss_was_repaid_does_not_reopen_debt(account,provider,paid):
    reverse()
    repay(account,rows(account)[0],'first-loss-repayment-123')
    paypal.webhook(json.dumps(paid[2]).encode(),HEADERS)
    assert sum(r['due_micro'] for r in rows(account))==0
    assert sum(r['amount_micro'] for r in rows(account))==3_000_000


def test_buyer_favour_dispute_without_actual_reversal_never_collects_fee(account,provider,paid,monkeypatch):
    original=paypal._api
    obj={'dispute_id':'PP-D-NOMONEY','update_time':'2026-10-25T02:00:00Z','status':'RESOLVED',
         'disputed_transactions':[{'seller_transaction_id':'CAPTURE111'}],
         'dispute_amount':{'currency_code':'EUR','value':'3.00'},
         'dispute_outcome':{'outcome_code':'RESOLVED_BUYER_FAVOUR'}}
    monkeypatch.setattr(paypal,'_api',lambda cfg,method,path,*args:copy.deepcopy(obj) if path=='/v1/customer/disputes/PP-D-NOMONEY' else original(cfg,method,path,*args))
    paypal.webhook(json.dumps({'id':'unproved-original-movement','event_type':'CUSTOMER.DISPUTE.UPDATED','resource':{'dispute_id':obj['dispute_id']}}).encode(),HEADERS)
    assert rows(account)==[]
    from app.payment_reconciliation import report
    with auth.db() as c:
        assert report(c)['subscription_original_loss_review']['unresolved'][0]['reason']=='permanent_dispute_movement_unproved'
