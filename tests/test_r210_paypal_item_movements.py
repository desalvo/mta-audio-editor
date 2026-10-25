"""Read-only item evidence -> exact risk ledger; movement details never settle."""
import json
from concurrent.futures import ThreadPoolExecutor

import pytest
from app import auth,payment_reconcile_service as service,resource_accounts as resources,owner_payments
from app.regime_operation_fence import FenceBlocked
from test_r210_paypal_dispute_history import fixture,report
from test_r210_subscriptions import account as account  # noqa: F401
from test_r210_paypal import provider as provider  # noqa: F401


def partial(account,provider,monkeypatch,*,paid=False,subscription=False):
    local,order,docs,calls,hook=fixture(account,provider,monkeypatch,paid=paid,multi=True,subscription=subscription)
    d=docs['PP-D-123'];d['dispute_amount']['value']='3.00'
    d['disputed_transactions'][0]['items']=[{'item_id':'ITEM-A','item_quantity':'99','item_name':'<img src=x onerror=alert(1)> private buyer','dispute_amount':{'value':'1.25','currency_code':'EUR'}},{'item_id':'ITEM-B','dispute_amount':{'value':'0.75','currency_code':'EUR'}}]
    d['disputed_transactions'][1]['items']=[{'item_id':'ITEM-C','dispute_amount':{'value':'1.00','currency_code':'EUR'}}]
    return local,order,docs,calls,hook


@pytest.mark.parametrize('paid',[False,True])
@pytest.mark.parametrize('outcome',['RESOLVED_SELLER_FAVOUR','RESOLVED_BUYER_FAVOUR'])
def test_exact_partial_multicapture_first_funding_release_loss_and_replay(account,provider,monkeypatch,paid,outcome):
    local,_,docs,_,_=partial(account,provider,monkeypatch,paid=paid)
    result=service.reconcile_paypal(local);assert result['disputes']==1 and result['ledger_reconciled']
    assert resources.state(account)['credits_micro']==2_000_000 and report()['positions'][0]['held_minor']==300
    with ThreadPoolExecutor(max_workers=3) as pool:list(pool.map(lambda _:service.reconcile_paypal(local),range(3)))
    assert resources.state(account)['credits_micro']==2_000_000 and report()['pending']==0
    with auth.db() as c:
        assert sorted(tuple(r) for r in c.execute('SELECT capture_id,amount_cents FROM paypal_financial_holds'))==[('CAPTURE111',200),('CAPTURE222',100)]
        raw=[r[0] for r in c.execute("SELECT normalized_json FROM payment_reconciliation_events WHERE event_id LIKE 'reconcile:risk:%'")]
        assert all(json.loads(x)['allocation_proof']['item_count']==3 for x in raw)
        assert all('private buyer' not in x and 'ITEM-A' not in x for x in raw)
    docs['PP-D-123'].update(status='RESOLVED',update_time='2026-10-24T03:00:00Z',dispute_outcome={'outcome_code':outcome})
    service.reconcile_paypal(local);service.reconcile_paypal(local)
    assert resources.state(account)['credits_micro']==(5_000_000 if outcome=='RESOLVED_SELLER_FAVOUR' else 2_000_000)
    assert report()['verified'] and report()['pending']==0


def test_partial_multicapture_original_subscription_risk_does_not_mint_credit(account,provider,monkeypatch):
    local,_,_,_,_=partial(account,provider,monkeypatch,subscription=True)
    service.reconcile_paypal(local)
    assert resources.state(account)['credits_micro']==0 and report()['subscription_risk_micro']==3_000_000


@pytest.mark.parametrize('defect',['missing_items','empty_items','wrong_type','missing_id','duplicate_id','duplicate_cross_capture','control_id','long_id','missing_money','negative','zero','currency','capture_overflow','global_mismatch','numeric_quantity','zero_quantity','excess_items','malformed_item'])
def test_item_ambiguities_preserve_pending_gap_and_no_gross_credit(account,provider,monkeypatch,defect):
    local,_,docs,_,_=partial(account,provider,monkeypatch)
    d=docs['PP-D-123'];tx=d['disputed_transactions'][0];item=tx['items'][0]
    if defect=='missing_items':tx.pop('items')
    if defect=='empty_items':tx['items']=[]
    if defect=='wrong_type':tx['items']={}
    if defect=='missing_id':item.pop('item_id')
    if defect=='duplicate_id':tx['items'][1]['item_id']='ITEM-A'
    if defect=='duplicate_cross_capture':d['disputed_transactions'][1]['items'][0]['item_id']='ITEM-A'
    if defect=='control_id':item['item_id']='line\nnext'
    if defect=='long_id':item['item_id']='x'*256
    if defect=='missing_money':item.pop('dispute_amount')
    if defect=='negative':item['dispute_amount']['value']='-1.00'
    if defect=='zero':item['dispute_amount']['value']='0.00'
    if defect=='currency':item['dispute_amount']['currency_code']='USD'
    if defect=='capture_overflow':item['dispute_amount']['value']='4.00';d['dispute_amount']['value']='5.75'
    if defect=='global_mismatch':d['dispute_amount']['value']='3.01'
    if defect=='numeric_quantity':item['item_quantity']=2
    if defect=='zero_quantity':item['item_quantity']='0'
    if defect=='excess_items':tx['items']=[{**item,'item_id':str(i)} for i in range(101)]
    if defect=='malformed_item':tx['items']=[None]
    with pytest.raises((ValueError,FenceBlocked)):service.reconcile_paypal(local)
    assert resources.state(account)['credits_micro']==0 and report()['pending']==1
    assert owner_payments.history(account)['items'][0]['financial_review_pending']


def movements(source='fund_movements',*,party='SELLER',reason='DISPUTE_SETTLEMENT',value='2.00',direction='DEBIT'):
    return {source:[{'party' if source=='fund_movements' else 'affected_party':party,'reason':reason,'type':direction,'amount':{'value':value,'currency_code':'EUR'},'initiated_time':'2026-10-24T02:00:00Z','private_notes':'NEVER EXPOSE THIS CUSTOMER'}]}


@pytest.mark.parametrize('source',['fund_movements','money_movements','both','none'])
@pytest.mark.parametrize('party',['SELLER','BUYER','PAYMENT_PROCESSOR'])
def test_canonical_movement_review_never_releases_payout_or_charges_fee_to_customer(account,provider,monkeypatch,source,party):
    local,_,docs,_,_=fixture(account,provider,monkeypatch)
    d=docs['PP-D-123'];d.update(status='RESOLVED',dispute_outcome={'outcome_code':'RESOLVED_WITH_PAYOUT'})
    if source!='none':d.update(movements('fund_movements' if source=='both' else source,party=party,reason='DISPUTE_FEE',value='7.00',direction='CREDIT'))
    if source=='both':d.update(movements('money_movements',party=party,reason='DISPUTE_FEE',value='7.00',direction='CREDIT'))
    result=service.reconcile_paypal(local);assert result['financial_review_pending'] and resources.state(account)['credits_micro']==3_000_000
    p=report()['positions'][0];view=p['movement_reviews'];assert view['settlement_proven'] is False and len(view['items'])==1
    item=view['items'][0];assert item['pending'] and item['settlement_proven'] is False
    assert len(item['observations'])==(2 if source=='both' else 0 if source=='none' else 1)
    if item['observations']:assert item['observations'][0]['amount_minor']==700 and item['observations'][0]['party']==party
    raw=json.dumps(p);assert 'NEVER EXPOSE' not in raw
    private=json.dumps(owner_payments.history(account));assert all(x not in private for x in ['movement_reviews','PP-D-123','PAYMENT_PROCESSOR','NEVER EXPOSE'])
    service.reconcile_paypal(local);assert resources.state(account)['credits_micro']==3_000_000 and len(report()['positions'][0]['movement_reviews']['items'])==1
    # Observations remain immutable history even after a separately supported
    # final resolution. Neither a movement sum nor CREDIT itself grants this.
    for key in ('money_movements','fund_movements'):d.pop(key,None)
    d.update(update_time='2026-10-24T04:00:00Z',dispute_outcome={'outcome_code':'RESOLVED_SELLER_FAVOUR'})
    service.reconcile_paypal(local);assert resources.state(account)['credits_micro']==5_000_000 and report()['pending']==0
    assert not report()['positions'][0]['movement_reviews']['items'][0]['pending']


@pytest.mark.parametrize('defect',['missing_party','missing_direction','unknown_reason','missing_amount','bad_time','asset','missing_time'])
def test_optional_or_unproven_movement_fields_remain_observations_not_payment_proof(account,provider,monkeypatch,defect):
    local,_,docs,_,_=fixture(account,provider,monkeypatch)
    d=docs['PP-D-123'];d.update(status='RESOLVED',dispute_outcome={'outcome_code':'RESOLVED_WITH_PAYOUT'},**movements())
    row=d['fund_movements'][0]
    if defect=='missing_party':row.pop('party')
    if defect=='missing_direction':row.pop('type')
    if defect=='unknown_reason':row['reason']='<script>secret</script>'
    if defect=='missing_amount':row.pop('amount')
    if defect=='bad_time':row['initiated_time']='2026-99-99T01:00:00Z'
    if defect=='missing_time':row.pop('initiated_time')
    if defect=='asset':row['asset']={'asset_symbol':'BTC','quantity':'1'}
    service.reconcile_paypal(local);assert resources.state(account)['credits_micro']==3_000_000 and report()['pending']==1
    assert '<script>' not in json.dumps(report())
    with auth.db() as c:
        data=json.loads(c.execute("SELECT normalized_json FROM payment_reconciliation_events WHERE event_id LIKE 'reconcile:risk:%'").fetchone()[0]);assert data['movement_review']['warnings']


@pytest.mark.parametrize('defect',['non_list','non_object','over_bound','wrong_currency','invalid_money'])
def test_malformed_movement_collection_requires_durable_history_review(account,provider,monkeypatch,defect):
    local,_,docs,_,_=fixture(account,provider,monkeypatch)
    d=docs['PP-D-123'];d.update(status='RESOLVED',dispute_outcome={'outcome_code':'RESOLVED_WITH_PAYOUT'},**movements())
    if defect=='non_list':d['fund_movements']={"secret":"value"}
    if defect=='non_object':d['fund_movements']=[None]
    if defect=='over_bound':d['fund_movements']*=51
    if defect=='wrong_currency':d['fund_movements'][0]['amount']['currency_code']='USD'
    if defect=='invalid_money':d['fund_movements'][0]['amount']['value']='-1.00'
    with pytest.raises(ValueError):service.reconcile_paypal(local)
    assert resources.state(account)['credits_micro']==0 and report()['pending']==1


def test_private_movement_report_bounded_and_deduplicated_across_two_captures(account,provider,monkeypatch):
    local,_,docs,_,_=partial(account,provider,monkeypatch)
    d=docs['PP-D-123'];d.update(status='RESOLVED',dispute_outcome={'outcome_code':'RESOLVED_WITH_PAYOUT'},**movements())
    service.reconcile_paypal(local);assert report()['pending']==2
    reviews=report()['positions'][0]['movement_reviews'];assert len(reviews['items'])==1 and not reviews['truncated']
    assert resources.state(account)['credits_micro']==2_000_000


@pytest.mark.parametrize('value',[{},None,False,0,''])
def test_false_valued_malformed_movement_field_cannot_authorize_a_seller_release(account,provider,monkeypatch,value):
    local,_,docs,_,_=fixture(account,provider,monkeypatch)
    docs['PP-D-123'].update(status='RESOLVED',dispute_outcome={'outcome_code':'RESOLVED_SELLER_FAVOUR'},fund_movements=value)
    with pytest.raises(ValueError):service.reconcile_paypal(local)
    assert resources.state(account)['credits_micro']==0 and report()['pending']==1


def test_admin_only_safe_movement_dto_and_corrupt_observation_fail_closed(account,provider,monkeypatch):
    from test_r210_account_acceptance import client
    local,_,docs,_,_=fixture(account,provider,monkeypatch)
    docs['PP-D-123'].update(status='RESOLVED',dispute_outcome={'outcome_code':'RESOLVED_WITH_PAYOUT'},**movements())
    service.reconcile_paypal(local)
    owner=client(account,monkeypatch);admin=client(auth.find_user('admin')['id'],monkeypatch)
    assert owner.get('/api/admin/service-regime/payment-ledger').status_code==403
    response=admin.get('/api/admin/service-regime/payment-ledger');assert response.status_code==200
    assert 'NEVER EXPOSE' not in response.text and response.json()['positions'][0]['movement_reviews']['settlement_proven'] is False
    with auth.db() as c:
        row=c.execute("SELECT event_id,normalized_json FROM payment_reconciliation_events WHERE event_id LIKE 'reconcile:risk:%'").fetchone()
        data=json.loads(row[1]);data['movement_review']['observations'][0]['direction']='<script>private</script>'
        c.execute('DROP TRIGGER payment_events_immutable_payload')  # Explicit privileged corruption injection.
        c.execute('UPDATE payment_reconciliation_events SET normalized_json=? WHERE event_id=?',(json.dumps(data),row[0]))
    failed=admin.get('/api/admin/service-regime/payment-ledger');assert failed.status_code==409 and 'private' not in failed.text
