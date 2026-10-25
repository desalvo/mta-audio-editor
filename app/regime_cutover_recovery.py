"""Maintenance-only recovery of a committed service-regime cutover.

The entry point deliberately cannot release the admission fence.  External
payment and worker reconciliation is a separate mandatory certification gate.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

from .regime_cutover_mirror import inspect_mirror, reconcile_mirror
from .regime_operation_fence import FenceBlocked


def recover_committed_mirror(connection: sqlite3.Connection, *, mirror_path: Path,
                             transition_id: str) -> dict:
    """Recover a committed SQLite epoch's JSON mirror, never release its fence.

    Requires a caller-owned BEGIN IMMEDIATE and an exclusive, *cross-process*
    maintenance lock covering the whole application. No provider calls occur.
    The caller commits the DB only after this method returns successfully.
    """
    if not connection.in_transaction:
        raise FenceBlocked('BEGIN IMMEDIATE maintenance transaction required')
    before = inspect_mirror(connection, mirror_path, transition_id)
    if not before['barrier_held']:
        raise FenceBlocked('Cutover fence is not held')
    if connection.execute("SELECT COUNT(*) FROM regime_fence_operations WHERE status='open'").fetchone()[0]:
        raise FenceBlocked('Open operations require reconciliation before mirror recovery')
    after = reconcile_mirror(connection, mirror_path, transition_id)
    if not after['mirror_matches'] or not after['barrier_held']:
        raise FenceBlocked('Mirror recovery did not preserve the admission fence')
    return {'transition_id': transition_id, 'mirror_matches': True,
            'barrier_held': True, 'activation_permitted': False,
            'revision': after['revision'], 'regime': after['to']}
