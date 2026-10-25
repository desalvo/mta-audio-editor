"""Merchant-wide readback: stable pages/private API; never money authority."""
import copy
import json
from urllib.parse import urlsplit,parse_qs
import pytest
from app import auth,paypal_payments as paypal,paypal_merchant_history as history
from app.regime_operation_fence import FenceBlocked
from test_r210_subscriptions import account as account  # noqa: F401
from test_r210_paypal import provider as provider  # noqa: F401

START,END='2026-09-01T00:00:00Z','2026-09-02T00:00:00Z'


def record(n=1,code='T0006'):
    return {'transaction_info':{'transaction_id':f'TXN{n:014d}','transaction_event_code':code,
      'transaction_status':'S','transaction_amount':{'currency_code':'EUR','value':'-1.23'},
      'paypal_reference_id':'UNBOUND123','paypal_reference_id_type':'TXN','transaction_subject':'SECRET CUSTOMER',
      'transaction_note':'SECRET NOTE','fee_amount':{'value':'99','currency_code':'EUR'}},
      'payer_info':{'email_address':'private@example.test'}}


@pytest.fixture
def reporting(account,provider,monkeypatch):
    admin=auth.find_user('admin')['id'];calls=[];data=[record()]
    def api(cfg,method,path,*args):
        assert method=='GET' and urlsplit(path).path=='/v1/reporting/transactions'
        q=parse_qs(urlsplit(path).query);calls.append(q)
        assert set(q)=={'start_date','end_date','fields','balance_affecting_records_only','page_size','page'}
        assert q['fields']==['transaction_info'] and q['balance_affecting_records_only']==['N']
        page=int(q['page'][0]);pages=(len(data)+99)//100
        return {'page':page,'total_pages':pages,'total_items':len(data),'transaction_details':copy.deepcopy(data[(page-1)*100:page*100])}
    monkeypatch.setattr(paypal,'_api',api)
    return admin,calls,data,api


def acquire(reporting):
    return history.acquire(reporting[0],START,END,confirm=True)


def test_stable_global_query_persists_private_fixed_dto_without_money_mutation(reporting):
    with auth.db() as c:before=[tuple(r) for r in c.execute('SELECT * FROM resource_credits')]
    receipt=acquire(reporting)
    assert receipt['records']==1 and not receipt['settlement_proven'] and not receipt['transition_authorized']
    assert len(reporting[1])==2 and 'transaction_id' not in reporting[1][0]
    dto=history.details(reporting[0],receipt['snapshot_id'])
    assert dto['items'][0]['amount']=='-1.23'
    assert 'SECRET' not in json.dumps(dto) and 'private@example.test' not in json.dumps(dto)
    assert acquire(reporting)['snapshot_id']==receipt['snapshot_id']
    assert history.snapshots(reporting[0])['total']==1
    with auth.db() as c:assert [tuple(r) for r in c.execute('SELECT * FROM resource_credits')]==before


def test_pagination_covers_same_id_with_distinct_reporting_entries(reporting):
    reporting[2][:]=[record(n) for n in range(1,102)]+[record(1,'T1107')]
    receipt=acquire(reporting)
    assert receipt['records']==102 and len(reporting[1])==4
    listing=history.snapshots(reporting[0])['items'][0]
    assert listing['truncated'] and len(listing['observations'])==50
    assert len(history.details(reporting[0],receipt['snapshot_id'],offset=100)['items'])==2


@pytest.mark.parametrize('change',['missing_total','string_page','wrong_page','too_many_pages','count_mismatch','duplicate','changed_pass','malformed_money','unknown_status','timeout','configuration','actor_revoked'])
def test_incomplete_or_changed_readback_never_commits(reporting,monkeypatch,change):
    original=reporting[3];counter=[0]
    def api(*args):
        counter[0]+=1
        if change=='timeout':raise ValueError('Provider timeout')
        response=original(*args)
        if change=='missing_total':response.pop('total_items')
        elif change=='string_page':response['page']='1'
        elif change=='wrong_page':response['page']=2
        elif change=='too_many_pages':response['total_pages']=21
        elif change=='count_mismatch':response['total_items']=2
        elif change=='duplicate':response['transaction_details']*=2;response['total_items']=2
        elif change=='changed_pass' and counter[0]==2:response['transaction_details'][0]['transaction_info']['transaction_amount']['value']='-9'
        elif change=='malformed_money':response['transaction_details'][0]['transaction_info']['transaction_amount']['value']='NaN'
        elif change=='unknown_status':response['transaction_details'][0]['transaction_info']['transaction_status']='DONE'
        elif change=='configuration':
            with auth.db() as c:c.execute("UPDATE paypal_config SET enabled=0")
        elif change=='actor_revoked':
            with auth.db() as c:c.execute('UPDATE users SET active=0 WHERE id=?',(reporting[0],))
        return response
    monkeypatch.setattr(paypal,'_api',api)
    with pytest.raises((ValueError,FenceBlocked,PermissionError)):acquire(reporting)
    with auth.db() as c:
        if c.execute("SELECT 1 FROM sqlite_master WHERE name='paypal_merchant_history'").fetchone():
            assert c.execute('SELECT count(*) FROM paypal_merchant_history').fetchone()[0]==0


@pytest.mark.parametrize('start,end,confirm',[(START,END,False),('2026-09-01',END,True),(END,START,True),(START,'2026-11-05T00:00:00Z',True)])
def test_bad_or_unconfirmed_range_never_contacts_provider(reporting,start,end,confirm):
    with pytest.raises(ValueError):history.acquire(reporting[0],start,end,confirm=confirm)
    assert not reporting[1]


def test_reader_and_acquisition_require_active_administrator(reporting,account):
    for action in [lambda:history.acquire(account,START,END,confirm=True),lambda:history.snapshots(account)]:
        with pytest.raises(PermissionError):action()
    assert not reporting[1]


def test_snapshot_corruption_stays_blocked(reporting):
    receipt=acquire(reporting)
    with auth.db() as c:
        c.execute('DROP TRIGGER paypal_merchant_history_immutable')
        c.execute("UPDATE paypal_merchant_history SET evidence_json='[]'")
    with pytest.raises(FenceBlocked):history.details(reporting[0],receipt['snapshot_id'])
    with pytest.raises(FenceBlocked):history.snapshots(reporting[0])


def test_private_actual_admin_api_session_csrf_confirmation_and_details(reporting,account,monkeypatch):
    from fastapi.testclient import TestClient
    from app import main
    from test_r210_legal_documents import cookie
    monkeypatch.setattr(main,'NATIVE_SINGLE_USER',False)
    monkeypatch.setattr(main,'check_basic_auth',lambda _:False)
    monkeypatch.delenv('MTA_ALLOW_INSECURE_NO_AUTH',raising=False)
    client=TestClient(main.app);path='/api/admin/paypal/merchant-history';body={'start_date':START,'end_date':END,'confirm':True}
    assert client.get(path).status_code==401
    client.cookies.update(cookie(account));assert client.get(path).status_code==403
    client.cookies.update(cookie(reporting[0]))
    assert client.post(path,json=body).status_code==403
    response=client.post(path,json=body,headers={'X-MTA-Request':'1'})
    assert response.status_code==200,response.text
    identity=response.json()['snapshot_id']
    assert client.get(path).json()['total']==1
    assert client.get(path+'/'+identity).json()['total']==1
    assert client.get(path+'?limit=0').status_code==422


def test_metadata_and_semantic_corruption_cannot_relabel_snapshot(reporting):
    receipt=acquire(reporting)
    with auth.db() as c:
        c.execute('DROP TRIGGER paypal_merchant_history_immutable')
        c.execute("UPDATE paypal_merchant_history SET end_date='2026-09-03T00:00:00Z'")
    with pytest.raises(FenceBlocked):history.snapshots(reporting[0])
    with pytest.raises(FenceBlocked):history.details(reporting[0],receipt['snapshot_id'])


def test_non_eur_pending_observations_remain_nonsettlement_data(reporting):
    item=reporting[2][0]['transaction_info'];item['transaction_status']='P'
    item['transaction_amount']={'currency_code':'JPY','value':'1000'}
    receipt=acquire(reporting)
    dto=history.details(reporting[0],receipt['snapshot_id'])
    assert dto['items'][0]['currency']=='JPY' and dto['items'][0]['status']=='P'
    assert not dto['settlement_proven']
