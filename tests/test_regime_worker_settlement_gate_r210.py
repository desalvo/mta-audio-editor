"""Regression for ledger, claim and accounting convergence at the real billing fence."""
import sqlite3
import pytest

from app.regime_operation_fence import initialize, admit, FenceBlocked
from app.regime_worker_claims import claim, finish
from app.regime_job_fence import settle_metered_job


def setup(*, billable=1):
    c = sqlite3.connect(':memory:', isolation_level=None)
    c.execute('CREATE TABLE ai_compute_jobs(id TEXT PRIMARY KEY,status TEXT,billable INTEGER)')
    c.execute('CREATE TABLE resource_job_contracts(job_id TEXT PRIMARY KEY,settled INTEGER)')
    c.execute("INSERT INTO ai_compute_jobs VALUES ('a','running',?)", (billable,))
    c.execute("INSERT INTO resource_job_contracts VALUES ('a',0)")
    c.execute('BEGIN IMMEDIATE')
    initialize(c)
    admit(c, 'job:ledger:a', 'job')
    claim(c,'a',worker_id='worker',token='token')
    finish(c,'job:ledger:a',worker_id='worker',token='token')
    return c


def test_worker_receipt_cannot_close_running_ledger():
    c=setup()
    with pytest.raises(FenceBlocked, match='running'):
        settle_metered_job(c,'a')
    assert c.execute('SELECT status FROM regime_fence_operations').fetchone()[0]=='open'


def test_worker_receipt_cannot_close_unsettled_billable_ledger():
    c=setup()
    c.execute("UPDATE ai_compute_jobs SET status='completed'")
    with pytest.raises(FenceBlocked,match='accounting'):
        settle_metered_job(c,'a')
    c.execute('UPDATE resource_job_contracts SET settled=1')
    settle_metered_job(c,'a')
    assert c.execute('SELECT status FROM regime_fence_operations').fetchone()[0]=='closed'


def test_worker_epoch_mismatch_rejected():
    c=setup(billable=0)
    c.execute("UPDATE ai_compute_jobs SET status='failed'")
    c.execute('UPDATE regime_worker_claims SET revision=revision+1')
    with pytest.raises(FenceBlocked,match='consistently'):
        settle_metered_job(c,'a')


def test_billable_worker_missing_contract_fails_closed():
    c=setup()
    c.execute("UPDATE ai_compute_jobs SET status='completed'")
    c.execute('DELETE FROM resource_job_contracts')
    with pytest.raises(FenceBlocked,match='accounting'):
        settle_metered_job(c,'a')


def test_unbillable_worker_terminal_may_close():
    c=setup(billable=0)
    c.execute("UPDATE ai_compute_jobs SET status='failed'")
    settle_metered_job(c,'a')
    assert c.execute('SELECT status FROM regime_fence_operations').fetchone()[0]=='closed'
