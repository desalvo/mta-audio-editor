"""Atomic, fail-closed completion of a previously claimed, metered AI job.

Does not infer billing from worker success: callers must durably finalize their
ledger and accounting before entering this operation. No network calls here.
"""
from __future__ import annotations

import sqlite3

from .regime_operation_fence import FenceBlocked, settle
from .regime_worker_claims import finish, _identity, verify_owner

_TERMINAL = frozenset({'done', 'completed', 'success', 'succeeded', 'failed', 'cancelled', 'canceled', 'refunded'})


def complete_claimed_job(connection: sqlite3.Connection, *, ledger_id: str,
                         worker_id: str, token: str) -> dict:
    """Own BEGIN IMMEDIATE, verify terminal ledger and settled billing, finish and fence.

    A retry with the same receipt is idempotent. Never settle billing itself:
    the accounting code must do that with its own verified evidence first.
    """
    if connection.in_transaction:
        raise FenceBlocked('Completion must own the SQLite transaction')
    _identity(worker_id, token)
    if not isinstance(ledger_id, str) or not 1 <= len(ledger_id) <= 140:
        raise ValueError('Invalid ledger ID')
    operation_id = 'job:ledger:' + ledger_id
    connection.execute('BEGIN IMMEDIATE')
    try:
        verify_owner(connection, operation_id, worker_id=worker_id, token=token, allow_finished=True)
        row = connection.execute('''SELECT c.worker_id,c.claim_token,c.state,f.kind,f.status,
                    f.regime,f.revision,j.status,j.billable,
                    s.regime,s.revision,s.transitioning
                  FROM regime_worker_claims c
                  JOIN regime_fence_operations f ON f.operation_id=c.operation_id
                  JOIN ai_compute_jobs j ON j.id=?
                  JOIN regime_fence_state s ON s.singleton=1
                  WHERE c.operation_id=?''', (ledger_id, operation_id)).fetchone()
        if row is None or tuple(row[0:2]) != (worker_id, token) or row[3] != 'job':
            raise FenceBlocked('Missing claim, wrong owner or changed regime epoch')
        if row[7] not in _TERMINAL:
            raise FenceBlocked('Cannot settle an unfinished ledger job')
        from .job_settlement_contract import verify_settled
        verify_settled(connection,ledger_id,billable=row[8])
        from .worker_cgroup_recovery import require_quiescent
        require_quiescent(connection, ledger_id)
        if row[2] == 'finished' and row[4] == 'closed':
            connection.commit()
            return {'completed': False, 'operation_id': operation_id}
        if row[2] != 'running' or row[4] != 'open':
            raise FenceBlocked('Partial or inconsistent worker finalization')
        finish(connection, operation_id, worker_id=worker_id, token=token)
        settle(connection, operation_id)
        connection.commit()
        return {'completed': True, 'operation_id': operation_id}
    except BaseException:
        if connection.in_transaction:
            connection.rollback()
        raise
