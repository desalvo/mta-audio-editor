"""Exercise the actual ai_billing.finish_job transaction with durable worker claims."""
import contextlib
import sqlite3
import time

import pytest
from app import ai_billing, resource_accounts
from app.regime_operation_fence import initialize, admit, FenceBlocked
from app.regime_worker_claims import claim


@pytest.fixture
def billing(tmp_path, monkeypatch):
    path = tmp_path / 'billing.sqlite'
    c = sqlite3.connect(path)
    c.row_factory = sqlite3.Row
    c.executescript('''
        CREATE TABLE ai_compute_jobs (id TEXT PRIMARY KEY,user_id INTEGER,started_at INTEGER,
            status TEXT,billable INTEGER,finished_at INTEGER,wall_ms INTEGER,
            usage_json TEXT,resource_source TEXT);
        CREATE TABLE ai_billing_periods(user_id INTEGER,start_ts INTEGER,end_ts INTEGER);
        CREATE TABLE resource_job_contracts(job_id TEXT PRIMARY KEY,settled INTEGER);
    ''')
    c.execute("INSERT INTO ai_compute_jobs VALUES ('job',1,?,'running',1,NULL,0,'{}','unmetered')", (int(time.time())-10,))
    c.execute("INSERT INTO resource_job_contracts VALUES ('job',0)")
    c.commit()
    c.execute('BEGIN IMMEDIATE')
    initialize(c)
    admit(c,'job:ledger:job','job')
    claim(c,'job',worker_id='w1',token='secret')
    c.commit()
    c.close()

    @contextlib.contextmanager
    def database():
        connection = sqlite3.connect(path)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
            connection.commit()
        except BaseException:
            connection.rollback()
            raise
        finally:
            connection.close()

    monkeypatch.setattr(ai_billing, 'db', database)
    monkeypatch.setattr(ai_billing, '_init', lambda c: None)
    monkeypatch.setattr(resource_accounts, 'prepare_upgrade', lambda c: None)
    monkeypatch.setattr(resource_accounts, 'settle', lambda c, j, v: c.execute('UPDATE resource_job_contracts SET settled=1 WHERE job_id=?', (j,)))
    return path


def state(path):
    with sqlite3.connect(path) as c:
        return (c.execute('SELECT status FROM ai_compute_jobs').fetchone()[0],
                c.execute('SELECT settled FROM resource_job_contracts').fetchone()[0],
                c.execute('SELECT state FROM regime_worker_claims').fetchone()[0],
                c.execute('SELECT status FROM regime_fence_operations').fetchone()[0])


def test_owner_completes_accounting_claim_and_fence_atomically(billing):
    ai_billing.finish_job('job', 'done', worker_id='w1', claim_token='secret')
    assert state(billing) == ('done',1,'finished','closed')


@pytest.mark.parametrize('credentials', [{}, {'worker_id':'w2','claim_token':'secret'}, {'worker_id':'w1','claim_token':'wrong'}])
def test_unauthorized_completion_rolls_back_all_changes(billing, credentials):
    with pytest.raises(FenceBlocked):
        ai_billing.finish_job('job','done', **credentials)
    assert state(billing) == ('running',0,'running','open')

@pytest.mark.parametrize('credentials', [
    {}, {'worker_id': 'w2', 'claim_token': 'secret'},
    {'worker_id': 'w1', 'claim_token': 'invalid'},
])
def test_retry_of_claimed_job_rejects_missing_or_foreign_receipt(billing, credentials):
    ai_billing.finish_job('job', 'done', worker_id='w1', claim_token='secret')
    with pytest.raises(FenceBlocked):
        ai_billing.finish_job_idempotent('job', 'done', **credentials)
    assert state(billing) == ('done', 1, 'finished', 'closed')


def test_retry_of_claimed_job_accepts_matching_completed_receipt(billing):
    ai_billing.finish_job('job', 'done', worker_id='w1', claim_token='secret')
    result = ai_billing.finish_job_idempotent('job', 'done', worker_id='w1', claim_token='secret')
    assert result['already_finalized'] is True
    assert state(billing) == ('done', 1, 'finished', 'closed')


def test_first_attempt_idempotent_completion_requires_claim_owner(billing):
    with pytest.raises(FenceBlocked):
        ai_billing.finish_job_idempotent('job', 'done')
    assert state(billing) == ('running', 0, 'running', 'open')
    result = ai_billing.finish_job_idempotent('job','done',worker_id='w1',claim_token='secret')
    assert result['already_finalized'] is False
    assert state(billing) == ('done', 1, 'finished', 'closed')
