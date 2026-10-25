"""Durable cross-process execution claims for previously fenced AI ledger jobs.

Every claim, heartbeat and release must be done inside the caller's SQLite
BEGIN IMMEDIATE transaction. Claims have no time-based automatic takeover:
a lost worker requires explicit audited recovery after external quiescence.
The module deliberately does not certify queue-wide worker integration.
"""
from __future__ import annotations

import sqlite3

from .regime_operation_fence import FenceBlocked

_SCHEMA = '''CREATE TABLE IF NOT EXISTS regime_worker_claims (
    operation_id TEXT PRIMARY KEY,
    worker_id TEXT NOT NULL,
    claim_token TEXT NOT NULL,
    regime TEXT NOT NULL,
    revision INTEGER NOT NULL,
    state TEXT NOT NULL CHECK(state IN ('running','finished')),
    heartbeat_count INTEGER NOT NULL DEFAULT 0 CHECK(heartbeat_count >= 0),
    FOREIGN KEY(operation_id) REFERENCES regime_fence_operations(operation_id)
)'''


def _txn(connection: sqlite3.Connection) -> None:
    if not connection.in_transaction:
        raise FenceBlocked('Worker claim requires owning database write transaction')


def _identity(worker_id: str, token: str) -> None:
    if not all(isinstance(x, str) and 1 <= len(x) <= 160 and not x.isspace()
               for x in (worker_id, token)):
        raise ValueError('Invalid worker identity or claim token')


def claim(connection: sqlite3.Connection, ledger_id: str, *, worker_id: str, token: str) -> dict:
    """Grant one durable worker ownership to an already admitted ledger job."""
    _txn(connection)
    _identity(worker_id, token)
    if not isinstance(ledger_id, str) or not 1 <= len(ledger_id) <= 140:
        raise ValueError('Invalid ledger ID')
    operation_id = f'job:ledger:{ledger_id}'
    row = connection.execute('''SELECT f.kind,f.regime,f.revision,f.status,
               s.regime,s.revision,s.transitioning
               FROM regime_fence_operations f CROSS JOIN regime_fence_state s
               WHERE f.operation_id=? AND s.singleton=1''', (operation_id,)).fetchone()
    if (row is None or row[0] != 'job' or row[3] != 'open' or row[6] or
            (row[1],row[2]) != (row[4],row[5])):
        raise FenceBlocked('Job not admitted in the current open regime epoch')
    connection.execute(_SCHEMA)
    old = connection.execute('SELECT worker_id,claim_token,state FROM regime_worker_claims WHERE operation_id=?',
                             (operation_id,)).fetchone()
    if old:
        if tuple(old) != (worker_id,token,'running'):
            raise FenceBlocked('Job already claimed or previously completed; no automatic takeover')
        verify_owner(connection, operation_id, worker_id=worker_id, token=token)
        return {'operation_id': operation_id, 'claimed': False}
    connection.execute('''INSERT INTO regime_worker_claims
        (operation_id,worker_id,claim_token,regime,revision,state)
        VALUES(?,?,?,?,?,'running')''', (operation_id,worker_id,token,row[1],row[2]))
    return {'operation_id': operation_id, 'claimed': True}


def verify_owner(connection: sqlite3.Connection, operation_id: str, *, worker_id: str,
                 token: str, allow_finished: bool = False) -> dict:
    """Check the original receipt and active epoch without mutating state.

    Running claims and released-but-unsettled claims require the current open
    epoch. An exactly matching finished/closed receipt may be read after an
    epoch change; it grants no right to launch, heartbeat or settle new work.
    Callers still verify terminal ledger/accounting and physical quiescence.
    Mutations must hold their caller-owned write transaction around this check.
    """
    _identity(worker_id, token)
    row = connection.execute('''SELECT c.worker_id,c.claim_token,c.state,c.regime,c.revision,
        f.kind,f.regime,f.revision,f.status,s.regime,s.revision,s.transitioning
        FROM regime_worker_claims c
        JOIN regime_fence_operations f ON f.operation_id=c.operation_id
        CROSS JOIN regime_fence_state s
        WHERE c.operation_id=? AND s.singleton=1''', (operation_id,)).fetchone()
    if (row is None or tuple(row[:2]) != (worker_id, token) or row[5] != 'job'
            or tuple(row[3:5]) != tuple(row[6:8])):
        raise FenceBlocked('Worker ownership receipt is missing or not consistently bound')
    if row[2] == 'finished' and row[8] == 'closed' and allow_finished:
        return {'state': row[2], 'fence_status': row[8], 'historical': True}
    if (row[8] != 'open' or row[11] or tuple(row[3:5]) != tuple(row[9:11])
            or row[2] not in (('running', 'finished') if allow_finished else ('running',))):
        raise FenceBlocked('Worker ownership is no longer active in the current regime epoch')
    return {'state': row[2], 'fence_status': row[8], 'historical': False}


def heartbeat(connection: sqlite3.Connection, operation_id: str, *, worker_id: str, token: str) -> None:
    _txn(connection)
    verify_owner(connection, operation_id, worker_id=worker_id, token=token)
    updated = connection.execute('''UPDATE regime_worker_claims SET heartbeat_count=heartbeat_count+1
        WHERE operation_id=? AND worker_id=? AND claim_token=? AND state='running'
        AND EXISTS (SELECT 1 FROM regime_fence_operations f WHERE f.operation_id=? AND f.status='open')''',
        (operation_id,worker_id,token,operation_id)).rowcount
    if updated != 1:
        raise FenceBlocked('Worker ownership lost or job already settled')


def finish(connection: sqlite3.Connection, operation_id: str, *, worker_id: str, token: str) -> None:
    """Finish worker ownership; ledger metering/fence settlement remains caller-owned."""
    _txn(connection)
    verify_owner(connection, operation_id, worker_id=worker_id, token=token, allow_finished=True)
    if operation_id.startswith('job:ledger:'):
        from .worker_cgroup_recovery import require_quiescent
        require_quiescent(connection,operation_id[len('job:ledger:'):])
    changed = connection.execute('''UPDATE regime_worker_claims SET state='finished'
        WHERE operation_id=? AND worker_id=? AND claim_token=? AND state='running' ''',
        (operation_id,worker_id,token)).rowcount
    if not changed:
        row = connection.execute('SELECT worker_id,claim_token,state FROM regime_worker_claims WHERE operation_id=?',
                                 (operation_id,)).fetchone()
        if row is None or tuple(row) != (worker_id,token,'finished'):
            raise FenceBlocked('Cannot release worker claim owned by another worker')


def inspect_claims(connection: sqlite3.Connection) -> dict:
    """Read-only transition blocker; unknown schema cannot be treated as zero."""
    try:
        rows = connection.execute('''SELECT state,COUNT(*) FROM regime_worker_claims GROUP BY state''').fetchall()
    except sqlite3.DatabaseError:
        return {'verified': False, 'running': None, 'finished': None}
    counts = dict(rows)
    return {'verified': True, 'running': counts.get('running',0), 'finished': counts.get('finished',0)}


def audit_claim_integrity(connection: sqlite3.Connection) -> dict:
    """Cross-check durable claims against their original fence and ledger.

    A completed claim is historical evidence, not by itself proof that a job
    settled. Missing schema or mismatched epochs always blocks cutover.
    """
    # Inspect schema, current epoch and claims from one SQLite snapshot. Do not
    # end a caller's transaction, including on a failed integrity inspection.
    owned = not connection.in_transaction
    try:
        if owned:
            connection.execute('SAVEPOINT mta_claim_integrity_read')
        return _audit_claim_integrity(connection)
    except sqlite3.DatabaseError:
        return {'verified': False, 'issues': {'audit_failed': 1}, 'safe': False}
    finally:
        if owned and connection.in_transaction:
            connection.execute('RELEASE SAVEPOINT mta_claim_integrity_read')


def _audit_claim_integrity(connection: sqlite3.Connection) -> dict:
    try:
        known = {r[0] for r in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
        required = {'regime_worker_claims', 'regime_fence_operations', 'regime_fence_state', 'ai_compute_jobs'}
        if not required.issubset(known):
            return {'verified': False, 'issues': {'schema_unavailable': 1}, 'safe': False}
        current = connection.execute(
            'SELECT regime,revision,transitioning FROM regime_fence_state WHERE singleton=1').fetchone()
        if current is None:
            return {'verified': False, 'issues': {'epoch_unavailable': 1}, 'safe': False}
        rows = connection.execute(
            """SELECT c.operation_id,c.regime,c.revision,c.state,
                      f.kind,f.regime,f.revision,f.status,j.status
               FROM regime_worker_claims c
               LEFT JOIN regime_fence_operations f ON f.operation_id=c.operation_id
               LEFT JOIN ai_compute_jobs j ON ('job:ledger:' || j.id)=c.operation_id"""
        ).fetchall()
        issues = {}
        for op, regime, rev, state, kind, f_regime, f_rev, f_status, job_status in rows:
            reason = None
            if kind != 'job' or (regime, rev) != (f_regime, f_rev):
                reason = 'claim_receipt_mismatch'
            elif job_status is None:
                reason = 'orphaned_ledger_job'
            elif state == 'running' and f_status != 'open':
                reason = 'running_claim_closed_fence'
            elif state == 'running' and (regime, rev) != tuple(current[:2]):
                reason = 'running_claim_stale_epoch'
            elif state == 'running' and current[2]:
                reason = 'running_claim_transition_barrier'
            elif state == 'running' and job_status != 'running':
                reason = 'terminal_ledger_running_claim'
            elif state == 'finished' and f_status == 'open':
                reason = 'finished_claim_open_fence'
            elif state == 'finished' and job_status == 'running' and f_status == 'closed':
                reason = 'unfinished_ledger_closed_fence'
            elif state not in ('running', 'finished'):
                reason = 'unknown_claim_state'
            if reason:
                issues[reason] = issues.get(reason, 0) + 1
        return {'verified': True, 'issues': issues, 'safe': not bool(issues),
                'claims_checked': len(rows)}
    except sqlite3.DatabaseError:
        return {'verified': False, 'issues': {'audit_failed': 1}, 'safe': False}
