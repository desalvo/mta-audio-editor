import sqlite3
import pytest
from app.regime_operation_fence import FenceBlocked, initialize, admit
from app.regime_worker_claims import claim
from app.regime_worker_completion import complete_claimed_job


def setup(tmp_path, *, billable=1):
    path=tmp_path/'worker.sqlite'
    c=sqlite3.connect(path, isolation_level=None)
    c.executescript('''CREATE TABLE ai_compute_jobs(id TEXT PRIMARY KEY,status TEXT NOT NULL,billable INTEGER NOT NULL);
    CREATE TABLE resource_job_contracts(job_id TEXT PRIMARY KEY,settled INTEGER NOT NULL);''')
    c.execute('INSERT INTO ai_compute_jobs VALUES(?,?,?)',('job1','running',billable))
    c.execute('INSERT INTO resource_job_contracts VALUES(?,0)',('job1',))
    c.execute('BEGIN IMMEDIATE'); initialize(c); admit(c,'job:ledger:job1','job'); claim(c,'job1',worker_id='worker',token='token');c.commit()
    return c,path


def test_atomic_completion_and_idempotent_retry(tmp_path):
    c,path=setup(tmp_path)
    for status,settled in [('running',0),('completed',0)]:
        c.execute('UPDATE ai_compute_jobs SET status=?',(status,))
        c.execute('UPDATE resource_job_contracts SET settled=?',(settled,))
        with pytest.raises(FenceBlocked): complete_claimed_job(c,ledger_id='job1',worker_id='worker',token='token')
        assert c.execute('SELECT state FROM regime_worker_claims').fetchone()[0]=='running'
    c.execute('UPDATE resource_job_contracts SET settled=1')
    assert complete_claimed_job(c,ledger_id='job1',worker_id='worker',token='token')['completed']
    assert not complete_claimed_job(c,ledger_id='job1',worker_id='worker',token='token')['completed']
    assert c.execute('SELECT status FROM regime_fence_operations').fetchone()[0]=='closed'
    other=sqlite3.connect(path,isolation_level=None)
    with pytest.raises(FenceBlocked):complete_claimed_job(other,ledger_id='job1',worker_id='other',token='token')


def test_failed_attempt_preserves_claim_and_transaction(tmp_path):
    c,_=setup(tmp_path,billable=0)
    c.execute("UPDATE ai_compute_jobs SET status='failed'")
    with pytest.raises(FenceBlocked):complete_claimed_job(c,ledger_id='job1',worker_id='worker',token='wrong')
    assert not c.in_transaction
    assert complete_claimed_job(c,ledger_id='job1',worker_id='worker',token='token')['completed']


def test_epoch_drift_and_partial_completion_are_blocked(tmp_path):
    c,_=setup(tmp_path,billable=0)
    c.execute("UPDATE ai_compute_jobs SET status='completed'")
    c.execute('UPDATE regime_fence_state SET revision=revision+1')
    with pytest.raises(FenceBlocked):complete_claimed_job(c,ledger_id='job1',worker_id='worker',token='token')
    c.execute('UPDATE regime_fence_state SET revision=revision-1')
    c.execute("UPDATE regime_worker_claims SET state='finished'")
    with pytest.raises(FenceBlocked):complete_claimed_job(c,ledger_id='job1',worker_id='worker',token='token')
