"""Durable actor and ledger ownership must match across both databases."""
from contextlib import contextmanager
import json
import sqlite3
import pytest
from app import ai_arranger_runtime as queue, ai_billing_outbox as outbox

@pytest.fixture
def scoped(monkeypatch, tmp_path):
    monkeypatch.setattr(queue, '_ROOT', tmp_path)
    with queue._db() as con:
        con.execute("INSERT INTO jobs(job_id,project_id,operation,state,rank,created_at,phase,message,payload_json) VALUES(?,?,?,?,?,?,?,?,?)", ('owner-test', 'p', 'arranger', 'queued', 1, 0, 'queued', 'test', json.dumps({'schema_version':1, 'actor_user_id':7, 'adapter':'arranger'})))
    @contextmanager
    def db():
        con = sqlite3.connect(':memory:')
        con.row_factory = sqlite3.Row
        con.execute('CREATE TABLE ai_compute_jobs(id TEXT,user_id INTEGER,kind TEXT,status TEXT)')
        con.execute("INSERT INTO ai_compute_jobs VALUES('bill-test',8,'arranger','running')")
        try: yield con
        finally: con.close()
    monkeypatch.setattr(outbox.ai_billing,'db',db)
    monkeypatch.setattr(outbox.ai_billing,'_init',lambda c:None)
    return tmp_path

def test_no_cross_user_binding_even_with_owned_ledger(scoped):
    with pytest.raises(ValueError, match='owner mismatch'):
        outbox.register_verified('owner-test','bill-test',8,'done')
    assert outbox.inspect('owner-test') is None

def test_valid_actor_cannot_bind_to_other_users_ledger(scoped):
    with pytest.raises(ValueError, match='another user'):
        outbox.register_verified('owner-test','bill-test',7,'done')

def test_corrupt_actor_payload_cannot_create_intent(scoped):
    with queue._db() as c:
        c.execute("UPDATE jobs SET payload_json='not json' WHERE job_id='owner-test'")
    with pytest.raises(ValueError,match='Invalid durable inference payload'):
        outbox.register_verified('owner-test','bill-test',8,'done')
