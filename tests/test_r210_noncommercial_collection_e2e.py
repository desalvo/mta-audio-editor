"""Actual measured NC period -> optional transfer -> reviewed receipt/reversal."""
import hashlib
import sqlite3
from concurrent.futures import ThreadPoolExecutor

import pytest
from app import auth,ai_billing,storage
from app import noncommercial_contributions as nc
from app.noncommercial_statements import create_statement,user_statements
from app.regime_operation_fence import FenceBlocked


@pytest.fixture
def nc_env(tmp_path,monkeypatch):
    monkeypatch.setenv('MTA_DATA_DIR',str(tmp_path));monkeypatch.setattr(auth,'DATA_ROOT',tmp_path)
    monkeypatch.setenv('MTA_ADMIN_PASSWORD','a-secure-test-password')
    monkeypatch.setattr(storage,'ROOT',tmp_path/'projects');storage.ROOT.mkdir()
    monkeypatch.setattr(auth,'send_mail',lambda *a,**kw:None)
    auth.init_auth_db();admin=auth.find_user('admin')['id'];users=[]
    from app.resource_accounts import config
    config()
    with auth.db() as c:
        for name in ('nc-alice','nc-bob'):
            c.execute('INSERT INTO users(username,email,password_hash,role,active,email_confirmed,created_at,updated_at) VALUES(?,?,?,\'user\',1,1,1,1)',(name,name+'@example.test','unused'))
            users.append(c.execute('SELECT id FROM users WHERE username=?',(name,)).fetchone()[0])
    for uid,cpu in zip(users,(1,2),strict=True):
        job=ai_billing.create_job(uid,'whisper',started_at=200)
        ai_billing.finish_job(job,'done',{'cpu_seconds':cpu},source='worker',finished_at=203)
    with auth.db() as c:statement=create_statement(c,start=100,end=300,documented_cost_cents=300)
    assert statement['contribution_cents']=={str(users[0]):100,str(users[1]):200}
    return admin,*users,statement


def enable(env,**kw):
    return nc.configure(env[0],{'enabled':True,'instructions':'Bank transfer to TEST ACCOUNT. Quote the displayed MTA reference.','ledger_id':'test-bank-001','expected_revision':0,**kw})


def pledge(env,uid=None,*,amount=100,key='optional-pledge-123'):
    return nc.create(uid or env[1],{'start':100,'end':300,'statement_sha256':env[3]['sha256'],'amount_cents':amount,'request_id':key,'expected_settings_revision':1})


def receipt(env,item,*,amount=100,key='bank-receipt-123',reference='BANK-RECEIPT-001',kind='confirmed',original=None):
    return nc.event(env[0],item['id'],{'kind':kind,'request_id':key,'amount_cents':amount,'external_reference':reference,
        'evidence_sha256':hashlib.sha256(reference.encode()).hexdigest(),'verified_external_receipt':True,'original_event_id':original},admin=True)


def overview(uid=None):
    with auth.db() as c:return nc.overview(c,uid)


def test_optional_receipt_reversal_and_repayment_do_not_touch_usage_or_credits(nc_env):
    admin,alice,_,statement=nc_env;enable(nc_env)
    with auth.db() as c:
        original_usage=[tuple(r) for r in c.execute('SELECT id,usage_json FROM ai_compute_jobs')]
        original_credits=[tuple(r) for r in c.execute('SELECT * FROM resource_credits')]
    item=pledge(nc_env);assert item['state']=='awaiting_transfer'
    reported=nc.event(alice,item['id'],{'kind':'reported','request_id':'owner-report-123'})
    assert reported['received_cents']==0 and reported['state']=='pending_review'
    partial=receipt(nc_env,item,amount=40);assert partial['remaining_cents']==60
    paid=receipt(nc_env,item,amount=60,key='bank-receipt-456',reference='BANK-RECEIPT-002')
    assert paid['state']=='received' and paid['received_cents']==100
    assert receipt(nc_env,item,amount=60,key='bank-receipt-456',reference='BANK-RECEIPT-002')==paid
    original=next(e['id'] for e in paid['events'] if e['kind']=='confirmed')
    reopened=receipt(nc_env,item,amount=20,key='bank-reversal-123',reference='BANK-REFUND-001',kind='reversed',original=original)
    assert reopened['remaining_cents']==20 and reopened['state']=='partially_received'
    assert receipt(nc_env,item,amount=20,key='bank-receipt-789',reference='BANK-RECEIPT-003')['state']=='received'
    with auth.db() as c:
        assert user_statements(c,str(alice))[0]['sha256']==statement['sha256']
        assert [tuple(r) for r in c.execute('SELECT id,usage_json FROM ai_compute_jobs')]==original_usage
        assert [tuple(r) for r in c.execute('SELECT * FROM resource_credits')]==original_credits
        assert nc.audit(c)=={'verified':True,'pending':0,'received_cents':100,'refund_due_cents':0,'transition_enabled':False}


def test_excess_transfer_is_recorded_as_operator_refund_then_reconciled(nc_env):
    enable(nc_env);item=pledge(nc_env)
    extra=receipt(nc_env,item,amount=150)
    assert (extra['net_received_cents'],extra['received_cents'],extra['excess_cents'],extra['state'])==(150,100,50,'refund_due')
    original=extra['events'][0]['id']
    resolved=receipt(nc_env,item,amount=50,key='refund-excess-123',reference='BANK-EXCESS-REFUND',kind='reversed',original=original)
    assert resolved['state']=='received' and resolved['excess_cents']==0
    with auth.db() as c:
        from app.regime_reconciliation import combined_readiness
        report=combined_readiness(c,current='NON_COMMERCIAL',target='COMMERCIAL')
        assert 'nc_contribution_refunds_outstanding' not in report['unresolved']
        assert not report['ready_for_automatic_transition']


def test_unpaid_intent_can_cancel_but_reported_transfer_cannot(nc_env):
    enable(nc_env);item=pledge(nc_env)
    cancelled=nc.event(nc_env[1],item['id'],{'kind':'cancelled','request_id':'owner-cancel-123'})
    assert cancelled['state']=='cancelled' and cancelled['remaining_cents']==0
    late=receipt(nc_env,item)
    assert late['state']=='refund_due' and late['excess_cents']==100 and late['received_cents']==0
    second=pledge(nc_env,key='replacement-pledge-123')
    nc.event(nc_env[1],second['id'],{'kind':'reported','request_id':'owner-report-123'})
    with pytest.raises(FenceBlocked):nc.event(nc_env[1],second['id'],{'kind':'cancelled','request_id':'cancel-reported-123'})


@pytest.mark.parametrize('case',['disabled','wrong_owner','wrong_statement','over_share','boolean','stale_settings','drain','epoch','mirror','commercial'])
def test_invalid_pledge_is_rejected_without_financial_authority(nc_env,case):
    enable(nc_env);admin,uid,other,statement=nc_env
    body={'start':100,'end':300,'statement_sha256':statement['sha256'],'amount_cents':100,'request_id':'invalid-pledge-123','expected_settings_revision':1}
    if case=='disabled':nc.configure(admin,{'enabled':False,'instructions':'Old transfer instructions','ledger_id':'test-bank-001','expected_revision':1})
    if case=='wrong_owner':uid=auth.find_user('admin')['id']
    if case=='wrong_statement':body['statement_sha256']='0'*64
    if case=='over_share':body['amount_cents']=101
    if case=='boolean':body['amount_cents']=True
    if case=='stale_settings':body['expected_settings_revision']=0
    if case in ('drain','epoch','commercial'):
        with auth.db() as c:c.execute("UPDATE regime_fence_state SET transitioning=1" if case=='drain' else "UPDATE regime_fence_state SET revision=1" if case=='epoch' else "UPDATE regime_fence_state SET regime='COMMERCIAL'")
    if case=='mirror':(auth.data_root()/'service-regime.json').write_text('{"regime":"NON_COMMERCIAL","revision":1}')
    with pytest.raises((FenceBlocked,ValueError)):nc.create(uid,body)
    with auth.db() as c:assert c.execute('SELECT count(*) FROM nc_contribution_intents').fetchone()[0]==0


def test_concurrent_pledges_and_receipts_are_idempotent_and_conserve_share(nc_env):
    enable(nc_env)
    with ThreadPoolExecutor(max_workers=4) as pool:items=list(pool.map(lambda _:pledge(nc_env),range(4)))
    assert len({i['id'] for i in items})==1
    with ThreadPoolExecutor(max_workers=4) as pool:results=list(pool.map(lambda _:receipt(nc_env,items[0]),range(4)))
    assert all(i['received_cents']==100 and len(i['events'])==1 for i in results)
    with pytest.raises(FenceBlocked):pledge(nc_env,key='double-recovery-123')


def test_same_external_receipt_cannot_fund_another_account(nc_env):
    enable(nc_env);first=pledge(nc_env);receipt(nc_env,first)
    other=pledge(nc_env,nc_env[2])
    with pytest.raises(sqlite3.IntegrityError):receipt(nc_env,other,key='second-owner-123')
    assert overview(nc_env[2])['contributions'][0]['received_cents']==0


@pytest.mark.parametrize('change',['amount','reference','proof','verified','role','self','reversal'])
def test_external_receipt_requires_authorized_independent_evidence(nc_env,change):
    enable(nc_env);item=pledge(nc_env)
    actor=nc_env[0];body={'kind':'confirmed','request_id':'invalid-receipt-123','amount_cents':100,'external_reference':'BANK-RECEIPT-001','evidence_sha256':'a'*64,'verified_external_receipt':True,'original_event_id':None}
    if change=='amount':body['amount_cents']=True
    if change=='reference':body['external_reference']='\nunsafe'
    if change=='proof':body['evidence_sha256']='not-a-digest'
    if change=='verified':body['verified_external_receipt']=False
    if change=='role':actor=nc_env[2]
    if change=='self':
        with auth.db() as c:c.execute("UPDATE users SET role='admin' WHERE id=?",(nc_env[1],))
        actor=nc_env[1]
    if change=='reversal':body.update(kind='reversed',original_event_id='missing')
    with pytest.raises((FenceBlocked,ValueError)):nc.event(actor,item['id'],body,admin=True)
    assert overview(nc_env[1])['contributions'][0]['received_cents']==0


def test_owner_cannot_select_another_contribution_or_change_server_target(nc_env):
    enable(nc_env);item=pledge(nc_env)
    with pytest.raises(ValueError):nc.event(nc_env[2],item['id'],{'kind':'reported','request_id':'other-report-123'})
    with pytest.raises(ValueError):nc.event(nc_env[1],item['id'],{'kind':'confirmed','request_id':'fake-confirm-123'})
    with pytest.raises(FenceBlocked):pledge(nc_env,amount=50)
    assert item['id'] not in str(overview(nc_env[2]))


def test_partial_optional_contributions_do_not_require_full_share(nc_env):
    enable(nc_env);first=pledge(nc_env,amount=30);receipt(nc_env,first,amount=30)
    assert overview(nc_env[1])['statements'][0]['available_cents']==70
    second=pledge(nc_env,amount=70,key='remaining-pledge-123')
    receipt(nc_env,second,amount=70,key='remaining-receipt-123',reference='BANK-SECOND-RECEIPT')
    assert overview(nc_env[1])['statements'][0]['received_cents']==100


def test_changed_configuration_preserves_existing_transfer_instructions(nc_env):
    enable(nc_env);item=pledge(nc_env)
    nc.configure(nc_env[0],{'enabled':False,'instructions':'Different receiving bank account','ledger_id':'new-bank-002','expected_revision':1})
    receipt(nc_env,item)
    assert overview(nc_env[1])['contributions'][0]['instructions']==item['instructions']
    assert not overview(nc_env[1])['enabled']


def test_immutable_financial_rows_and_tamper_detection(nc_env):
    enable(nc_env);item=pledge(nc_env);receipt(nc_env,item)
    with auth.db() as c:
        for query in ('UPDATE nc_contribution_intents SET amount_cents=1','DELETE FROM nc_contribution_intents','DELETE FROM nc_contribution_events','UPDATE nc_contribution_events SET amount_cents=1'):
            with pytest.raises(sqlite3.IntegrityError):c.execute(query)
        c.execute('DROP TRIGGER nc_contribution_events_immutable_update')
        c.execute('UPDATE nc_contribution_events SET amount_cents=1')
        assert not nc.audit(c)['verified']


@pytest.mark.parametrize('lang',['it','en'])
def test_owner_export_is_private_nonfiscal_and_contains_actual_net(nc_env,lang):
    enable(nc_env);item=pledge(nc_env);receipt(nc_env,item,amount=110)
    other=pledge(nc_env,nc_env[2],key='bob-pledge-123')
    with auth.db() as c:result=nc.export_csv(c,nc_env[1],lang)
    assert not result['fiscal_receipt'] and item['id'] in result['content'] and other['id'] not in result['content']
    assert ',110,100,10,refund_due' in result['content']


def test_failed_receipt_transaction_rolls_back_and_can_retry(nc_env,monkeypatch):
    enable(nc_env);item=pledge(nc_env);original=nc._put
    def fail(c,table,data):
        original(c,table,data)
        if table=='event':raise RuntimeError('crash before acknowledgment')
    monkeypatch.setattr(nc,'_put',fail)
    with pytest.raises(RuntimeError):receipt(nc_env,item)
    assert overview(nc_env[1])['contributions'][0]['received_cents']==0
    monkeypatch.setattr(nc,'_put',original)
    assert receipt(nc_env,item)['received_cents']==100


def test_same_normalized_bank_reference_remains_unique(nc_env):
    enable(nc_env);item=pledge(nc_env);receipt(nc_env,item)
    other=pledge(nc_env,nc_env[2])
    with pytest.raises(sqlite3.IntegrityError):receipt(nc_env,other,key='normalized-reference-123',reference=' bank- receipt-001 ')


def test_reported_transfer_and_excess_are_readiness_blockers(nc_env):
    enable(nc_env);item=pledge(nc_env)
    from app.regime_reconciliation import combined_readiness
    with auth.db() as c:
        report=combined_readiness(c,current='NON_COMMERCIAL',target='COMMERCIAL')
        assert 'nc_contributions_pending' in report['unresolved']
    receipt(nc_env,item,amount=150)
    with auth.db() as c:
        report=combined_readiness(c,current='NON_COMMERCIAL',target='COMMERCIAL')
        assert 'nc_contribution_refunds_outstanding' in report['unresolved']
        assert 'nc_contributions_pending' not in report['unresolved']


@pytest.mark.parametrize('mode',['erase','privacy_purge'])
def test_financial_erasure_is_retired_owner_scoped(nc_env,monkeypatch,tmp_path,mode):
    from app import account_lifecycle as life,account_erasure,ai_arranger_runtime
    monkeypatch.setattr(ai_arranger_runtime,'_ROOT',tmp_path/'private-queue')
    enable(nc_env);item=pledge(nc_env);receipt(nc_env,item)
    other=pledge(nc_env,nc_env[2]);receipt(nc_env,other,key='bob-receipt-123',reference='BOB-BANK-RECEIPT')
    admin,uid,other_uid,_=nc_env;life.register(uid);life.retire(uid,admin)
    with pytest.raises(ValueError,match='contabili'):life.purge(uid,admin,False)
    if mode=='privacy_purge':life.purge(uid,admin,True)
    assert account_erasure.erase(uid,admin,confirmed=True)['done']
    assert not auth.get_user(uid) and auth.get_user(other_uid)
    with auth.db() as c:
        assert {r[0] for r in c.execute('SELECT user_id FROM nc_contribution_intents')}=={other_uid}
        assert {r[0] for r in c.execute('SELECT user_id FROM nc_contribution_events')}=={other_uid}
        assert nc.audit(c)['verified']
        with pytest.raises(sqlite3.IntegrityError):c.execute('DELETE FROM nc_contribution_events')


def test_actual_api_owner_admin_and_csrf_boundaries(nc_env,monkeypatch):
    from fastapi.testclient import TestClient
    from app import main
    from test_r210_legal_documents import cookie
    monkeypatch.setattr(main,'NATIVE_SINGLE_USER',False);monkeypatch.setattr(main,'check_basic_auth',lambda request:False)
    monkeypatch.delenv('MTA_ALLOW_INSECURE_NO_AUTH',raising=False)
    admin,uid,other,statement=nc_env
    client=TestClient(main.app);client.cookies.update(cookie(uid))
    assert client.get('/api/account/noncommercial-contributions').status_code==200
    assert client.get('/api/admin/noncommercial-contributions').status_code==403
    client.cookies.clear();client.cookies.update(cookie(admin))
    cfg={'enabled':True,'instructions':'Bank transfer to TEST ACCOUNT','ledger_id':'api-bank-001','expected_revision':0}
    assert client.put('/api/admin/noncommercial-contributions/settings',json=cfg).status_code==403
    headers={'X-MTA-Request':'1'}
    assert client.put('/api/admin/noncommercial-contributions/settings',json=cfg,headers=headers).status_code==200
    client.cookies.clear();client.cookies.update(cookie(uid))
    body={'start':100,'end':300,'statement_sha256':statement['sha256'],'amount_cents':100,'request_id':'api-pledge-123','expected_settings_revision':1}
    assert client.post('/api/account/noncommercial-contributions',json=body).status_code==403
    response=client.post('/api/account/noncommercial-contributions',json=body,headers=headers)
    assert response.status_code==200,response.text
    item=response.json()
    response=client.post('/api/account/noncommercial-contributions/'+item['id']+'/events',json={'kind':'reported','request_id':'api-report-123'},headers=headers)
    assert response.status_code==200 and response.json()['received_cents']==0
    client.cookies.clear();client.cookies.update(cookie(other))
    assert item['id'] not in client.get('/api/account/noncommercial-contributions').text
    assert client.post('/api/account/noncommercial-contributions/'+item['id']+'/events',json={'kind':'reported','request_id':'api-forged-123'},headers=headers).status_code==422
    assert client.get('/api/account/noncommercial-contributions/export-csv?lang=fr').status_code==422
    client.cookies.clear();client.cookies.update(cookie(admin))
    proof={'kind':'confirmed','request_id':'api-receipt-123','amount_cents':100,'external_reference':'API-BANK-RECEIPT','evidence_sha256':'a'*64,'verified_external_receipt':True,'original_event_id':None}
    response=client.post('/api/admin/noncommercial-contributions/'+item['id']+'/events',json=proof,headers=headers)
    assert response.status_code==200 and response.json()['state']=='received'
    client.cookies.clear();client.cookies.update(cookie(uid))
    assert item['id'] in client.get('/api/account/noncommercial-contributions/export-csv?lang=it').json()['content']
    client.cookies.clear()
    assert client.get('/api/account/noncommercial-contributions').status_code==401


def test_fully_returned_contribution_can_close_without_forced_repayment(nc_env):
    enable(nc_env);item=pledge(nc_env)
    nc.event(nc_env[1],item['id'],{'kind':'reported','request_id':'returned-owner-report'})
    paid=receipt(nc_env,item)
    returned=receipt(nc_env,item,kind='reversed',original=next(e['id'] for e in paid['events'] if e['kind']=='confirmed'),amount=100,key='returned-bank-123',reference='FULL-BANK-RETURN')
    assert returned['can_cancel'] and returned['received_cents']==0
    closed=nc.event(nc_env[1],item['id'],{'kind':'cancelled','request_id':'returned-close-123'})
    assert closed['state']=='cancelled' and closed['remaining_cents']==0
    assert overview(nc_env[1])['statements'][0]['available_cents']==100
    late=receipt(nc_env,item,amount=20,key='late-after-return-123',reference='LATE-AFTER-RETURN')
    assert late['received_cents']==0 and late['excess_cents']==20


def test_history_remains_readable_during_drain_but_cannot_mutate(nc_env):
    enable(nc_env);item=pledge(nc_env)
    with auth.db() as c:c.execute('UPDATE regime_fence_state SET transitioning=1')
    assert overview(nc_env[1])['contributions'][0]['id']==item['id']
    assert not overview(nc_env[1])['mutations_allowed']
    with pytest.raises(FenceBlocked):receipt(nc_env,item)
    with pytest.raises(FenceBlocked):nc.event(nc_env[1],item['id'],{'kind':'reported','request_id':'drained-report-123'})


def test_erasure_permission_is_owner_scoped_and_connection_local(nc_env):
    from app import account_lifecycle as life
    enable(nc_env);first=pledge(nc_env);second=pledge(nc_env,nc_env[2])
    life.register(nc_env[1]);life.retire(nc_env[1],nc_env[0])
    with auth.db() as c:
        c.execute('BEGIN IMMEDIATE');nc.authorize_account_erasure(c,nc_env[1],nc_env[0])
        with pytest.raises(sqlite3.IntegrityError):c.execute('DELETE FROM nc_contribution_intents WHERE id=?',(second['id'],))
        c.rollback()
    with auth.db() as c:
        with pytest.raises(sqlite3.IntegrityError):c.execute('DELETE FROM nc_contribution_intents WHERE id=?',(first['id'],))


def test_partial_collection_schema_never_recreates_lost_receipts(nc_env):
    enable(nc_env);item=pledge(nc_env);receipt(nc_env,item)
    with auth.db() as c:
        c.execute('PRAGMA foreign_keys=OFF')
        c.execute('DROP TABLE nc_contribution_events')
    with auth.db() as c:assert not nc.audit(c)['verified']
    with pytest.raises(FenceBlocked):pledge(nc_env,key='lost-evidence-retry')
    with auth.db() as c:assert 'nc_contribution_events' not in nc._tables(c)
