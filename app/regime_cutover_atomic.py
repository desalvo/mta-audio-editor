"""Database-local cutover primitive; not a production switch endpoint.

The service also persists its effective mode outside SQLite. That mirror, legacy
payment liabilities and unfenced workers must be reconciled before enabling a
production cutover. This module intentionally never writes the external file.
"""
from __future__ import annotations

import sqlite3
from typing import Callable

from .regime_operation_fence import FenceBlocked


def commit_reserved_database_cutover(
    connection: sqlite3.Connection, *, transition_id: str,
    expected_revision: int, readiness_check: Callable[[sqlite3.Connection], bool],
) -> dict:
    """Commit the *SQLite half* of a prepared cutover in a caller-owned transaction.

    readiness_check must be a trusted internal callback reading this same DB;
    passing an HTTP-supplied readiness value is forbidden. The database retains
    the 'transitioning' barrier until the external mirror can be reconciled.
    """
    if not connection.in_transaction:
        raise FenceBlocked('BEGIN IMMEDIATE required for cutover')
    if type(expected_revision) is not int or expected_revision < 0:
        raise ValueError('Invalid expected revision')
    if not isinstance(transition_id, str) or not transition_id:
        raise ValueError('Invalid transition id')
    if not callable(readiness_check):
        raise ValueError('Internal readiness callback required')
    row = connection.execute(
        'SELECT source_regime,target_regime,source_revision,status '
        'FROM regime_transition_journal WHERE id=?', (transition_id,)
    ).fetchone()
    state = connection.execute(
        'SELECT regime,revision,transitioning FROM regime_fence_state WHERE singleton=1'
    ).fetchone()
    if not row or not state or row[3] != 'reserved':
        raise FenceBlocked('No matching reserved transition')
    source, target, revision, _ = row
    if (source, revision, 1) != (state[0], state[1], state[2]) or revision != expected_revision:
        raise FenceBlocked('Stale or inconsistent transition reservation')
    if source == target or target not in {'NON_COMMERCIAL', 'COMMERCIAL'}:
        raise FenceBlocked('Invalid transition target')
    if connection.execute(
        "SELECT COUNT(*) FROM regime_fence_operations WHERE status='open'"
    ).fetchone()[0]:
        raise FenceBlocked('Unsettled operations block cutover')
    if readiness_check(connection) is not True:
        raise FenceBlocked('Authoritative reconciliation is not ready')
    # Deliberately leave transitioning=1: uninstrumented clients and the
    # external JSON regime mirror cannot safely observe the new epoch yet.
    connection.execute(
        'UPDATE regime_fence_state SET regime=?,revision=? WHERE singleton=1',
        (target, revision + 1),
    )
    connection.execute("""CREATE TABLE IF NOT EXISTS regime_cutover_commits (
        transition_id TEXT PRIMARY KEY, source TEXT NOT NULL, target TEXT NOT NULL,
        previous_revision INTEGER NOT NULL, new_revision INTEGER NOT NULL
    )""")
    connection.execute(
        "INSERT INTO regime_cutover_commits VALUES (?,?,?,?,?)",
        (transition_id, source, target, revision, revision + 1),
    )
    return {'from': source, 'to': target, 'revision': revision + 1,
            'barrier_held': True, 'requires_external_recovery': True}
