"""Regression gates for explicit durable inference/ledger associations."""
from contextlib import contextmanager
import sqlite3
import pytest
from app import ai_arranger_runtime as queue
from app import ai_billing_outbox as billing


@pytest.fixture
def staged(monkeypatch, tmp_path):
    monkeypatch.setattr(queue, '_ROOT', tmp_path)
    with queue._db() as con:
        con.execute("INSERT INTO jobs(job_id,project_id,operation,state,rank,created_at,phase,message,payload_json) VALUES('inference1','p1','arranger','queued',1,0,'queued','test','{}')")
    @contextmanager
    def ledger_db():
        con = sqlite3.connect(':memory:')
        con.row_factory = sqlite3.Row
        con.execute('CREATE TABLE ai_compute_jobs(id TEXT,user_id INTEGER,kind TEXT,status TEXT)')
        con.execute("INSERT INTO ai_compute_jobs VALUES('ledger1',17,'arranger','running')")
        try:
            yield con
        finally:
            con.close()
    monkeypatch.setattr(billing.ai_billing, 'db', ledger_db)
    monkeypatch.setattr(billing.ai_billing, '_init', lambda con: None)


def test_verified_binding_and_idempotence(staged):
    assert billing.register_verified('inference1', 'ledger1', 17, 'done') is True
    assert billing.register_verified('inference1', 'ledger1', 17, 'done') is False
    assert billing.inspect('inference1')['state'] == 'pending'


def test_other_user_refused(staged):
    with pytest.raises(ValueError, match='another user'):
        billing.register_verified('inference1', 'ledger1', 18, 'done')
    assert billing.inspect('inference1') is None


def test_missing_inference_refused(staged):
    with pytest.raises(ValueError, match='Durable inference'):
        billing.register_verified('nonexistent', 'ledger1', 17, 'done')


def test_bad_identity_refused(staged):
    with pytest.raises(ValueError, match='Authenticated'):
        billing.register_verified('inference1', 'ledger1', True, 'done')


def test_kind_mismatch_refused(staged, monkeypatch):
    @contextmanager
    def other_db():
        con = sqlite3.connect(':memory:')
        con.row_factory = sqlite3.Row
        con.execute('CREATE TABLE ai_compute_jobs(id TEXT,user_id INTEGER,kind TEXT,status TEXT)')
        con.execute("INSERT INTO ai_compute_jobs VALUES('ledger1',17,'whisper','running')")
        try:
            yield con
        finally:
            con.close()
    monkeypatch.setattr(billing.ai_billing, 'db', other_db)
    with pytest.raises(ValueError, match='kind mismatch'):
        billing.register_verified('inference1', 'ledger1', 17, 'done')


@pytest.mark.parametrize('payload', [
    '[]', 'null', '123', '"hello"', 'true', '{',
    '{"schema_version":null}', '{"schema_version":0}', '{"schema_version":2}',
    '{"schema_version":true}', '{"schema_version":"1"}',
    '{"schema_version":1}', '{"schema_version":1,"actor_user_id":null}',
    '{"schema_version":1,"actor_user_id":true}',
    '{"schema_version":1,"actor_user_id":0}',
    '{"schema_version":1,"actor_user_id":-1}',
    '{"schema_version":1,"actor_user_id":"17"}',
    '{"schema_version":1,"actor_user_id":18,"adapter":"arranger"}',
    '{"schema_version":1,"actor_user_id":17}',
    '{"schema_version":1,"actor_user_id":17,"adapter":"remix"}',
    '{"actor_user_id":17}', '{"adapter":"arranger"}',
    '{"actor_user_id":17,"adapter":"arranger"}',
])
def test_verified_binding_rejects_malformed_identity_contract(staged, payload):
    with queue._db() as con:
        con.execute('UPDATE jobs SET payload_json=? WHERE job_id=?', (payload, 'inference1'))
    with pytest.raises((ValueError, TypeError)):
        billing.register_verified('inference1', 'ledger1', 17, 'done')
    assert billing.inspect('inference1') is None


def test_verified_binding_accepts_versioned_owner_and_adapter(staged):
    with queue._db() as con:
        con.execute('UPDATE jobs SET payload_json=? WHERE job_id=?',
                    ('{"schema_version":1,"actor_user_id":17,"adapter":"arranger"}', 'inference1'))
    assert billing.register_verified('inference1', 'ledger1', 17, 'done')
