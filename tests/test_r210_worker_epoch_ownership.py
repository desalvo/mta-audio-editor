"""Stale authority cannot mutate claims/ledger; closed original proofs can replay."""
from concurrent.futures import ThreadPoolExecutor
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import threading
import time

import pytest

from app import ai_billing
from app.deferred_execution_owner import validate_receipt
from app.regime_job_fence import settle_metered_job
from app.regime_operation_fence import FenceBlocked
from app.regime_worker_claims import audit_claim_integrity, claim, finish, heartbeat
from app.regime_worker_completion import complete_claimed_job
from test_r210_claimed_billing_completion_integration import billing as billing, state  # noqa: F401


OWNER = {'worker_id': 'w1', 'claim_token': 'secret'}


def connect(path):
    c = sqlite3.connect(path)
    c.row_factory = sqlite3.Row
    return c


def corrupt(c, boundary):
    statements = {
        'current_revision': 'UPDATE regime_fence_state SET revision=revision+1',
        'current_regime': "UPDATE regime_fence_state SET regime='COMMERCIAL'",
        'claim_revision': 'UPDATE regime_worker_claims SET revision=revision+1',
        'fence_revision': 'UPDATE regime_fence_operations SET revision=revision+1',
        'barrier': 'UPDATE regime_fence_state SET transitioning=1',
    }
    c.execute(statements[boundary])


@pytest.mark.parametrize('boundary', ['current_revision', 'current_regime', 'claim_revision', 'fence_revision', 'barrier'])
@pytest.mark.parametrize('action', ['claim_retry', 'heartbeat', 'release', 'billing', 'deferred'])
def test_every_active_boundary_rejects_stale_receipt_atomically(billing, boundary, action):
    with connect(billing) as c:
        corrupt(c, boundary)
    before = state(billing)
    with connect(billing) as c:
        c.execute('BEGIN IMMEDIATE')
        before_count = c.execute('SELECT heartbeat_count FROM regime_worker_claims').fetchone()[0]
        with pytest.raises(FenceBlocked):
            if action == 'claim_retry':
                claim(c, 'job', worker_id='w1', token='secret')
            elif action == 'heartbeat':
                heartbeat(c, 'job:ledger:job', worker_id='w1', token='secret')
            elif action == 'release':
                finish(c, 'job:ledger:job', worker_id='w1', token='secret')
            elif action == 'deferred':
                validate_receipt(c, 'job', 'w1', 'secret')
            else:
                # The actual billing function owns a separate transaction.
                c.rollback()
                ai_billing.finish_job('job', 'done', {'cpu_seconds': 2}, source='worker', **OWNER)
        assert c.execute('SELECT heartbeat_count FROM regime_worker_claims').fetchone()[0] == before_count
    assert state(billing) == before == ('running', 0, 'running', 'open')


@pytest.mark.parametrize('boundary', ['claim_revision', 'fence_revision'])
def test_identical_ledger_values_cannot_authenticate_corrupted_closed_proof(billing, boundary):
    ai_billing.finish_job('job', 'done', **OWNER)
    with connect(billing) as c:
        corrupt(c, boundary)
    with pytest.raises(FenceBlocked):
        ai_billing.finish_job_idempotent('job', 'done', **OWNER)
    with connect(billing) as c:
        with pytest.raises(FenceBlocked):
            complete_claimed_job(c, ledger_id='job', worker_id='w1', token='secret')
    assert state(billing) == ('done', 1, 'finished', 'closed')


def test_historical_closed_receipt_survives_later_epoch_without_execution_right(billing):
    ai_billing.finish_job('job', 'done', **OWNER)
    with connect(billing) as c:
        corrupt(c, 'current_revision')
        corrupt(c, 'current_regime')
        corrupt(c, 'barrier')
    assert ai_billing.finish_job_idempotent('job', 'done', **OWNER)['already_finalized']
    with connect(billing) as c:
        validate_receipt(c, 'job', 'w1', 'secret', allow_finished=True)
        assert not complete_claimed_job(c, ledger_id='job', worker_id='w1', token='secret')['completed']
        c.execute('BEGIN IMMEDIATE')
        with pytest.raises(FenceBlocked):
            heartbeat(c, 'job:ledger:job', worker_id='w1', token='secret')
        with pytest.raises(FenceBlocked):
            claim(c, 'job', worker_id='w1', token='secret')
        assert audit_claim_integrity(c)['safe']


def test_released_but_unsettled_claim_cannot_close_old_epoch(billing):
    with connect(billing) as c:
        c.execute('BEGIN IMMEDIATE')
        finish(c, 'job:ledger:job', worker_id='w1', token='secret')
        c.execute("UPDATE ai_compute_jobs SET status='done'")
        c.execute('UPDATE resource_job_contracts SET settled=1')
        corrupt(c, 'current_revision')
        with pytest.raises(FenceBlocked):
            settle_metered_job(c, 'job')
        assert c.execute('SELECT status FROM regime_fence_operations').fetchone()[0] == 'open'


@pytest.mark.parametrize('boundary,reason', [
    ('current_revision', 'running_claim_stale_epoch'),
    ('current_regime', 'running_claim_stale_epoch'),
    ('barrier', 'running_claim_transition_barrier'),
])
def test_read_only_audit_detects_current_epoch_corruption(billing, boundary, reason):
    with connect(billing) as c:
        corrupt(c, boundary)
        before = list(c.iterdump())
        result = audit_claim_integrity(c)
        assert result['verified'] and not result['safe']
        assert result['issues'] == {reason: 1}
        assert list(c.iterdump()) == before


@pytest.mark.parametrize('remove', ['DROP TABLE regime_fence_state', 'DELETE FROM regime_fence_state'])
def test_missing_current_epoch_never_audits_clean(billing, remove):
    with connect(billing) as c:
        c.execute(remove)
        result = audit_claim_integrity(c)
        assert not result['verified'] and not result['safe']


@pytest.mark.parametrize('caller_transaction', [False, True])
def test_audit_uses_one_read_snapshot_without_ending_caller_transaction(billing, caller_transaction):
    with connect(billing) as c:
        c.execute('PRAGMA journal_mode=WAL')
        if caller_transaction:
            c.execute('BEGIN')
        observations = []
        def trace(statement):
            if statement.lstrip().startswith('SELECT c.operation_id'):
                observations.append(c.in_transaction)
                with connect(billing) as writer:
                    corrupt(writer, 'current_revision')
        c.set_trace_callback(trace)
        assert audit_claim_integrity(c)['safe']
        assert observations == [True]
        assert c.in_transaction is caller_transaction
        c.set_trace_callback(None)
        if caller_transaction:
            c.rollback()
        assert audit_claim_integrity(c)['issues'] == {'running_claim_stale_epoch': 1}


def test_audit_operates_on_read_only_connection(billing):
    c = sqlite3.connect(billing.as_uri() + '?mode=ro', uri=True)
    try:
        assert audit_claim_integrity(c)['safe']
        assert not c.in_transaction
    finally:
        c.close()


def test_concurrent_original_owner_delivery_charges_once(billing):
    def deliver(_):
        return ai_billing.finish_job_idempotent('job', 'done', {'cpu_seconds': 2}, source='worker', **OWNER)
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(deliver, range(8)))
    assert sum(not result['already_finalized'] for result in results) == 1
    assert state(billing) == ('done', 1, 'finished', 'closed')
    with pytest.raises(ValueError, match='Conflicting'):
        ai_billing.finish_job_idempotent('job', 'done', {'cpu_seconds': 3}, source='worker', **OWNER)


def test_actual_process_death_after_commit_recovers_closed_original_receipt(billing, tmp_path, monkeypatch):
    """SIGKILL after the ledger commit and before delivery acknowledgement."""
    ready = tmp_path / 'committed'
    script = tmp_path / 'settle.py'
    with connect(billing) as c:
        c.execute('CREATE TABLE settlement_calls(value INTEGER)')
        c.execute('INSERT INTO settlement_calls VALUES(0)')
    script.write_text('''import contextlib,sqlite3,sys,time
from pathlib import Path
from app import ai_billing,resource_accounts
@contextlib.contextmanager
def database():
 c=sqlite3.connect(sys.argv[1]);c.row_factory=sqlite3.Row
 try:
  yield c
  c.commit()
 except BaseException:
  c.rollback();raise
 finally:c.close()
def settle(c,job,values):
 c.execute('UPDATE resource_job_contracts SET settled=1 WHERE job_id=?',(job,))
 c.execute('UPDATE settlement_calls SET value=value+1')
ai_billing.db=database;ai_billing._init=lambda c:None
resource_accounts.prepare_upgrade=lambda c:None;resource_accounts.settle=settle
ai_billing.finish_job_idempotent('job','done',{'cpu_seconds':2},source='worker',worker_id='w1',claim_token='secret')
Path(sys.argv[2]).touch()
time.sleep(30)
''')
    root = Path(__file__).resolve().parents[1]
    proc = subprocess.Popen([sys.executable, str(script), str(billing), str(ready)], cwd=root,
                            env={**os.environ, 'PYTHONPATH': str(root)})
    try:
        deadline = time.monotonic() + 10
        while not ready.exists() and proc.poll() is None and time.monotonic() < deadline:
            threading.Event().wait(.01)
        assert ready.exists()
        proc.kill()
        proc.wait(timeout=5)
        assert proc.returncode != 0
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait(timeout=5)
    from app import resource_accounts
    monkeypatch.setattr(resource_accounts, 'settle', lambda *_: pytest.fail('Settlement replayed'))
    with connect(billing) as c:
        corrupt(c, 'current_revision')
    assert ai_billing.finish_job_idempotent('job', 'done', {'cpu_seconds': 2}, source='worker', **OWNER)['already_finalized']
    with connect(billing) as c:
        assert c.execute('SELECT value FROM settlement_calls').fetchone()[0] == 1
    assert state(billing) == ('done', 1, 'finished', 'closed')
