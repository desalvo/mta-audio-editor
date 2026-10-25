"""Actual owner-scoped account summary, verified NC journals and commercial state."""
import json
from fastapi.testclient import TestClient
from app import account_limits,auth,main,resource_accounts as resources
from test_r210_noncommercial_collection_e2e import nc_env as nc_env,enable,pledge,receipt  # noqa: F401
from test_r210_subscriptions import account as account,plan  # noqa: F401
from test_r210_legal_documents import cookie

STORAGE=dict(used_bytes=0,audio_bytes=0,other_bytes=0,project_count=0,track_count=0)


def test_nc_cost_shares_are_not_debt_and_unverified_reports_are_not_receipts(nc_env):
    from app.noncommercial_contributions import event
    enable(nc_env);item=pledge(nc_env);event(nc_env[1],item['id'],{'kind':'reported','request_id':'personal-report-00001'})
    data=account_limits.summary(nc_env[1],STORAGE,at=500)
    assert data['service_regime']=='NON_COMMERCIAL'
    f=data['financial_context'];nc=f['noncommercial']
    assert f['aggregate_outstanding_debt_micro'] is None and f['operator_assumed_unknown_jobs']==0
    assert nc['allocated_cost_cents']==100 and nc['verified_received_cents']==0 and nc['declared_remaining_cents']==100
    assert nc['reported_pending_count']==1 and nc['voluntary'] and not nc['affects_access']
    assert not f['commercial']['controls_allowed'] and data['resources']['cpu']['closed_seconds']==1
    assert 'instructions' not in json.dumps(f) and 'evidence_sha256' not in json.dumps(f)


def test_receipts_excess_and_other_owners_remain_separate(nc_env):
    enable(nc_env);item=pledge(nc_env);receipt(nc_env,item,amount=150)
    alice=account_limits.summary(nc_env[1],STORAGE,at=500)['financial_context']['noncommercial']
    bob=account_limits.summary(nc_env[2],STORAGE,at=500)['financial_context']['noncommercial']
    assert (alice['allocated_cost_cents'],alice['verified_received_cents'],alice['refund_due_cents'])==(100,100,50)
    assert (bob['allocated_cost_cents'],bob['verified_received_cents'],bob['refund_due_cents'])==(200,0,0)


def test_commercial_wallet_remains_distinct_from_cost_shares(account):
    plan(account);resources.grant(account,123456,'wallet fixture',1,'account-context-grant')
    f=account_limits.summary(account,STORAGE)['financial_context']
    assert f['regime']=='COMMERCIAL' and f['commercial']['credit_balance_micro']==123456
    assert f['commercial']['controls_allowed'] and f['commercial']['subscription']=='day'
    assert f['noncommercial']['allocated_cost_cents']==0 and f['aggregate_outstanding_debt_micro'] is None


def test_actual_api_is_private_and_does_not_accept_another_owner_selector(nc_env,monkeypatch):
    monkeypatch.setattr(main,'NATIVE_SINGLE_USER',False);monkeypatch.setattr(main,'check_basic_auth',lambda request:False)
    client=TestClient(main.app)
    assert client.get('/api/account/limits').status_code in (401,403)
    client.cookies.update(cookie(nc_env[1]))
    result=client.get('/api/account/limits?user_id='+str(nc_env[2]))
    assert result.status_code==200,result.text
    assert result.json()['user_id']==nc_env[1]
    assert result.json()['financial_context']['noncommercial']['allocated_cost_cents']==100


def test_tampered_receipt_fails_closed_without_private_details(nc_env,monkeypatch):
    enable(nc_env);item=pledge(nc_env);receipt(nc_env,item)
    with auth.db() as c:
        c.execute('DROP TRIGGER nc_contribution_events_immutable_update')
        c.execute("UPDATE nc_contribution_events SET payload_sha256=?",('0'*64,))
    client=TestClient(main.app);client.cookies.update(cookie(nc_env[1]))
    result=client.get('/api/account/limits')
    assert result.status_code==409 and 'Personal accounting unavailable' in result.text
    assert item['id'] not in result.text and 'sha256' not in result.text
