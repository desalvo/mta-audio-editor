"""Explicit contractual no-charge, not fabricated zero resource consumption."""
from concurrent.futures import ThreadPoolExecutor
import json
import sqlite3
import time

import pytest
from app import auth,ai_billing,worker_cgroup_recovery as processes,worker_loss_resolution as losses
from app.regime_operation_fence import FenceBlocked
from test_r210_subscriptions import account as account  # noqa: F401
from test_r210_durable_cgroup_recovery import kernel as kernel,owned as owned,dead,economic_state  # noqa: F401


@pytest.fixture
def stopped(owned,monkeypatch):
    processes.owner_quiescent(owned[1]);dead(monkeypatch)
    return owned


def preview(owned):
    with auth.db() as c:return losses.preview(c,owned[0],1)


def body(owned,**changes):
    return {'request_id':'approve-operator-loss-0001','expected_sha256':preview(owned)['expected_sha256'],
            'reason':'Documented worker crash; operator absorbs the unrecoverable service cost.',
            'evidence_sha256':'a'*64,'confirm_operator_loss':True,'confirm_no_customer_charge':True,
            'confirm_no_reallocation':True,**changes}


def test_explicit_operator_loss_closes_original_contract_claim_fence_without_invented_usage(stopped,account):
    before=economic_state()
    result=losses.resolve(stopped[0],1,body(stopped))
    assert result['unknown_consumption'] and result['customer_charge_micro']==0
    assert result['operator_assumes_loss'] and result['reallocation_to_other_users'] is False
    with auth.db() as c:
        job=c.execute('SELECT * FROM ai_compute_jobs WHERE id=?',(stopped[0],)).fetchone()
        assert job['status']=='failed' and job['usage_json']=='{}' and job['resource_source']=='unmetered'
        assert job['billable']==1 and job['accounting_excluded']==1
        assert c.execute('SELECT state FROM regime_worker_claims').fetchone()[0]=='finished'
        assert c.execute('SELECT status FROM regime_fence_operations').fetchone()[0]=='closed'
        contract=c.execute('SELECT settled,charge_micro FROM resource_job_contracts').fetchone()
        assert tuple(contract)==(1,0)
        assert losses.history(c,account)[0]['id']==result['id']
        assert losses.audit(c)['verified']
        raw=c.execute('SELECT record_json FROM worker_loss_resolutions').fetchone()[0]
        assert 'original-private-token' not in raw and json.loads(raw)['snapshot']['job']['usage_json']=='{}'
    assert economic_state()['credits']==before['credits']


def test_approval_idempotent_and_concurrent(stopped):
    request=body(stopped)
    with ThreadPoolExecutor(3) as pool:
        results=list(pool.map(lambda _:losses.resolve(stopped[0],1,request),range(3)))
    assert results[0]==results[1]==results[2]
    with auth.db() as c:assert c.execute('SELECT count(*) FROM worker_loss_resolutions').fetchone()[0]==1


def test_registered_frozen_evidence_cannot_be_discarded(stopped,monkeypatch):
    from app import ai_arranger_runtime as queue
    monkeypatch.setattr(queue,'_process_identity',lambda _:'irrelevant')
    losses.mark_evidence(stopped[0],stopped[2]['worker_id'],stopped[2]['claim_token'])
    with pytest.raises(FenceBlocked,match='Existing evidence'):preview(stopped)


def test_gpu_lease_release_and_credit_reservation_are_atomic(stopped):
    from app import ai_gpu_slot_accounting as slots
    slots.acquire(stopped[0])
    result=losses.resolve(stopped[0],1,body(stopped))
    assert result['gpu_lease_released']
    with auth.db() as c:
        lease=c.execute('SELECT state,released_ms FROM ai_gpu_slot_leases').fetchone()
        assert lease[0]=='aborted' and lease[1] is not None


@pytest.mark.parametrize('flag',['confirm_operator_loss','confirm_no_customer_charge','confirm_no_reallocation'])
def test_each_approval_confirmation_is_required(stopped,flag):
    before=economic_state()
    with pytest.raises(ValueError):losses.resolve(stopped[0],1,body(stopped,**{flag:False}))
    assert economic_state()==before


def test_live_supervisor_and_missing_quiescence_never_approved(owned):
    with pytest.raises(FenceBlocked):preview(owned)


def test_stale_preview_cannot_release_changed_reservations(stopped):
    request=body(stopped)
    with auth.db() as c:c.execute('UPDATE resource_job_budgets SET budget_micro=budget_micro+1')
    before=economic_state()
    with pytest.raises(FenceBlocked,match='stale'):losses.resolve(stopped[0],1,request)
    assert economic_state()==before


def test_legacy_admission_cannot_silently_gain_negative_evidence(stopped):
    with auth.db() as c:c.execute("UPDATE ai_compute_jobs SET recovery_evidence_state='legacy_unknown'")
    with pytest.raises(FenceBlocked,match='legacy uncertainty'):preview(stopped)


def test_late_receipt_or_new_billing_cannot_resurrect_approved_loss(stopped):
    losses.resolve(stopped[0],1,body(stopped))
    with pytest.raises(FenceBlocked):losses.mark_evidence(stopped[0],stopped[2]['worker_id'],stopped[2]['claim_token'])
    with pytest.raises(FenceBlocked):ai_billing.finish_job(stopped[0],'done',{'cpu_seconds':1},source='worker',**stopped[2])


def test_failed_close_rolls_back_contract_lease_and_approval(stopped,monkeypatch):
    from app import regime_job_fence
    request=body(stopped);before=economic_state()
    monkeypatch.setattr(regime_job_fence,'settle_metered_job',lambda *a:(_ for _ in ()).throw(RuntimeError('before fence ack')))
    with pytest.raises(RuntimeError):losses.resolve(stopped[0],1,request)
    assert economic_state()==before
    with auth.db() as c:assert c.execute("SELECT 1 FROM sqlite_master WHERE name='worker_loss_resolutions'").fetchone() is None


def test_nc_cost_basis_must_explicitly_exclude_operator_loss(stopped):
    from app.noncommercial_allocation import preview_from_metered_jobs
    losses.resolve(stopped[0],1,body(stopped));end=int(time.time())+3
    with auth.db() as c:
        with pytest.raises(ValueError,match='exclude operator-assumed'):
            preview_from_metered_jobs(c,start=0,end=end,documented_cost_cents=100)
        draft=preview_from_metered_jobs(c,start=0,end=end,documented_cost_cents=100,operator_cost_exclusion_confirmed=True)
        assert draft['total_draft_cents']==0 and draft['measured_milliseconds']=={}
        assert draft['operator_losses'][0]['job_id']==stopped[0]


def test_approval_is_immutable_and_journal_corruption_blocks_readiness(stopped):
    losses.resolve(stopped[0],1,body(stopped))
    with auth.db() as c:
        with pytest.raises(sqlite3.IntegrityError):c.execute('DELETE FROM worker_loss_resolutions')
        with pytest.raises(sqlite3.IntegrityError):c.execute("UPDATE worker_loss_resolutions SET sha256='changed'")
        c.execute('DROP TRIGGER worker_loss_immutable_update')
        c.execute("UPDATE worker_loss_resolutions SET record_json='{}'")
        assert losses.audit(c)['verified'] is False
        assert processes.report(c)['verified'] is False


def test_missing_approval_journal_is_not_recreated(stopped):
    request=body(stopped);losses.resolve(stopped[0],1,request)
    with auth.db() as c:c.execute('DROP TABLE worker_loss_resolutions')
    with pytest.raises(FenceBlocked,match='cannot recreate'):losses.resolve(stopped[0],1,request)
    with auth.db() as c:assert losses.audit(c)['verified'] is False


def test_altered_request_cannot_reapprove_finished_job(stopped):
    request=body(stopped);losses.resolve(stopped[0],1,request)
    request['reason']='Changed justification must not overwrite the original approval.'
    with pytest.raises(FenceBlocked,match='Conflicting'):losses.resolve(stopped[0],1,request)


def test_approved_reservation_outcome_cannot_change_silently(stopped):
    losses.resolve(stopped[0],1,body(stopped))
    with auth.db() as c:
        c.execute('UPDATE resource_job_contracts SET charge_micro=5')
        assert losses.audit(c)['verified'] is False


def test_loss_rows_follow_scoped_retired_owner_erasure(stopped,account):
    from app.account_lifecycle import init,_rows_for_user
    result=losses.resolve(stopped[0],1,body(stopped))
    with auth.db() as c:
        init(c);c.execute('BEGIN IMMEDIATE')
        with pytest.raises(FenceBlocked):losses.authorize_account_erasure(c,account,1)
        c.execute('UPDATE users SET active=0 WHERE id=?',(account,))
        c.execute("INSERT OR REPLACE INTO account_lifecycle(user_id,state) VALUES(?,'erasing')",(account,))
        losses.authorize_account_erasure(c,account,1)
        selected,_=_rows_for_user(c,account)
        assert len(selected['worker_loss_resolutions'])==1
        c.execute('DELETE FROM worker_loss_resolutions WHERE id=?',(result['id'],))


def test_new_api_auth_csrf_exact_fields_and_private_history(stopped,monkeypatch,account):
    from app import main
    from fastapi.testclient import TestClient
    client=TestClient(main.app);identity=[None]
    monkeypatch.setattr(auth,'session_user',lambda request:identity[0])
    monkeypatch.setattr(main,'session_user',lambda request:identity[0])
    root='/api/admin/service-regime/worker-losses/'+stopped[0]
    assert client.get(root+'/preview').status_code==401
    identity[0]=auth.get_user(account)
    assert client.get(root+'/preview').status_code==403
    identity[0]=auth.get_user(1)
    plan=client.get(root+'/preview').json();request=body(stopped,expected_sha256=plan['expected_sha256'])
    assert client.post(root+'/resolve',json=request).status_code==403
    headers={'X-MTA-Request':'1'}
    assert client.post(root+'/resolve',json={**request,'charge_micro':100},headers=headers).status_code==422
    response=client.post(root+'/resolve',json=request,headers=headers)
    assert response.status_code==200 and response.json()['customer_charge_micro']==0
    identity[0]=auth.get_user(account)
    own=client.get('/api/account/worker-losses');assert len(own.json()['losses'])==1
    assert 'original-private-token' not in own.text and 'snapshot' not in own.text
    identity[0]=auth.get_user(1)
    assert client.get('/api/account/worker-losses').json()['losses']==[]


def test_scoped_approval_cannot_be_self_verified(stopped,account):
    with auth.db() as c:c.execute("UPDATE users SET role='admin' WHERE id=?",(account,))
    with auth.db() as c:
        with pytest.raises(FenceBlocked,match='Another administrator'):
            losses.preview(c,stopped[0],account)


@pytest.mark.parametrize('producer',['gpu','estimate'])
def test_persisted_metering_cannot_be_discarded_even_if_marker_was_missing(stopped,producer):
    with auth.db() as c:
        if producer=='gpu':
            c.execute('CREATE TABLE ai_verified_gpu_evidence(job_id TEXT PRIMARY KEY)')
            c.execute('INSERT INTO ai_verified_gpu_evidence VALUES(?)',(stopped[0],))
        else:
            c.execute('CREATE TABLE ai_trusted_estimate_evidence(job_id TEXT PRIMARY KEY)')
            c.execute('INSERT INTO ai_trusted_estimate_evidence VALUES(?)',(stopped[0],))
    with pytest.raises(FenceBlocked,match='Persisted metering'):preview(stopped)


def test_late_producer_transaction_cannot_commit_evidence_after_loss(stopped):
    losses.resolve(stopped[0],1,body(stopped))
    with auth.db() as c:
        c.execute('BEGIN IMMEDIATE')
        with pytest.raises(FenceBlocked):losses.note_evidence_in_transaction(c,stopped[0])


def test_billing_report_retains_visible_unknown_loss_instead_of_silent_omission(stopped,account):
    losses.resolve(stopped[0],1,body(stopped))
    report=ai_billing.report('day',user_id=account)
    assert report['operator_losses'][0]['unknown_consumption']
    assert report['operator_losses'][0]['customer_charge_micro']==0 and report['job_count']==0


def test_released_lease_without_journal_commit_is_rolled_back(stopped,monkeypatch):
    from app import ai_gpu_slot_accounting as slots,regime_job_fence
    slots.acquire(stopped[0]);request=body(stopped)
    monkeypatch.setattr(regime_job_fence,'settle_metered_job',lambda *a:(_ for _ in ()).throw(RuntimeError('abort transaction')))
    with pytest.raises(RuntimeError):losses.resolve(stopped[0],1,request)
    with auth.db() as c:
        assert tuple(c.execute('SELECT state,released_ms FROM ai_gpu_slot_leases').fetchone())==('active',None)
