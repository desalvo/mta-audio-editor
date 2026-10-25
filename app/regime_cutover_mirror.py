"""Fail-closed recovery of the external regime mirror after a SQLite cutover.

Never opens the operation fence: activating a new regime also requires a
separate, audited certification of all billing and worker entry points.
"""
from __future__ import annotations

import json
import os
import sqlite3
import tempfile
from pathlib import Path

from .regime_operation_fence import FenceBlocked
from .service_regime import Regime, RegimeState, read_regime


def inspect_mirror(connection: sqlite3.Connection, path: Path, transition_id: str) -> dict:
    """Compare committed database receipt against external JSON, without mutation."""
    row = connection.execute(
        'SELECT source,target,previous_revision,new_revision FROM regime_cutover_commits WHERE transition_id=?',
        (transition_id,)).fetchone()
    state = connection.execute('SELECT regime,revision,transitioning FROM regime_fence_state WHERE singleton=1').fetchone()
    if row is None or state is None or (state[0], state[1], state[2]) != (row[1], row[3], 1):
        raise FenceBlocked('Cutover receipt or held barrier inconsistent')
    existing = read_regime(path)
    original = (row[0], row[2])
    expected = (row[1], row[3])
    current = (existing.regime.value, existing.revision)
    if current not in (original, expected):
        raise FenceBlocked('External mirror has an unexpected epoch')
    return {'transition_id': transition_id, 'from': original[0], 'to': expected[0],
            'revision': expected[1], 'mirror_matches': current == expected,
            'barrier_held': True, 'activation_permitted': False}


def reconcile_mirror(connection: sqlite3.Connection, path: Path, transition_id: str) -> dict:
    """Atomically replace only a matching old mirror; never clear the barrier.

    The caller must hold an exclusive maintenance lock across app processes;
    this function must not be used while workers serve requests. SQLite cannot
    atomically commit a separate filesystem write. Recovery is idempotent.
    """
    if not connection.in_transaction:
        raise FenceBlocked('BEGIN IMMEDIATE maintenance transaction required')
    path = Path(path)
    result = inspect_mirror(connection, path, transition_id)
    if result['mirror_matches']:
        return result
    if path.is_symlink() or not path.is_file():
        raise FenceBlocked('Expected original regime mirror file missing or unsafe')
    parent = path.parent
    temporary = None
    try:
        fd, temporary = tempfile.mkstemp(prefix='.regime-recovery-', dir=parent)
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            os.fchmod(stream.fileno(), 0o600)
            json.dump(RegimeState(Regime(result['to']), result['revision']).as_dict(), stream, sort_keys=True)
            stream.flush()
            os.fsync(stream.fileno())
        # Recheck the source immediately before replacement (the maintenance
        # lock must protect this check across processes).
        inspect_mirror(connection, path, transition_id)
        os.replace(temporary, path)
        temporary = None
        dirfd = os.open(parent, os.O_RDONLY | getattr(os, 'O_DIRECTORY', 0))
        try:
            os.fsync(dirfd)
        finally:
            os.close(dirfd)
    finally:
        if temporary is not None:
            os.unlink(temporary)
    result = inspect_mirror(connection, path, transition_id)
    if not result['mirror_matches']:
        raise FenceBlocked('Mirror reconciliation verification failed')
    return result
