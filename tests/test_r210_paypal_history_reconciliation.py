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
from test_r210_subscriptions import plan


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


def test_owner_capture_recovers_already_refunded_order_at_exact_net_after_disable(account,provider,monkeypatch):
    local,_,_,_=history_fixture(account,provider,monkeypatch,paid=False)
    resources.configure({'credits_enabled':False})
    before=len(provider[1]);result=paypal.capture(account,local)
    assert result['ledger_reconciled'] and result['status']=='paid' and result['refunds']==2
    assert resources.state(account)['credits_micro']==1_000_000
    assert not any(call[0]=='POST' for call in provider[1][before:])
    assert paypal.capture(account,local)['status']=='paid'
    assert resources.state(account)['credits_micro']==1_000_000


@pytest.mark.parametrize('incomplete',[False,True])
def test_first_capture_refund_is_reconciled_before_credit(account,provider,monkeypatch,incomplete):
    plan(account)
    local=paypal.checkout(account,{'kind':'credits','amount_cents':500,'request_id':'first-capture-refund-'+str(incomplete)})['order_id']
    pid=next(iter(provider[0]));capture_id='CAPTURE'+pid;original=paypal._api
    refund={'id':'REFUND999','status':'COMPLETED','amount':{'value':'2.00','currency_code':'EUR'},
            'seller_payable_breakdown':{'total_refunded_amount':{'value':'2.00','currency_code':'EUR'}},
            'links':[{'rel':'up','href':'https://api-m.sandbox.paypal.com/v2/payments/captures/'+capture_id}]}
    def api(cfg,method,path,*args):
        if method=='GET' and path=='/v2/payments/refunds/REFUND999':return copy.deepcopy(refund)
        value=original(cfg,method,path,*args)
        if method=='POST' and path.endswith('/capture'):
            payments=provider[0][pid]['purchase_units'][0]['payments']
            payments['captures'][0]['status']='PARTIALLY_REFUNDED'
            payments['refunds']=[] if incomplete else [copy.deepcopy(refund)]
        return value
    monkeypatch.setattr(paypal,'_api',api)
    if incomplete:
        with pytest.raises(ValueError,match='history is incomplete'):paypal.capture(account,local)
        assert resources.state(account)['credits_micro']==0
    else:
        assert paypal.capture(account,local)['status']=='paid'
        assert resources.state(account)['credits_micro']==3_000_000
    assert len([call for call in provider[1] if call[1].endswith('/capture')])==1


def test_webhook_reconciles_prior_refunds_and_records_event_atomically(account,provider,monkeypatch):
    import json
    local,order,_,_=history_fixture(account,provider,monkeypatch,paid=False)
    original=paypal._api
    def api(cfg,method,path,*args):
        if path.endswith('/verify-webhook-signature'):return {'verification_status':'SUCCESS'}
        return original(cfg,method,path,*args)
    monkeypatch.setattr(paypal,'_api',api)
    payload={'id':'refunded-completed-event','event_type':'PAYMENT.CAPTURE.COMPLETED',
             'resource':{'supplementary_data':{'related_ids':{'order_id':order['id']}}}}
    headers={key:'test' for key in ['paypal-auth-algo','paypal-cert-url','paypal-transmission-id','paypal-transmission-sig','paypal-transmission-time']}
    paypal.webhook(json.dumps(payload).encode(),headers)
    paypal.webhook(json.dumps(payload).encode(),headers)
    assert resources.state(account)['credits_micro']==1_000_000
    with auth.db() as c:
        assert c.execute('SELECT count(*) FROM paypal_events WHERE id=?',(payload['id'],)).fetchone()[0]==1
        assert c.execute('SELECT status FROM paypal_orders WHERE id=?',(local,)).fetchone()[0]=='paid'
def test_owner_capture_rejects_incomplete_refund_history_without_credit(account,provider,monkeypatch):
    local,order,_,_=history_fixture(account,provider,monkeypatch,paid=False)
    order['purchase_units'][0]['payments']['refunds'].pop()
    before=len(provider[1])
    with pytest.raises(ValueError,match='history is incomplete'):
        paypal.capture(account,local)
    assert resources.state(account)['credits_micro']==0
    assert not any(call[0]=='POST' for call in provider[1][before:])


def test_owner_capture_rechecks_new_history_gap_inside_financial_transaction(account,provider,monkeypatch):
    from app import paypal_dispute_history
    from app.regime_operation_fence import FenceBlocked
    local,_,_,_=history_fixture(account,provider,monkeypatch,paid=False)
    original=paypal.fulfill
    def fulfill_with_concurrent_gap(identifier,document,**kwargs):
        with auth.db() as c:
            order=dict(c.execute('SELECT * FROM paypal_orders WHERE id=?',(identifier,)).fetchone())
            cfg=paypal._keys(c)
        paypal_dispute_history.record_gap(order,cfg,())
        return original(identifier,document,**kwargs)
    monkeypatch.setattr(paypal,'fulfill',fulfill_with_concurrent_gap)
    with pytest.raises(FenceBlocked,match='Complete PayPal history'):
        paypal.capture(account,local)
    assert resources.state(account)['credits_micro']==0
    monkeypatch.setattr(paypal,'fulfill',original)
    assert service.reconcile_paypal(local)['ledger_reconciled']
    assert resources.state(account)['credits_micro']==1_000_000


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
