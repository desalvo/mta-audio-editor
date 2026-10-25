"""Death after committed dispatch barrier, ledger rollback and financial variants."""
import copy
import json
import os
import sqlite3
from pathlib import Path
import subprocess
import sys

import pytest
from app import auth,operator_refunds as refunds,paypal_payments as paypal,resource_accounts
from app.regime_operation_fence import FenceBlocked
from test_r210_operator_refunds import stripe_env as stripe_env,paypal_env as paypal_env,actor,create,body,current,audit  # noqa: F401
from test_r210_subscriptions import account as account  # noqa: F401
from test_r210_paypal import provider as provider  # noqa: F401


def test_real_child_exit_after_committed_uncertainty_is_recovered_without_reexecution(stripe_env,tmp_path,account):
    item=create(stripe_env);receipt=tmp_path/'remote-refund-receipt.json'
    code='''import json,os,sys
from pathlib import Path
from app import operator_refunds as refunds
refunds._reconcile=lambda *args:None
def crash(row,config):
    doc={'id':'re_childrefund','object':'refund','payment_intent':row['target'],'charge':'ch_test','currency':'eur','amount':row['amount_cents'],'metadata':{'mta_refund':'mta-refund-'+row['id']},'status':'succeeded'}
    Path(sys.argv[3]).write_text(json.dumps(doc))
    os._exit(23)
refunds._dispatch=crash
refunds.execute(int(sys.argv[1]),sys.argv[2],0)
'''
    # The child uses the actual same SQLite database and dies abruptly. Only
    # provider execution/readback is simulated; no real endpoint is reachable.
    completed=subprocess.run([sys.executable,'-c',code,str(actor()),item['id'],str(receipt)],cwd=Path(__file__).resolve().parents[1],env=os.environ.copy(),capture_output=True,text=True,timeout=30)
    assert completed.returncode==23,completed.stderr
    doc=json.loads(receipt.read_text());stripe_env['refunds'][doc['id']]=doc
    row=current(item['id']);assert row['state']=='uncertain' and row['provider_reference'] is None and audit()['pending']==1
    with pytest.raises(FenceBlocked):refunds.execute(actor(),item['id'],row['revision'])
    assert refunds.verify(actor(),item['id'],row['revision'],doc['id'])['state']=='settled'
    assert not stripe_env['posts'] and resource_accounts.state(account)['credits_micro']==3_000_000


def test_external_balance_change_invalidates_prepared_quote(stripe_env,account):
    item=create(stripe_env)
    stripe_env['refunds']['re_external']={'id':'re_external','object':'refund','payment_intent':'pi_test','charge':'ch_test','currency':'eur','amount':100,'status':'succeeded','metadata':{}}
    with pytest.raises(FenceBlocked,match='quote changed'):refunds.execute(actor(),item['id'],0)
    assert not stripe_env['posts'];assert resource_accounts.state(account)['credits_micro']==4_000_000
    assert current(item['id'])['state']=='prepared'
    refunds.cancel(actor(),item['id'],0)
    new=create(stripe_env,key='new-quote-after-external',amount=400)
    assert refunds.execute(actor(),new['id'],0)['state']=='settled'


@pytest.mark.parametrize('field,value',[('user_id',1),('amount_cents',600),('session_id','cs_other')])
def test_original_payment_drift_is_rejected_before_provider_read_or_write(stripe_env,field,value):
    item=create(stripe_env);before=len(stripe_env['gets'])
    with auth.db() as c:
        # Fixed test-only identifiers, never browser-supplied SQL.
        c.execute({'user_id':'UPDATE credit_purchase_orders SET user_id=? WHERE id=?','amount_cents':'UPDATE credit_purchase_orders SET amount_cents=? WHERE id=?','session_id':'UPDATE credit_purchase_orders SET session_id=? WHERE id=?'}[field],(value,stripe_env['order']))
    with pytest.raises(FenceBlocked,match='identity changed'):refunds.execute(actor(),item['id'],0)
    assert not stripe_env['posts'] and len(stripe_env['gets'])==before


def test_reason_bound_includes_whitespace_and_rejects_before_provider_io(stripe_env):
    request=body(stripe_env['order']);request['reason']=' '*600+'valid reason'
    with pytest.raises(ValueError):refunds.prepare(actor(),request)
    assert not stripe_env['posts'] and not stripe_env['gets']


def test_wallet_commit_failure_keeps_refund_pending_then_reconciles_once(stripe_env,account,monkeypatch):
    from app import payment_reconciliation
    item=create(stripe_env);original=payment_reconciliation._stripe_apply
    # Preserve the real signature and fail only after applying a refund.
    def after_apply(c,event_id,data,order):
        result=original(c,event_id,data,order)
        row=c.execute('SELECT refunded_cents FROM credit_purchase_orders WHERE id=?',(stripe_env['order'],)).fetchone()
        if row and row[0]:raise ValueError('simulated ledger failure')
        return result
    monkeypatch.setattr(payment_reconciliation,'_stripe_apply',after_apply)
    result=refunds.execute(actor(),item['id'],0);assert result['state']=='pending'
    assert resource_accounts.state(account)['credits_micro']==5_000_000
    monkeypatch.setattr(payment_reconciliation,'_stripe_apply',original)
    assert refunds.verify(actor(),item['id'],result['revision'])['state']=='settled'
    assert resource_accounts.state(account)['credits_micro']==3_000_000 and len(stripe_env['posts'])==1


def test_role_revoked_during_readback_prevents_dispatch(stripe_env,monkeypatch):
    item=create(stripe_env);original=refunds._reconcile;uid=actor()
    def revoke(*args):
        original(*args)
        with auth.db() as c:c.execute("UPDATE users SET role='user' WHERE id=?",(uid,))
    monkeypatch.setattr(refunds,'_reconcile',revoke)
    with pytest.raises(FenceBlocked):refunds.execute(uid,item['id'],0)
    assert not stripe_env['posts'] and current(item['id'])['state']=='prepared'


def test_pending_paypal_needs_completed_receipt_and_canonical_capture(paypal_env,account):
    item=create(paypal_env,provider='paypal',target=paypal_env['target']);paypal_env['status']='PENDING'
    result=refunds.execute(actor(),item['id'],0);assert result['state']=='pending'
    assert resource_accounts.state(account)['credits_micro']==5_000_000
    doc=paypal_env['refunds'][result['provider_reference']];doc['status']='COMPLETED'
    paypal_env['canonical']['purchase_units'][0]['payments']['captures'][0]['status']='PARTIALLY_REFUNDED'
    assert refunds.verify(actor(),item['id'],result['revision'])['state']=='settled'
    assert resource_accounts.state(account)['credits_micro']==3_000_000 and len(paypal_env['posts'])==1


def test_multicapture_history_remaining_capture_refund(account,provider,monkeypatch):
    from test_r210_paypal_history_reconciliation import history_fixture
    local,canonical,objects,_=history_fixture(account,provider,monkeypatch,paid=True)
    original=paypal._api;posts=[]
    def api(cfg,method,path,payload=None,request_id=None):
        if method=='GET' and path.startswith('/v1/customer/disputes?'):return {'items':[],'links':[]}
        if method=='POST':
            assert path=='/v2/payments/captures/CAPTURE222/refund';posts.append(path)
            doc={'id':'REFUND333','status':'COMPLETED','custom_id':payload['custom_id'],'amount':copy.deepcopy(payload['amount']),
                 'seller_payable_breakdown':{'total_refunded_amount':{'value':'2.00','currency_code':'EUR'}},
                 'links':[{'rel':'up','href':paypal.BASES['sandbox']+'/v2/payments/captures/CAPTURE222'}]}
            objects[doc['id']]=doc;payments=canonical['purchase_units'][0]['payments'];payments['refunds'].append(doc);payments['captures'][1]['status']='REFUNDED';return copy.deepcopy(doc)
        return original(cfg,method,path)
    monkeypatch.setattr(paypal,'_api',api)
    item=refunds.prepare(actor(),body(local,provider='paypal',target='CAPTURE222',amount=100))
    assert refunds.execute(actor(),item['id'],0)['state']=='settled'
    assert resource_accounts.state(account)['credits_micro']==0 and len(posts)==1


@pytest.mark.parametrize('kind',['subscription','subscription_reversal'])
def test_paypal_subscription_and_repayment_refunds_preserve_exact_receivable(account,provider,monkeypatch,kind):
    from test_r210_subscription_repayment_e2e import checkout,balance
    from test_r210_paypal_reconciliation_e2e import setup_order,HEADERS
    if kind=='subscription':
        local,canonical,_,_=setup_order(account,provider,monkeypatch,subscription=True,before_capture=True)
    else:
        _,_,event,_=setup_order(account,provider,monkeypatch,subscription=True)
        paypal.webhook(json.dumps(event).encode(),HEADERS)
        local=checkout(account)['order_id'];paypal.capture(account,local)
        with auth.db() as c:pid=c.execute('SELECT provider_order FROM paypal_orders WHERE id=?',(local,)).fetchone()[0]
        canonical=provider[0][pid]
    # Install canonical payment/refund GET handling for these existing paid or
    # newly reconciled orders; original webhook verification remains simulated.
    captures=canonical['purchase_units'][0]['payments']['captures'];objects={};posts=[]
    if kind=='subscription':
        # setup_order's original refund is intentionally not yet in the order
        # history; start from all captures completed and no operator refund.
        for cap in captures:cap['status']='COMPLETED'
    def api(cfg,method,path,payload=None,request_id=None):
        if method=='GET' and path.startswith('/v1/customer/disputes?'):return {'items':[],'links':[]}
        if method=='POST':
            cid=path.split('/')[-2];capture=next(x for x in captures if x['id']==cid);posts.append(path)
            doc={'id':'REFUNDOPERATOR1','status':'COMPLETED','custom_id':payload['custom_id'],'amount':copy.deepcopy(payload['amount']),
                 'seller_payable_breakdown':{'total_refunded_amount':copy.deepcopy(payload['amount'])},
                 'links':[{'rel':'up','href':paypal.BASES['sandbox']+'/v2/payments/captures/'+cid}]}
            objects[doc['id']]=doc;canonical['purchase_units'][0]['payments']['refunds']=[doc];capture['status']='PARTIALLY_REFUNDED';return copy.deepcopy(doc)
        if '/payments/refunds/' in path:return copy.deepcopy(objects[path.rsplit('/',1)[1]])
        if '/payments/captures/' in path:return copy.deepcopy(next(x for x in captures if x['id']==path.rsplit('/',1)[1]))
        assert path=='/v2/checkout/orders/'+canonical['id'];return copy.deepcopy(canonical)
    monkeypatch.setattr(paypal,'_api',api)
    item=refunds.prepare(actor(),body(local,provider='paypal',target=captures[0]['id'],amount=100))
    assert refunds.execute(actor(),item['id'],0)['state']=='settled'
    assert resource_accounts.state(account)['credits_micro']==0 and len(posts)==1
    if kind=='subscription':
        assert resource_accounts.transactions(account)['subscription_reversals'][0]['due_micro']==1_000_000
    else:assert balance(account)['due_micro']==1_000_000


@pytest.mark.parametrize('corruption',['context','revision','receipt','schema'])
def test_corrupt_journal_cannot_dispatch_or_clear_drain(stripe_env,corruption):
    item=create(stripe_env)
    with auth.db() as c:
        if corruption=='context':
            with pytest.raises(sqlite3.IntegrityError):c.execute("UPDATE operator_refunds SET context_json='{}'")
            assert audit()['verified'];return
        if corruption=='revision':c.execute('UPDATE operator_refunds SET revision=4')
        if corruption=='receipt':c.execute("UPDATE operator_refunds SET state='settled'")
        if corruption=='schema':c.execute('DROP TABLE operator_refund_audit')
    with pytest.raises(FenceBlocked):refunds.execute(actor(),item['id'],0)
    assert not stripe_env['posts'] and not audit()['verified']


def test_refund_identity_audit_and_deletion_require_retired_owner_authorization(stripe_env,account,monkeypatch,tmp_path):
    from app import account_lifecycle as life,account_erasure,ai_arranger_runtime
    monkeypatch.setattr(auth,'send_mail',lambda *args,**kwargs:None)
    monkeypatch.setattr(ai_arranger_runtime,'_ROOT',tmp_path/'isolated-queue')
    item=create(stripe_env)
    with auth.db() as c:
        selected,_=life._rows_for_user(c,account)
        assert any(row['id']==item['id'] for row in selected['operator_refunds'].values())
        assert len(selected['operator_refund_audit'])==1
        assert any(row['operation_id']=='operator-refund:'+item['id'] for row in selected['regime_fence_operations'].values())
        for sql in ('DELETE FROM operator_refunds','DELETE FROM operator_refund_audit',"UPDATE operator_refund_audit SET state='settled'",'UPDATE operator_refunds SET amount_cents=1'):
            with pytest.raises(sqlite3.IntegrityError):c.execute(sql)
    life.register(account);life.retire(account,actor())
    with pytest.raises(FenceBlocked):account_erasure.erase(account,actor(),confirmed=True)
    assert auth.get_user(account) and audit()['pending']==1
    assert not list(life.root().glob('erase-*.json'))
    refunds.cancel(actor(),item['id'],0)
    assert account_erasure.erase(account,actor(),confirmed=True)['done']
    assert auth.get_user(account) is None
    with auth.db() as c:
        assert not c.execute('SELECT 1 FROM operator_refunds').fetchone()
        assert not c.execute('SELECT 1 FROM operator_refund_audit').fetchone()
        assert not c.execute('SELECT 1 FROM regime_fence_operations WHERE operation_id=?',('operator-refund:'+item['id'],)).fetchone()


def test_operator_refund_actually_clears_surplus_repayment_liability(account,provider,monkeypatch):
    from test_r210_subscription_repayment_e2e import checkout,balance,risk,capture_id
    from test_r210_paypal_reconciliation_e2e import setup_order,HEADERS
    _,_,event,_=setup_order(account,provider,monkeypatch,subscription=True)
    paypal.webhook(json.dumps(event).encode(),HEADERS)
    first=checkout(account)['order_id'];paypal.capture(account,first);risk(monkeypatch,first)
    second=checkout(account,key='refund-surplus-repayment')['order_id'];paypal.capture(account,second);risk(monkeypatch,first,resolved=True)
    assert sum(p['refund_due_micro'] for p in balance(account)['payments'])==3_000_000
    with auth.db() as c:pid=c.execute('SELECT provider_order FROM paypal_orders WHERE id=?',(second,)).fetchone()[0]
    canonical=provider[0][pid];cid=capture_id(second);capture=canonical['purchase_units'][0]['payments']['captures'][0];objects={};posts=[]
    def api(cfg,method,path,payload=None,request_id=None):
        if method=='GET' and path.startswith('/v1/customer/disputes?'):return {'items':[],'links':[]}
        if method=='POST':
            assert path=='/v2/payments/captures/'+cid+'/refund';posts.append(path)
            doc={'id':'SURPLUSREFUND1','status':'COMPLETED','custom_id':payload['custom_id'],'amount':copy.deepcopy(payload['amount']),
                 'seller_payable_breakdown':{'total_refunded_amount':copy.deepcopy(payload['amount'])},
                 'links':[{'rel':'up','href':paypal.BASES['sandbox']+'/v2/payments/captures/'+cid}]}
            objects[doc['id']]=doc;canonical['purchase_units'][0]['payments']['refunds']=[doc];capture['status']='REFUNDED';return copy.deepcopy(doc)
        if '/payments/refunds/' in path:return copy.deepcopy(objects[path.rsplit('/',1)[1]])
        if '/payments/captures/' in path:return copy.deepcopy(capture)
        assert path=='/v2/checkout/orders/'+pid;return copy.deepcopy(canonical)
    monkeypatch.setattr(paypal,'_api',api)
    item=refunds.prepare(actor(),body(second,provider='paypal',target=cid,amount=300))
    assert refunds.execute(actor(),item['id'],0)['state']=='settled'
    state=balance(account);assert state['due_micro']==0 and sum(p['refund_due_micro'] for p in state['payments'])==0
    assert resource_accounts.state(account)['credits_micro']==0 and len(posts)==1
