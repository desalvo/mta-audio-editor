"""Canonical GET-only history, atomic wallet, replay and stale snapshot tests."""
import copy
from concurrent.futures import ThreadPoolExecutor

import pytest
from app import auth,paypal_payments as paypal,payment_reconcile_service as service
from app import resource_accounts as resources,payment_reconciliation as journal
from app.regime_operation_fence import FenceBlocked
from test_r210_paypal import provider as provider  # noqa: F401
from test_r210_subscriptions import account as account  # noqa: F401
from test_r210_paypal_reconciliation_e2e import setup_order


def history_fixture(account,provider,monkeypatch,*,paid=False,subscription=False):
    local,order,_,first=setup_order(account,provider,monkeypatch,before_capture=not paid,subscription=subscription)
    first['seller_payable_breakdown']={'total_refunded_amount':{'value':'3.00','currency_code':'EUR'}}
    captures=order['purchase_units'][0]['payments']['captures']
    captures[0]['status']='REFUNDED'
    second={'id':'REFUND222','status':'COMPLETED','amount':{'value':'1.00','currency_code':'EUR'},
            'seller_payable_breakdown':{'total_refunded_amount':{'value':'1.00','currency_code':'EUR'}},
            'links':[{'rel':'up','href':'https://api-m.sandbox.paypal.com/v2/payments/captures/CAPTURE222'}]}
    captures[1]['status']='PARTIALLY_REFUNDED'
    refunds={'REFUND111':first,'REFUND222':second}
    order['purchase_units'][0]['payments']['refunds']=[copy.deepcopy(first),copy.deepcopy(second)]
    original=paypal._api;calls=[]
    def api(cfg,method,path,*args):
        assert method=='GET'
        calls.append(path)
        if '/payments/refunds/' in path:return copy.deepcopy(refunds[path.rsplit('/',1)[1]])
        if '/payments/captures/' in path:return copy.deepcopy(next(c for c in captures if c['id']==path.rsplit('/',1)[1]))
        return original(cfg,method,path,*args)
    monkeypatch.setattr(paypal,'_api',api)
    return local,order,refunds,calls


@pytest.mark.parametrize('paid',[False,True])
def test_initial_refunded_or_previously_paid_capture_reconciles_exact_net(account,provider,monkeypatch,paid):
    local,_,_,calls=history_fixture(account,provider,monkeypatch,paid=paid)
    result=service.reconcile_paypal(local)
    assert result['ledger_reconciled'] and result['refunds']==2 and not result['transition_authorized']
    assert resources.state(account)['credits_micro']==1_000_000
    with ThreadPoolExecutor(max_workers=3) as pool:list(pool.map(lambda _:service.reconcile_paypal(local),range(3)))
    assert resources.state(account)['credits_micro']==1_000_000
    with auth.db() as c:
        report=journal.report(c)
        assert report['verified'] and report['pending']==0
        assert report['positions'][0]['refunded_minor']==400
        assert c.execute('SELECT count(*) FROM paypal_refunds').fetchone()[0]==2
    assert sum('/checkout/orders/' in call for call in calls)==12


@pytest.mark.parametrize('failure',['missing','cumulative','pending','identity','amount','currency','duplicate','capture','order_changed','config_changed','local_changed'])
def test_incomplete_or_changed_history_cannot_grant_gross_credit(account,provider,monkeypatch,failure):
    local,order,refunds,_=history_fixture(account,provider,monkeypatch)
    payments=order['purchase_units'][0]['payments'];refund=refunds['REFUND222']
    if failure=='missing':payments['refunds'].pop()
    if failure=='cumulative':refund['seller_payable_breakdown']['total_refunded_amount']['value']='1.50'
    if failure=='pending':refund['status']=payments['refunds'][1]['status']='PENDING'
    if failure=='identity':refund['links'][0]['href']=refund['links'][0]['href'].replace('CAPTURE222','CAPTURE999')
    if failure=='amount':refund['amount']['value']='2.00'
    if failure=='currency':refund['amount']['currency_code']='USD'
    if failure=='duplicate':payments['refunds'].append(copy.deepcopy(payments['refunds'][0]))
    if failure=='capture':payments['captures'][0]['status']='PENDING'
    original=paypal._api;reads=[]
    def api(cfg,method,path,*args):
        value=original(cfg,method,path,*args)
        if '/checkout/orders/' in path:
            reads.append(path)
            if len(reads)==2:
                if failure=='order_changed':value['purchase_units'][0]['payments']['refunds'].pop()
                if failure=='config_changed':paypal.settings({'client_secret':'rotated-secret'})
                if failure=='local_changed':
                    with auth.db() as c:c.execute('UPDATE paypal_orders SET user_id=1 WHERE id=?',(local,))
        return value
    monkeypatch.setattr(paypal,'_api',api)
    if failure=='local_changed':
        # Use an amount change independent of fixture user IDs.
        def changed(cfg,method,path,*args):
            value=api(cfg,method,path,*args)
            if len(reads)==2:
                with auth.db() as c:c.execute('UPDATE paypal_orders SET amount_cents=600 WHERE id=?',(local,))
            return value
        monkeypatch.setattr(paypal,'_api',changed)
    with pytest.raises((ValueError,FenceBlocked)):service.reconcile_paypal(local)
    assert resources.state(account)['credits_micro']==0
    with auth.db() as c:
        assert c.execute('SELECT count(*) FROM paypal_captures').fetchone()[0]==0
        assert c.execute('SELECT count(*) FROM paypal_refunds').fetchone()[0]==0


def test_failure_after_funding_rolls_back_history_and_wallet(account,provider,monkeypatch):
    local,_,_,_=history_fixture(account,provider,monkeypatch)
    original=paypal._apply_refund;count=[]
    def fail(c,data,event):
        count.append(event)
        if len(count)==2:raise RuntimeError('after first refund')
        return original(c,data,event)
    monkeypatch.setattr(paypal,'_apply_refund',fail)
    with pytest.raises(RuntimeError):service.reconcile_paypal(local)
    assert resources.state(account)['credits_micro']==0
    with auth.db() as c:
        assert c.execute('SELECT count(*) FROM paypal_captures').fetchone()[0]==0
        assert c.execute("SELECT status FROM paypal_orders WHERE id=?",(local,)).fetchone()[0]!='paid'
    monkeypatch.setattr(paypal,'_apply_refund',original)
    service.reconcile_paypal(local)
    assert resources.state(account)['credits_micro']==1_000_000


def test_refunded_subscription_creates_exact_receivable(account,provider,monkeypatch):
    local,_,_,_=history_fixture(account,provider,monkeypatch,subscription=True)
    service.reconcile_paypal(local);service.reconcile_paypal(local)
    assert resources.state(account)['credits_micro']==0
    with auth.db() as c:assert journal.report(c)['subscription_reversal_due_micro']==4_000_000


@pytest.mark.parametrize('value',[1,True,1.01,'NaN','1e2','-1','1.001',' 1','1.'])
def test_money_is_an_exact_eur_decimal_string(value):
    with pytest.raises(ValueError):paypal._cents({'value':value,'currency_code':'EUR'})
