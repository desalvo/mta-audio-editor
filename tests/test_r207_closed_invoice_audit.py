"""Immutable snapshot audits must not reprice closed historical invoices."""
import json
import pytest
from app.auth import db, init_auth_db
from app import ai_billing
from scripts.benchmark_ai_concurrency import verify_server_ledger

@pytest.fixture(autouse=True)
def setup(tmp_path, monkeypatch):
    monkeypatch.setenv('MTA_DATA_DIR', str(tmp_path))
    init_auth_db()
    with db() as c:
        for name in ('alpha', 'beta'):
            c.execute('INSERT INTO users(username,email,password_hash,active,role,created_at,updated_at) VALUES(?,?,?,?,?,?,?)',
                      (name,name+'@example.org','x',1,'user',1,1))

def uid(name):
    with db() as c:
        return c.execute('SELECT id FROM users WHERE username=?',(name,)).fetchone()[0]

def test_closed_invoice_snapshot_audit_and_tamper_detection():
    u=uid('alpha')
    result=ai_billing.close_period(u,'2025-05-01','2025-05-31')
    assert ai_billing.audit_closed_invoices()['ready']
    with db() as c:
        c.execute('UPDATE ai_billing_periods SET total_micro=total_micro+500 WHERE id=?',(result['id'],))
    audit=ai_billing.audit_closed_invoices()
    assert not audit['ready']
    assert 'snapshot_total_mismatch' in {x['code'] for x in audit['issues']}

def test_invalid_snapshot_detected():
    u=uid('alpha')
    result=ai_billing.close_period(u,'2025-05-01','2025-05-31')
    with db() as c:
        c.execute('UPDATE ai_billing_periods SET snapshot_json=? WHERE id=?', ('{broken',result['id']))
    assert any(x['code']=='invalid_snapshot_json' for x in ai_billing.audit_closed_invoices()['issues'])

def test_benchmark_verification_isolated_and_checks_counters(tmp_path):
    from app.auth import db_path
    jobs=[]
    for name in ('alpha','beta'):
        job=ai_billing.create_job(uid(name),'whisper')
        ai_billing.finish_job(job,'done',{'cpu_seconds':1.5},source='cgroup')
        jobs.append({'job_id':job,'user':name})
    audit=verify_server_ledger({'jobs':jobs},db_path())
    assert audit['ready'] and audit['user_isolation_valid']
    bad=verify_server_ledger({'jobs':[dict(jobs[0],user='alpha'),dict(jobs[0],user='beta')]},db_path())
    assert not bad['ready']

@pytest.mark.parametrize('bad_value', ['0', 0.0, True, -1, float('nan')])
def test_closed_invoice_rejects_noninteger_snapshot_money(bad_value):
    u=uid('alpha')
    result=ai_billing.close_period(u,'2025-05-01','2025-05-31')
    with db() as c:
        record=c.execute('SELECT snapshot_json FROM ai_billing_periods WHERE id=?',(result['id'],)).fetchone()
        data=json.loads(record[0]); data['total_micro']=bad_value
        c.execute('UPDATE ai_billing_periods SET snapshot_json=? WHERE id=?', (json.dumps(data),result['id']))
    assert not ai_billing.audit_closed_invoices()['ready']


def test_closed_invoice_detects_identity_change():
    u=uid('alpha')
    result=ai_billing.close_period(u,'2025-05-01','2025-05-31')
    with db() as c:
        data=json.loads(c.execute('SELECT snapshot_json FROM ai_billing_periods WHERE id=?',(result['id'],)).fetchone()[0])
        data['user_id']=uid('beta')
        c.execute('UPDATE ai_billing_periods SET snapshot_json=? WHERE id=?',(json.dumps(data),result['id']))
    assert 'snapshot_identity_mismatch' in {issue['code'] for issue in ai_billing.audit_closed_invoices()['issues']}
