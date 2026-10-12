"""Agentless slot charges are immutable, historical and separately labeled."""
import datetime as dt
import pytest
from app.auth import db, init_auth_db
from app import ai_billing, ai_gpu_slot_accounting as slots

START = int(dt.datetime(2026, 10, 1, tzinfo=dt.timezone.utc).timestamp())

@pytest.fixture(autouse=True)
def environment(tmp_path, monkeypatch):
    monkeypatch.setenv('MTA_DATA_DIR', str(tmp_path))
    monkeypatch.delenv('MTA_AI_USER_STORAGE_ROOT', raising=False)
    init_auth_db()
    with db() as c:
        for i in (1, 2):
            c.execute('INSERT INTO users(id,username,email,password_hash,active,role,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?)',
                      (i,f'u{i}',f'u{i}@example.com','x',1,'user',1,1))

def _job(uid, start, end, diag=False):
    jid=ai_billing.create_job(uid,'demucs',started_at=start,diagnostic=diag)
    slots.acquire(jid,at_ms=start*1000)
    slots.release(jid,at_ms=end*1000)
    ai_billing.finish_job(jid,'done',{'cpu_seconds':1},source='cgroup',finished_at=end)
    return jid

def test_concurrency_paid_tariff_and_closed_snapshot():
    ai_billing.set_price('gpu_slot_seconds_estimated',1000,valid_from=START)
    _job(1,START+10,START+20)
    _job(2,START+10,START+20)
    a=ai_billing.report('custom',user_id=1,start='2026-10-01',end='2026-10-02')
    b=ai_billing.report('custom',user_id=2,start='2026-10-01',end='2026-10-02')
    assert a['gpu_slot_service']['jobs'][0]['slot_seconds']==5
    assert a['total_micro']==5000 and b['total_micro']==5000
    first=ai_billing.close_period(1,'2026-10-01','2026-10-02')
    second=ai_billing.close_period(1,'2026-10-01','2026-10-02')
    assert first['total_micro']==5000 and not first['already_closed']
    assert second['already_closed'] and second['total_micro']==5000
    assert ai_billing.audit_closed_invoices(1)['ready']
    with pytest.raises(ValueError):
        ai_billing.set_price('gpu_slot_seconds_estimated',2000,valid_from=START+5)

def test_tariff_changes_split_lease_exactly():
    ai_billing.set_price('gpu_slot_seconds_estimated',1000,valid_from=START)
    ai_billing.set_price('gpu_slot_seconds_estimated',2000,valid_from=START+15)
    _job(1,START+10,START+20)
    out=ai_billing.report('custom',user_id=1,start='2026-10-01',end='2026-10-02')
    assert out['total_micro']==15000

def test_unfinished_slot_blocks_invoice():
    ai_billing.set_price('gpu_slot_seconds_estimated',1000,valid_from=START)
    jid=ai_billing.create_job(1,'demucs',started_at=START+10)
    slots.acquire(jid,at_ms=(START+10)*1000)
    with pytest.raises(ValueError):
        ai_billing.close_period(1,'2026-10-01','2026-10-02')

def test_disabled_default_produces_no_gpu_invoice():
    _job(1,START+10,START+20)
    out=ai_billing.report('custom',user_id=1,start='2026-10-01',end='2026-10-02')
    assert out['gpu_slot_service']['enabled'] is False
    assert out['total_micro']==0

def test_diagnostic_has_no_gpu_charge():
    ai_billing.set_price('gpu_slot_seconds_estimated',1000,valid_from=START)
    _job(1,START+10,START+20,diag=True)
    out=ai_billing.report('custom',user_id=1,start='2026-10-01',end='2026-10-02')
    assert out['total_micro']==0

def test_priced_gpu_worker_without_slot_fails_closed(monkeypatch):
    monkeypatch.setenv('MTA_AI_GPU_SLOT_TRACKING_ENABLED','true')
    monkeypatch.setenv('MTA_AI_GPU_SLOT_KINDS','demucs')
    ai_billing.set_price('gpu_slot_seconds_estimated',1000,valid_from=START)
    job=ai_billing.create_job(1,'demucs',started_at=START+10)
    ai_billing.finish_job(job,'done',{'cpu_seconds':1},source='cgroup',finished_at=START+20)
    with pytest.raises(ValueError, match='no allocated slot evidence'):
        ai_billing.close_period(1,'2026-10-01','2026-10-02')


def test_untrusted_worker_cannot_claim_gpu_slot_resource():
    job=ai_billing.create_job(1,'demucs',started_at=START+10)
    with pytest.raises(ValueError, match='Unsupported resource'):
        ai_billing.finish_job(job,'done',{'gpu_slot_seconds_estimated':5},
                              source='worker',finished_at=START+20)


def test_priced_slot_and_measured_gpu_are_mutually_exclusive():
    ai_billing.set_price('gpu_slot_seconds_estimated',1000,valid_from=START)
    ai_billing.set_price('gpu_seconds',2000,valid_from=START)
    _job(1,START+10,START+20)
    with pytest.raises(ValueError, match='cannot both be active'):
        ai_billing.close_period(1,'2026-10-01','2026-10-02')


def test_reconcile_recognizes_separate_slot_evidence():
    ai_billing.set_price('gpu_slot_seconds_estimated',1000,valid_from=START)
    _job(1,START+10,START+20)
    result=ai_billing.reconcile_period(1,'2026-10-01','2026-10-02')
    assert result['ready'],result['issues']
