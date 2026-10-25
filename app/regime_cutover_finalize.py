"""Internal fail-closed finalization for a committed and mirrored regime cutover.

Never invoke directly from an HTTP request. The caller must hold an exclusive
cross-process maintenance lock and supply an authoritative readiness callback
checking *all* queue, ledger, provider and webhook entry points in this DB.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Callable

from .regime_cutover_mirror import inspect_mirror
from .regime_operation_fence import FenceBlocked


def finalize_cutover(connection: sqlite3.Connection, *, mirror_path: Path,
                     transition_id: str, readiness_check: Callable[[sqlite3.Connection], bool]) -> dict:
    """Atomically release fence after explicit cross-system authorization.

    A mirror check alone must NEVER enable production. This primitive retains
    the fence if any check fails or the SQLite transaction rolls back.
    """
    if not connection.in_transaction:
        raise FenceBlocked('BEGIN IMMEDIATE maintenance transaction required')
    if not callable(readiness_check):
        raise ValueError('Authoritative readiness callback required')
    state = inspect_mirror(connection, mirror_path, transition_id)
    if not state['mirror_matches'] or not state['barrier_held']:
        raise FenceBlocked('External regime mirror not synchronized')
    if connection.execute("SELECT COUNT(*) FROM regime_fence_operations WHERE status='open'").fetchone()[0]:
        raise FenceBlocked('Unsettled operations prevent fence release')
    if readiness_check(connection) is not True:
        raise FenceBlocked('Complete provider and worker reconciliation not certified')
    updated = connection.execute(
        'UPDATE regime_fence_state SET transitioning=0 WHERE singleton=1 AND transitioning=1 AND regime=? AND revision=?',
        (state['to'], state['revision']),
    ).rowcount
    if updated != 1:
        raise FenceBlocked('Cutover epoch changed during finalization')
    connection.execute('''CREATE TABLE IF NOT EXISTS regime_cutover_finalizations (
        transition_id TEXT PRIMARY KEY, regime TEXT NOT NULL, revision INTEGER NOT NULL)''')
    connection.execute('INSERT INTO regime_cutover_finalizations VALUES(?,?,?)',
                       (transition_id, state['to'], state['revision']))
    return {'transition_id': transition_id, 'regime': state['to'],
            'revision': state['revision'], 'barrier_held': False}
