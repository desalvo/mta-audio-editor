import sqlite3
import pytest
from app.regime_operation_fence import initialize, admit, FenceBlocked
from app.regime_worker_claims import claim, finish, audit_claim_integrity
from app.regime_job_fence import settle_metered_job


def setup():
    c = sqlite3.connect(':memory:', isolation_level=None)
    c.execute('BEGIN IMMEDIATE')
    initialize(c)
    c.execute('CREATE TABLE ai_compute_jobs (id TEXT PRIMARY KEY, status TEXT NOT NULL,billable INTEGER NOT NULL)')
    c.execute("INSERT INTO ai_compute_jobs VALUES ('abc','running',0)")
    admit(c, 'job:ledger:abc', 'job')
    return c


def test_running_worker_prevents_atomic_settlement():
    c=setup()
    claim(c, 'abc', worker_id='node1', token='token1')
    with pytest.raises(FenceBlocked, match='active worker'):
        settle_metered_job(c, 'abc')
    finish(c,'job:ledger:abc',worker_id='node1',token='token1')
    c.execute("UPDATE ai_compute_jobs SET status='completed' WHERE id='abc'")
    settle_metered_job(c, 'abc')
    assert audit_claim_integrity(c)['safe']


def test_reject_orphan_claim_and_epoch_mismatch():
    c=setup()
    claim(c, 'abc',worker_id='node1',token='token1')
    assert audit_claim_integrity(c)['safe']
    c.execute("DELETE FROM ai_compute_jobs WHERE id='abc'")
    assert audit_claim_integrity(c)['issues']['orphaned_ledger_job']==1
    c.execute("INSERT INTO ai_compute_jobs VALUES ('abc','running',0)")
    c.execute("UPDATE regime_worker_claims SET revision=123")
    assert audit_claim_integrity(c)['issues']['claim_receipt_mismatch']==1


def test_closed_fence_with_running_worker_detected():
    c=setup()
    claim(c,'abc',worker_id='node1',token='token1')
    c.execute("UPDATE regime_fence_operations SET status='closed'")
    assert audit_claim_integrity(c)['issues']['running_claim_closed_fence']==1


def test_missing_schema_is_not_reported_clean():
    c=sqlite3.connect(':memory:')
    assert not audit_claim_integrity(c)['safe']
