"""Known-order authenticated discovery -> immutable journal -> actual wallet."""
import copy
import json
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import parse_qs,urlsplit

import pytest
from app import auth,paypal_payments as paypal,resource_accounts as resources
from app import payment_reconcile_service as service,payment_reconciliation as journal,owner_payments
from app import paypal_dispute_history as history
from app.regime_operation_fence import FenceBlocked
from test_r210_subscriptions import account as account  # noqa: F401
from test_r210_paypal import provider as provider  # noqa: F401
from test_r210_paypal_reconciliation_e2e import setup_order


def fixture(account,provider,monkeypatch,*,paid=False,multi=False,subscription=False):
    local,order,_,_=setup_order(account,provider,monkeypatch,before_capture=not paid,subscription=subscription)
    tx=[{'seller_transaction_id':'CAPTURE111','gross_amount':{'value':'3.00','currency_code':'EUR'}}]
    if multi:tx.append({'seller_transaction_id':'CAPTURE222','gross_amount':{'value':'2.00','currency_code':'EUR'}})
    docs={'PP-D-123':{'dispute_id':'PP-D-123','status':'UNDER_REVIEW','update_time':'2026-10-24T01:00:00Z',
                      'dispute_amount':{'value':'5.00' if multi else '2.00','currency_code':'EUR'},'disputed_transactions':tx}}
    original=paypal._api;calls=[];hook={'run':None}
    def api(cfg,method,path,*args):
        if method!='GET':raise AssertionError('Discovery must never collect/refund money')
        calls.append(path)
        if hook['run']:
            override=hook['run'](cfg,path)
            if override is not None:return override
        if path.startswith('/v1/customer/disputes?'):
            query=parse_qs(urlsplit(path).query);cid=query['disputed_transaction_id'][0]
            assert set(query)=={'disputed_transaction_id','page_size','page'} and query['page_size']==['50']
            items=[{k:copy.deepcopy(d[k]) for k in ('dispute_id','status','update_time','dispute_amount')} for d in docs.values() if any(tx['seller_transaction_id']==cid for tx in d['disputed_transactions'])]
            return {'items':items,'links':[]}
        if path.startswith('/v1/customer/disputes/'):
            return copy.deepcopy(docs[path.rsplit('/',1)[1]])
        return original(cfg,method,path,*args)
    monkeypatch.setattr(paypal,'_api',api)
    return local,order,docs,calls,hook


def report():
    with auth.db() as c:return journal.report(c)


@pytest.mark.parametrize('paid',[False,True])
@pytest.mark.parametrize('multi',[False,True])
def test_discovery_funds_only_net_and_replays_idempotently(account,provider,monkeypatch,paid,multi):
    local,_,_,calls,_=fixture(account,provider,monkeypatch,paid=paid,multi=multi)
    result=service.reconcile_paypal(local)
    assert result['ledger_reconciled'] and result['disputes']==1 and not result['financial_review_pending'] and not result['transition_authorized']
    assert resources.state(account)['credits_micro']==(0 if multi else 3_000_000)
    with ThreadPoolExecutor(max_workers=3) as pool:list(pool.map(lambda _:service.reconcile_paypal(local),range(3)))
    assert resources.state(account)['credits_micro']==(0 if multi else 3_000_000)
    current=report();assert current['verified'] and current['pending']==0
    assert current['positions'][0]['held_minor']==(500 if multi else 200)
    assert all('capture?' not in p and not p.endswith('/capture') for p in calls)
    assert sum(p.startswith('/v1/customer/disputes?') for p in calls)==16


@pytest.mark.parametrize('multi',[False,True])
@pytest.mark.parametrize('outcome',['RESOLVED_SELLER_FAVOUR','CANCELED_BY_BUYER','RESOLVED_BUYER_FAVOUR'])
def test_discovered_final_outcomes_and_old_webhooks_cannot_reopen(account,provider,monkeypatch,multi,outcome):
    local,_,docs,_,_=fixture(account,provider,monkeypatch,multi=multi)
    service.reconcile_paypal(local);old=copy.deepcopy(docs['PP-D-123'])
    docs['PP-D-123'].update(status='RESOLVED',update_time='2026-10-24T02:00:00Z',dispute_outcome={'outcome_code':outcome})
    service.reconcile_paypal(local)
    expected=(0 if multi else 3_000_000) if outcome=='RESOLVED_BUYER_FAVOUR' else 5_000_000
    assert resources.state(account)['credits_micro']==expected and report()['pending']==0
    docs['PP-D-123']=old;service.reconcile_paypal(local)
    assert resources.state(account)['credits_micro']==expected
    with auth.db() as c:
        assert all(row[0] in ('released','permanent') for row in c.execute('SELECT status FROM paypal_financial_holds'))


@pytest.mark.parametrize('outcome',['RESOLVED_WITH_PAYOUT','RESOLVED_WITH_OTHER','UNKNOWN'])
@pytest.mark.parametrize('multi',[False,True])
def test_payouts_stay_pending_private_and_can_resolve_with_later_exact_outcome(account,provider,monkeypatch,outcome,multi):
    local,_,docs,_,_=fixture(account,provider,monkeypatch,multi=multi)
    docs['PP-D-123'].update(status='RESOLVED',dispute_outcome={'outcome_code':outcome})
    result=service.reconcile_paypal(local);assert result['financial_review_pending']
    assert resources.state(account)['credits_micro']==(0 if multi else 3_000_000)
    item=owner_payments.history(account)['items'][0];assert item['financial_review_pending'] and item['financial_held_minor']==(500 if multi else 200)
    assert owner_payments.history(1)['items']==[]
    serialized=json.dumps(owner_payments.history(account))
    assert all(x not in serialized for x in ['PP-D-123','CAPTURE111','test-client','UNDER_REVIEW'])
    docs['PP-D-123'].update(update_time='2026-10-24T03:00:00Z',dispute_outcome={'outcome_code':'RESOLVED_SELLER_FAVOUR'})
    service.reconcile_paypal(local);assert resources.state(account)['credits_micro']==5_000_000 and report()['pending']==0


@pytest.mark.parametrize('defect',['missing_items','non_list','summary_status','summary_amount','summary_time','wrong_detail','foreign_capture','duplicate_capture','partial_multi','negative','currency','bad_time','naive_time','empty_transactions','missing_gross','gross_mismatch','single_gross_mismatch','incomplete_membership','collection_changed','detail_changed','order_changed','http_error','missing_known'])
def test_unverifiable_history_never_funds_and_retains_durable_gap(account,provider,monkeypatch,defect):
    local,order,docs,calls,hook=fixture(account,provider,monkeypatch,multi=defect in ('partial_multi','missing_gross','gross_mismatch','incomplete_membership'))
    document=docs['PP-D-123'];reads=[]
    if defect=='foreign_capture':document['disputed_transactions'][0]['seller_transaction_id']='CAPTURE999'
    if defect=='duplicate_capture':document['disputed_transactions']*=2
    if defect=='partial_multi':document['dispute_amount']['value']='4.00'
    if defect=='negative':document['dispute_amount']['value']='-1'
    if defect=='currency':document['dispute_amount']['currency_code']='USD'
    if defect=='bad_time':document['update_time']='2026-13-99T01:00:00Z'
    if defect=='naive_time':document['update_time']='2026-10-24T01:00:00'
    if defect=='empty_transactions':document['disputed_transactions']=[]
    if defect=='missing_gross':document['disputed_transactions'][0].pop('gross_amount')
    if defect in ('gross_mismatch','single_gross_mismatch'):document['disputed_transactions'][0]['gross_amount']['value']='2.00'
    def override(cfg,path):
        reads.append(path)
        if path.startswith('/v1/customer/disputes?'):
            cid=parse_qs(urlsplit(path).query)['disputed_transaction_id'][0]
            if defect=='missing_items':return {'links':[]}
            if defect=='non_list':return {'items':{}}
            if defect=='http_error':raise ValueError('Simulated permission/HTTP failure')
            if defect in ('foreign_capture','empty_transactions'):return {'items':[{k:document[k] for k in ('dispute_id','status','update_time','dispute_amount')}],'links':[]}
            if defect in ('summary_status','summary_amount','summary_time') and cid=='CAPTURE111':
                row={k:copy.deepcopy(document[k]) for k in ('dispute_id','status','update_time','dispute_amount')}
                row[{'summary_status':'status','summary_amount':'dispute_amount','summary_time':'update_time'}[defect]]='bad';return {'items':[row],'links':[]}
            if defect=='incomplete_membership' and cid=='CAPTURE222':return {'items':[],'links':[]}
            if defect=='collection_changed' and sum(x.startswith('/v1/customer/disputes?') for x in reads)>2:return {'items':[],'links':[]}
        if path=='/v1/customer/disputes/PP-D-123':
            if defect=='wrong_detail':return {**document,'dispute_id':'PP-D-999'}
            if defect=='detail_changed' and reads.count(path)>1:return {**document,'update_time':'2026-10-24T05:00:00Z'}
        if defect=='order_changed' and path.startswith('/v2/checkout/orders/') and reads.count(path)>=3:return {**copy.deepcopy(order),'status':'APPROVED'}
    hook['run']=override
    if defect=='missing_known':
        hook['run']=None;service.reconcile_paypal(local);assert resources.state(account)['credits_micro']==3_000_000
        docs.clear();hook['run']=override
    with pytest.raises((ValueError,FenceBlocked)):service.reconcile_paypal(local)
    assert resources.state(account)['credits_micro']==(3_000_000 if defect=='missing_known' else 0)
    current=report();assert current['pending']>=1
    assert owner_payments.history(account)['items'][0]['financial_review_pending']
    # Repeated failures reuse the pending gap instead of creating duplicates.
    before=current['pending']
    with pytest.raises((ValueError,FenceBlocked)):service.reconcile_paypal(local)
    assert report()['pending']==before


def test_gap_recovery_is_atomic_and_later_gap_never_reopens_an_immutable_event(account,provider,monkeypatch):
    local,_,_,_,hook=fixture(account,provider,monkeypatch)
    def bad(cfg,path):
        if path.startswith('/v1/customer/disputes?'):return {}
    hook['run']=bad
    with pytest.raises(ValueError):service.reconcile_paypal(local)
    with auth.db() as c:first=dict(c.execute("SELECT * FROM payment_reconciliation_events WHERE state='pending'").fetchone())
    hook['run']=None;original=paypal._apply_risk
    monkeypatch.setattr(paypal,'_apply_risk',lambda *args:(_ for _ in ()).throw(RuntimeError('after funding')))
    with pytest.raises(RuntimeError):service.reconcile_paypal(local)
    assert resources.state(account)['credits_micro']==0 and report()['pending']==1
    monkeypatch.setattr(paypal,'_apply_risk',original);service.reconcile_paypal(local)
    assert resources.state(account)['credits_micro']==3_000_000 and report()['pending']==0
    hook['run']=bad
    with pytest.raises(ValueError):service.reconcile_paypal(local)
    with auth.db() as c:
        rows=[dict(x) for x in c.execute("SELECT * FROM payment_reconciliation_events WHERE event_id LIKE 'reconcile:history-gap:%'")]
        assert len(rows)==2 and {x['state'] for x in rows}=={'applied','pending'}
        old=next(x for x in rows if x['event_id']==first['event_id']);assert all(old[k]==first[k] for k in ('digest','normalized_json','created_at','order_id'))


@pytest.mark.parametrize('change',['owner','merchant','amount','kind','provider','epoch'])
def test_original_context_drift_after_remote_discovery_never_settles(account,provider,monkeypatch,change):
    local,_,_,_,hook=fixture(account,provider,monkeypatch);order_reads=[]
    def drift(cfg,path):
        if path.startswith('/v2/checkout/orders/'):
            order_reads.append(path)
            if len(order_reads)==3:
                with auth.db() as c:
                    if change=='owner':c.execute('UPDATE paypal_orders SET user_id=1 WHERE id=?',(local,))
                    if change=='amount':c.execute('UPDATE paypal_orders SET amount_cents=600 WHERE id=?',(local,))
                    if change=='kind':c.execute("UPDATE paypal_orders SET kind='subscription' WHERE id=?",(local,))
                    if change=='provider':c.execute("UPDATE paypal_orders SET provider_order='OTHER123' WHERE id=?",(local,))
                    if change=='epoch':c.execute('UPDATE regime_fence_state SET revision=revision+1')
                if change=='merchant':paypal.settings({'client_secret':'rotated-secret'})
    hook['run']=drift
    with pytest.raises((ValueError,FenceBlocked)):service.reconcile_paypal(local)
    assert resources.state(account)['credits_micro']==0


@pytest.mark.parametrize('subscription',[False,True])
def test_opposing_final_history_is_pending_and_never_releases_permanent_loss(account,provider,monkeypatch,subscription):
    local,_,docs,_,_=fixture(account,provider,monkeypatch,subscription=subscription)
    docs['PP-D-123'].update(status='RESOLVED',dispute_outcome={'outcome_code':'RESOLVED_BUYER_FAVOUR'})
    service.reconcile_paypal(local)
    docs['PP-D-123'].update(update_time='2026-10-24T03:00:00Z',dispute_outcome={'outcome_code':'RESOLVED_SELLER_FAVOUR'})
    assert service.reconcile_paypal(local)['financial_review_pending']
    assert resources.state(account)['credits_micro']==(0 if subscription else 3_000_000)
    assert report()['pending']==1
    if subscription:assert report()['subscription_risk_micro']==2_000_000


def pagination_fixture(account,provider,monkeypatch):
    local,order,docs,calls,hook=fixture(account,provider,monkeypatch)
    docs['PP-D-123']['dispute_amount']['value']='1.00'
    docs['PP-D-456']=copy.deepcopy(docs['PP-D-123']);docs['PP-D-456']['dispute_id']='PP-D-456'
    def pages(cfg,path):
        if not path.startswith('/v1/customer/disputes?'):return None
        query=parse_qs(urlsplit(path).query)
        if query['disputed_transaction_id']!=['CAPTURE111']:return {'items':[],'links':[]}
        page=int(query['page'][0]);did=['PP-D-123','PP-D-456'][page-1]
        row={k:docs[did][k] for k in ('dispute_id','status','update_time','dispute_amount')}
        link={'rel':'next','method':'GET','href':'https://api-m.sandbox.paypal.com/v1/customer/disputes?disputed_transaction_id=CAPTURE111&page_size=50&page=2'}
        return {'items':[copy.deepcopy(row)],'links':[link] if page==1 else []}
    hook['run']=pages
    return local,order,docs,calls,hook,pages


def test_complete_two_page_readback_applies_each_dispute_once(account,provider,monkeypatch):
    local,_,_,calls,_,_=pagination_fixture(account,provider,monkeypatch)
    assert service.reconcile_paypal(local)['disputes']==2
    assert resources.state(account)['credits_micro']==3_000_000
    assert sum('page=2' in p for p in calls)==2
    service.reconcile_paypal(local);assert resources.state(account)['credits_micro']==3_000_000


@pytest.mark.parametrize('defect',['host','environment','credentials','port','fragment','path','filter','page','size','extra_query','duplicate_query','method','duplicate_link','empty_continuation','duplicate_row','no_links_list','token','control','backslash','object_bound','page_bound','request_bound'])
def test_pagination_failures_do_not_follow_untrusted_links_or_grant_credit(account,provider,monkeypatch,defect):
    local,_,_,calls,hook,pages=pagination_fixture(account,provider,monkeypatch)
    def bad(cfg,path):
        result=pages(cfg,path)
        if result is None:return None
        if 'page=2' in path and defect=='duplicate_row':result['items'][0]['dispute_id']='PP-D-123'
        if not result['links']:return result
        link=result['links'][0];url=link['href']
        changes={'host':url.replace('api-m.sandbox.paypal.com','evil.test'),'environment':url.replace('api-m.sandbox.paypal.com','api-m.paypal.com'),'credentials':url.replace('https://','https://user:pass@'),'port':url.replace('.com/','.com:444/'),'fragment':url+'#x','path':url.replace('/customer/disputes?','/customer/disputes/PP-D-123?'),'filter':url.replace('CAPTURE111','CAPTURE222'),'page':url.replace('page=2','page=1'),'size':url.replace('size=50','size=100'),'extra_query':url+'&status=RESOLVED','duplicate_query':url+'&page=2','token':url.replace('page=2','next_page_token=abc'),'control':url+'\n','backslash':url+'\\'}
        if defect in changes:link['href']=changes[defect]
        if defect=='method':link['method']='POST'
        if defect=='duplicate_link':result['links']*=2
        if defect=='empty_continuation':result['items']=[]
        if defect=='no_links_list':result['links']={}
        return result
    if defect=='object_bound':monkeypatch.setattr(history,'MAX_DISPUTES',1)
    if defect=='page_bound':monkeypatch.setattr(history,'MAX_PAGES',1)
    if defect=='request_bound':monkeypatch.setattr(history,'MAX_READS',1)
    hook['run']=bad
    with pytest.raises(ValueError):service.reconcile_paypal(local)
    assert resources.state(account)['credits_micro']==0 and report()['pending']>=1
    assert all(p.startswith(('/v1/customer/disputes','/v2/payments/','/v2/checkout/orders/')) and 'evil.test' not in p for p in calls)


def test_observed_dispute_during_unstable_scan_cannot_disappear_on_later_empty_scan(account,provider,monkeypatch):
    local,_,docs,_,hook=fixture(account,provider,monkeypatch);reads=[]
    def unstable(cfg,path):
        reads.append(path)
        if path=='/v1/customer/disputes/PP-D-123' and reads.count(path)>1:return {**docs['PP-D-123'],'update_time':'2026-10-24T09:00:00Z'}
    hook['run']=unstable
    with pytest.raises(ValueError):service.reconcile_paypal(local)
    docs.clear();hook['run']=None
    with pytest.raises(FenceBlocked,match='previously observed'):service.reconcile_paypal(local)
    assert resources.state(account)['credits_micro']==0 and report()['pending']==1


@pytest.mark.parametrize('after_paid',[False,True])
def test_partial_full_discovery_cannot_clear_an_existing_unknown_gap_or_enable_capture(account,provider,monkeypatch,after_paid):
    local,_,_,_,hook=fixture(account,provider,monkeypatch,paid=after_paid)
    def unavailable(cfg,path):
        if path.startswith('/v1/customer/disputes?'):raise ValueError('No Disputes read scope')
    hook['run']=unavailable
    with pytest.raises(ValueError):service.reconcile_paypal(local)
    assert report()['pending']==1
    if after_paid:
        assert paypal.capture(account,local)['status']=='paid'
        assert report()['pending']==1  # Idempotent paid readback cannot clear the gap.
    else:
        with pytest.raises(FenceBlocked,match='Complete PayPal history'):paypal.capture(account,local)
    assert resources.state(account)['credits_micro']==(5_000_000 if after_paid else 0)

    hook['run']=None;service.reconcile_paypal(local)
    assert resources.state(account)['credits_micro']==3_000_000 and report()['pending']==0


def test_combined_historical_refunds_and_dispute_never_publish_gross_or_double_debit(account,provider,monkeypatch):
    from test_r210_paypal_history_reconciliation import history_fixture
    local,_,_,_=history_fixture(account,provider,monkeypatch)
    original=paypal._api
    document={'dispute_id':'PP-D-NET','status':'UNDER_REVIEW','update_time':'2026-10-24T01:00:00Z','disputed_transactions':[{'seller_transaction_id':'CAPTURE222'}],'dispute_amount':{'value':'1.00','currency_code':'EUR'}}
    def api(cfg,method,path,*args):
        assert method=='GET'
        if path.startswith('/v1/customer/disputes?'):
            items=[{k:document[k] for k in ('dispute_id','status','update_time','dispute_amount')}] if 'CAPTURE222' in path else []
            return copy.deepcopy({'items':items,'links':[]})
        if path=='/v1/customer/disputes/PP-D-NET':return copy.deepcopy(document)
        return original(cfg,method,path,*args)
    monkeypatch.setattr(paypal,'_api',api);service.reconcile_paypal(local)
    assert resources.state(account)['credits_micro']==0 and report()['positions'][0]['refunded_minor']==400 and report()['positions'][0]['held_minor']==100
    document.update(status='RESOLVED',update_time='2026-10-24T02:00:00Z',dispute_outcome={'outcome_code':'RESOLVED_SELLER_FAVOUR'})
    service.reconcile_paypal(local);service.reconcile_paypal(local)
    assert resources.state(account)['credits_micro']==1_000_000 and report()['verified']


def test_discovered_repayment_dispute_reopens_exact_debt_and_release_restores_allocation(account,provider,monkeypatch):
    from test_r210_paypal_reconciliation_e2e import HEADERS
    from test_r210_subscription_repayment_e2e import checkout,balance
    _,_,event,_=setup_order(account,provider,monkeypatch,subscription=True)
    paypal.webhook(json.dumps(event).encode(),HEADERS)
    local=checkout(account)['order_id']
    with auth.db() as c:pid=c.execute('SELECT provider_order FROM paypal_orders WHERE id=?',(local,)).fetchone()[0]
    original=paypal._api;canonical=original({},'POST','/v2/checkout/orders/'+pid+'/capture');cid=canonical['purchase_units'][0]['payments']['captures'][0]['id']
    document={'dispute_id':'PP-D-REPAY-HISTORY','status':'UNDER_REVIEW','update_time':'2026-10-24T01:00:00Z','disputed_transactions':[{'seller_transaction_id':cid}],'dispute_amount':{'value':'3.00','currency_code':'EUR'}}
    def api(cfg,method,path,*args):
        assert method=='GET'
        if path.startswith('/v1/customer/disputes?'):return {'items':[{k:copy.deepcopy(document[k]) for k in ('dispute_id','status','update_time','dispute_amount')}],'links':[]}
        if path=='/v1/customer/disputes/PP-D-REPAY-HISTORY':return copy.deepcopy(document)
        return original(cfg,method,path,*args)
    monkeypatch.setattr(paypal,'_api',api);service.reconcile_paypal(local)
    assert balance(account)['due_micro']==3_000_000 and resources.state(account)['credits_micro']==0 and report()['verified']
    document.update(status='RESOLVED',update_time='2026-10-24T02:00:00Z',dispute_outcome={'outcome_code':'RESOLVED_SELLER_FAVOUR'})
    service.reconcile_paypal(local);service.reconcile_paypal(local)
    assert balance(account)['due_micro']==0 and balance(account)['covered_micro']==3_000_000 and resources.state(account)['credits_micro']==0 and report()['pending']==0


def test_changed_dispute_amount_preserves_old_hold_and_durable_private_review(account,provider,monkeypatch):
    local,_,docs,_,_=fixture(account,provider,monkeypatch)
    service.reconcile_paypal(local)
    docs['PP-D-123'].update(update_time='2026-10-24T03:00:00Z');docs['PP-D-123']['dispute_amount']['value']='1.00'
    with pytest.raises(ValueError,match='identity changed'):service.reconcile_paypal(local)
    assert resources.state(account)['credits_micro']==3_000_000 and report()['pending']==1
    assert owner_payments.history(account)['items'][0]['financial_review_pending']
