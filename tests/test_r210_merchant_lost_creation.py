"""Lost create response -> merchant discovery -> original refunds and wallet."""
import copy
import json
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlsplit

import pytest
from app import auth,paypal_payments as paypal,paypal_merchant_history as history
from app import paypal_merchant_reconcile as bridge,resource_accounts as resources
from app.regime_operation_fence import FenceBlocked
from test_r210_subscriptions import account as account,plan  # noqa:F401
from test_r210_paypal import provider as provider  # noqa:F401
from test_r210_checkout_reference_recovery import unknown_paypal
from test_r210_paypal_merchant_history import START,END


@pytest.fixture
def lost(account,provider,monkeypatch):
    local,pid,order=unknown_paypal(account,provider,monkeypatch)
    admin=auth.find_user('admin')['id']
    order['status']='COMPLETED'
    captures=[{'id':cid,'status':status,'amount':{'value':amount,'currency_code':'EUR'},
        'supplementary_data':{'related_ids':{'order_id':pid}}} for cid,status,amount in
        [('CAPTURE111','REFUNDED','3.00'),('CAPTURE222','PARTIALLY_REFUNDED','2.00')]]
    refunds=[{'id':rid,'status':'COMPLETED','amount':{'value':amount,'currency_code':'EUR'},
        'seller_payable_breakdown':{'total_refunded_amount':{'value':amount,'currency_code':'EUR'}},
        'links':[{'rel':'up','href':'https://api-m.sandbox.paypal.com/v2/payments/captures/'+cid}]}
        for rid,cid,amount in [('REFUND111','CAPTURE111','3.00'),('REFUND222','CAPTURE222','1.00')]]
    order['purchase_units'][0]['payments']={'captures':captures,'refunds':refunds}
    original=paypal._api;calls=[];rows=[];hook={'run':None}
    def api(cfg,method,path,*args):
        assert method=='GET','Recovery must not repost creation, capture or refund'
        calls.append(path)
        if hook['run']:hook['run'](cfg,path)
        if urlsplit(path).path=='/v1/reporting/transactions':
            return {'page':1,'total_pages':1,'total_items':len(rows),'transaction_details':copy.deepcopy(rows)}
        if '/payments/refunds/' in path:return copy.deepcopy(next(r for r in refunds if r['id']==path.rsplit('/',1)[1]))
        return original(cfg,method,path,*args)
    monkeypatch.setattr(paypal,'_api',api)
    def observe(kind='capture',reference='TXN',**changes):
        item={'transaction_id':'CAPTURE111' if kind=='capture' else 'REFUND111',
            'transaction_event_code':'T0006' if kind=='capture' else 'T1107','transaction_status':'S',
            'transaction_amount':{'currency_code':'EUR','value':'3.00' if kind=='capture' else '-3.00'},
            'paypal_reference_id_type':reference,'paypal_reference_id':pid if reference=='ODR' else 'CAPTURE111',
            'transaction_initiation_date':'2026-09-01T01:00:00Z',
            'transaction_note':local,'transaction_subject':local}
        item.update(changes);rows[:]=[{'transaction_info':item}]
        receipt=history.acquire(admin,START,END,confirm=True)
        snap=receipt['snapshot_id']
        return snap,history.digest(history.details(admin,snap)['items'][0])
    return {'local':local,'pid':pid,'order':order,'admin':admin,'observe':observe,'calls':calls,'hook':hook,'refunds':refunds}


@pytest.mark.parametrize('kind',['capture','refund'])
@pytest.mark.parametrize('reference',['TXN','ODR'])
def test_lost_create_discovers_original_order_and_applies_exact_net_once(lost,account,provider,kind,reference):
    snap,sha=lost['observe'](kind,reference)
    assert bridge.review(lost['admin'],snap)['counts']['unbound_candidates']==1
    result=bridge.reconcile(lost['admin'],snap,sha,confirm=True)
    assert result['ledger_reconciled'] and not result['transition_authorized']
    assert resources.state(account)['credits_micro']==1_000_000
    assert bridge.review(lost['admin'],snap)['counts']['known_candidates']==1
    bridge.reconcile(lost['admin'],snap,sha,confirm=True)
    assert resources.state(account)['credits_micro']==1_000_000
    with auth.db() as c:
        assert tuple(c.execute('SELECT state,attempts,provider_reference FROM regime_payment_outbox').fetchone())==('confirmed',1,lost['pid'])
        assert c.execute('SELECT status FROM regime_fence_operations').fetchone()[0]=='closed'
        assert c.execute('SELECT count(*) FROM paypal_captures').fetchone()[0]==2
        assert c.execute('SELECT count(*) FROM paypal_refunds').fetchone()[0]==2
        assert c.execute("SELECT count(*) FROM payment_reconciliation_events WHERE normalized_json LIKE '%checkout.reference.recovered%'").fetchone()[0]==1
    assert sum(call[0]=='POST' for call in provider[1])==1


@pytest.mark.parametrize('damage',['reference','custom','amount','intent','units','missing_local','merchant','history','row_amount','row_time','row_order','unattempted'])
def test_unknown_reference_requires_original_local_and_canonical_proof(lost,account,damage):
    changes={}
    if damage=='row_amount':changes['transaction_amount']={'currency_code':'EUR','value':'2.99'}
    if damage=='row_time':changes['transaction_initiation_date']='2020-09-01T01:00:00Z'
    if damage=='row_order':changes['paypal_reference_id']='ORDEROTHER';changes['paypal_reference_id_type']='ODR'
    snap,sha=lost['observe'](**changes);unit=lost['order']['purchase_units'][0]
    if damage=='reference':unit['reference_id']='other-order'
    if damage=='custom':unit['custom_id']='other-order'
    if damage=='amount':unit['amount']['value']='9.00'
    if damage=='intent':lost['order']['intent']='AUTHORIZE'
    if damage=='units':lost['order']['purchase_units'].append(copy.deepcopy(unit))
    if damage=='history':unit['payments']['refunds'].pop()
    with auth.db() as c:
        if damage=='missing_local':c.execute('DELETE FROM paypal_orders WHERE id=?',(lost['local'],))
        if damage=='merchant':c.execute("UPDATE paypal_orders SET client_fingerprint='foreign' WHERE id=?",(lost['local'],))
        if damage=='unattempted':c.execute('UPDATE regime_payment_outbox SET attempts=0')
    with pytest.raises((ValueError,FenceBlocked)):
        bridge.reconcile(lost['admin'],snap,sha,confirm=True)
    assert resources.state(account)['credits_micro']==0
    with auth.db() as c:
        row=c.execute('SELECT provider_order FROM paypal_orders WHERE id=?',(lost['local'],)).fetchone()
        assert row is None or row[0] is None
        assert c.execute('SELECT state FROM regime_payment_outbox').fetchone()[0]=='uncertain'
        assert c.execute('SELECT count(*) FROM paypal_captures').fetchone()[0]==0


@pytest.mark.parametrize('damage',['admin','config','local','canonical','snapshot','network'])
def test_change_during_discovery_never_commits_reference_or_money(lost,account,monkeypatch,damage):
    snap,sha=lost['observe']();reads=[]
    def hook(cfg,path):
        if '/checkout/orders/' not in path:return
        reads.append(path)
        if len(reads)!=3:return  # The binding service performs its own final GET.
        if damage=='network':raise OSError('readback unavailable')
        if damage=='canonical':lost['order']['status']='APPROVED'
        with auth.db() as c:
            if damage=='admin':c.execute("UPDATE users SET role='user' WHERE id=?",(lost['admin'],))
            if damage=='local':c.execute('UPDATE paypal_orders SET amount_cents=999 WHERE id=?',(lost['local'],))
            if damage=='snapshot':c.execute('DELETE FROM paypal_merchant_history WHERE id=?',(snap,))
        if damage=='config':paypal.settings({'client_secret':'rotated-fixture'})
    lost['hook']['run']=hook
    with pytest.raises((ValueError,PermissionError,FenceBlocked,OSError)):
        bridge.reconcile(lost['admin'],snap,sha,confirm=True)
    assert resources.state(account)['credits_micro']==0
    with auth.db() as c:
        assert c.execute('SELECT provider_order FROM paypal_orders').fetchone()[0] is None
        assert c.execute('SELECT state FROM regime_payment_outbox').fetchone()[0]=='uncertain'


def test_crash_after_reference_binding_recovers_without_recreating_checkout(lost,account,monkeypatch):
    from app import payment_reconcile_service as service
    snap,sha=lost['observe']();original=service.reconcile_paypal
    monkeypatch.setattr(service,'reconcile_paypal',lambda *a,**kw:(_ for _ in ()).throw(RuntimeError('response lost after binding')))
    with pytest.raises(RuntimeError):bridge.reconcile(lost['admin'],snap,sha,confirm=True)
    with auth.db() as c:
        assert c.execute('SELECT provider_order FROM paypal_orders').fetchone()[0]==lost['pid']
        assert c.execute('SELECT status FROM regime_fence_operations').fetchone()[0]=='open'
    assert resources.state(account)['credits_micro']==0
    monkeypatch.setattr(service,'reconcile_paypal',original)
    assert bridge.reconcile(lost['admin'],snap,sha,confirm=True)['ledger_reconciled']
    assert resources.state(account)['credits_micro']==1_000_000


@pytest.mark.parametrize('boundary',['reference','refund'])
def test_failure_inside_binding_or_settlement_rolls_back_its_whole_transaction(lost,account,monkeypatch,boundary):
    from app import payment_reconciliation as journal
    snap,sha=lost['observe']()
    module,name=(journal,'record_event') if boundary=='reference' else (paypal,'_apply_refund')
    original=getattr(module,name)
    monkeypatch.setattr(module,name,lambda *a,**kw:(_ for _ in ()).throw(RuntimeError('crash in atomic write')))
    with pytest.raises(RuntimeError):bridge.reconcile(lost['admin'],snap,sha,confirm=True)
    assert resources.state(account)['credits_micro']==0
    with auth.db() as c:
        assert c.execute('SELECT provider_order FROM paypal_orders').fetchone()[0]==(None if boundary=='reference' else lost['pid'])
        assert c.execute('SELECT state FROM regime_payment_outbox').fetchone()[0]==('uncertain' if boundary=='reference' else 'confirmed')
        assert c.execute('SELECT count(*) FROM paypal_captures').fetchone()[0]==0
        assert c.execute('SELECT count(*) FROM paypal_refunds').fetchone()[0]==0
    monkeypatch.setattr(module,name,original)
    bridge.reconcile(lost['admin'],snap,sha,confirm=True)
    assert resources.state(account)['credits_micro']==1_000_000


def test_concurrent_discovery_and_retry_preserve_one_reference_and_one_credit(lost,account):
    snap,sha=lost['observe']()
    def run(_):
        try:return bridge.reconcile(lost['admin'],snap,sha,confirm=True)
        except FenceBlocked:return None  # A stale pre-binding context must be reread.
    with ThreadPoolExecutor(max_workers=4) as pool:results=list(pool.map(run,range(4)))
    assert any(r and r['ledger_reconciled'] for r in results)
    bridge.reconcile(lost['admin'],snap,sha,confirm=True)
    assert resources.state(account)['credits_micro']==1_000_000


@pytest.mark.parametrize('kind',['subscription','subscription_reversal','legacy-unknown'])
def test_missing_original_subscription_quote_is_not_reconstructed(lost,account,kind):
    snap,sha=lost['observe']()
    with auth.db() as c:c.execute('UPDATE paypal_orders SET kind=? WHERE id=?',(kind,lost['local']))
    with pytest.raises(FenceBlocked,match='Original subscription quote evidence'):
        bridge.reconcile(lost['admin'],snap,sha,confirm=True)
    with auth.db() as c:
        assert c.execute('SELECT provider_order FROM paypal_orders').fetchone()[0] is None
        assert c.execute('SELECT state FROM regime_payment_outbox').fetchone()[0]=='uncertain'
    assert resources.state(account)['credits_micro']==0


@pytest.mark.parametrize('boundary',['order','refund','capture','related'])
def test_malformed_discovery_reply_leaves_original_dispatch_uncertain(lost,account,monkeypatch,boundary):
    snap,sha=lost['observe']('refund' if boundary=='refund' else 'capture')
    original=paypal._api
    def api(cfg,method,path,*args):
        if (boundary=='order' and '/checkout/orders/' in path
                or boundary=='refund' and '/payments/refunds/' in path
                or boundary=='capture' and '/payments/captures/' in path):return None
        result=original(cfg,method,path,*args)
        if boundary=='related' and '/payments/captures/' in path:result['supplementary_data']={'related_ids':[]}
        return result
    monkeypatch.setattr(paypal,'_api',api)
    with pytest.raises((ValueError,FenceBlocked)):
        bridge.reconcile(lost['admin'],snap,sha,confirm=True)
    with auth.db() as c:
        assert c.execute('SELECT provider_order FROM paypal_orders').fetchone()[0] is None
        assert c.execute('SELECT state FROM regime_payment_outbox').fetchone()[0]=='uncertain'
    assert resources.state(account)['credits_micro']==0


def test_existing_private_admin_action_discovers_reference_without_payer_labels(lost,account,monkeypatch):
    from fastapi.testclient import TestClient
    from app import main
    from test_r210_legal_documents import cookie
    monkeypatch.setattr(main,'NATIVE_SINGLE_USER',False)
    snap,sha=lost['observe']();path='/api/admin/paypal/merchant-history/'+snap+'/reconcile'
    body={'observation_sha256':sha,'confirm':True}
    with TestClient(main.app) as client:
        assert client.post(path,json=body,headers={'X-MTA-Request':'1'}).status_code==401
        client.cookies.update(cookie(account))
        assert client.post(path,json=body,headers={'X-MTA-Request':'1'}).status_code==403
        client.cookies.update(cookie(lost['admin']))
        assert client.post(path,json=body).status_code==403
        assert client.post(path,json={**body,'_merchant_context':{}},headers={'X-MTA-Request':'1'}).status_code==422
        response=client.post(path,json=body,headers={'X-MTA-Request':'1'})
        assert response.status_code==200,response.text
        assert response.headers['cache-control']=='no-store' and response.json()['ledger_reconciled']
        assert 'claim_token' not in json.dumps(response.json())
    assert resources.state(account)['credits_micro']==1_000_000
