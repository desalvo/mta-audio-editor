"""Crash-safe journal for administrative regime cutover preparation.

This is deliberately NOT a regime switching API. Preparing a cutover must not
alter the effective service regime or authorize commercial billing. External
payment and worker entry points must be fully fenced before activation.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3

from .regime_operation_fence import FenceBlocked, begin_transition, abort_transition

_SCHEMA = '''CREATE TABLE IF NOT EXISTS regime_transition_journal (
 id TEXT PRIMARY KEY,
 source_regime TEXT NOT NULL,
 target_regime TEXT NOT NULL,
 source_revision INTEGER NOT NULL,
 evidence_sha256 TEXT NOT NULL,
 status TEXT NOT NULL CHECK(status IN ('reserved','aborted'))
)'''


def _transaction(connection):
    if not connection.in_transaction:
        raise FenceBlocked('BEGIN IMMEDIATE required for transition journal')


def _digest(evidence):
    if not isinstance(evidence, dict):
        raise ValueError('Structured reconciliation evidence required')
    canonical = json.dumps(evidence, sort_keys=True, separators=(',', ':'), allow_nan=False)
    if len(canonical) > 1024 * 1024:
        raise ValueError('Evidence too large')
    return hashlib.sha256(canonical.encode('utf-8')).hexdigest()


def reserve(connection: sqlite3.Connection, *, transition_id: str, target: str,
            expected_revision: int, evidence: dict) -> dict:
    """Durably record a cutover reservation; never changes the active regime.

    The operator MUST independently validate all evidence. We also require an
    explicit machine-checkable ``ready`` flag and no unresolved items, though
    these checks do not replace provider-side authenticated reconciliation.
    """
    _transaction(connection)
    if not isinstance(transition_id, str) or not (1 <= len(transition_id) <= 120):
        raise ValueError('Invalid transition identifier')
    if evidence.get('ready') is not True or evidence.get('unresolved') != []:
        raise FenceBlocked('Reconciliation evidence does not authorize reservation')
    digest = _digest(evidence)
    connection.execute(_SCHEMA)
    previous = connection.execute('SELECT source_regime,target_regime,source_revision,evidence_sha256,status FROM regime_transition_journal WHERE id=?', (transition_id,)).fetchone()
    if previous:
        if previous[1:] != (target, expected_revision, digest, 'reserved'):
            raise FenceBlocked('Transition identifier replay conflict')
        # Never accept a journal-only replay if the durable operation barrier
        # has been rolled back, reset or changed outside this reservation.
        status = inspect_reservations(connection)
        if (not status['integrity_verified'] or not status['transitioning'] or
                status['revision'] != expected_revision or
                len(status['reservations']) != 1 or
                status['reservations'][0]['id'] != transition_id):
            raise FenceBlocked('Transition replay is inconsistent with durable fence')
        return {'transition_id': transition_id, 'reserved': True, 'idempotent': True}
    ticket = begin_transition(connection, expected_revision=expected_revision, target=target)
    connection.execute('INSERT INTO regime_transition_journal VALUES (?,?,?,?,?,?)',
                       (transition_id, ticket['from'], target, expected_revision, digest, 'reserved'))
    return {'transition_id': transition_id, 'reserved': True, 'idempotent': False}


def abort(connection: sqlite3.Connection, *, transition_id: str) -> None:
    _transaction(connection)
    row = connection.execute('SELECT status FROM regime_transition_journal WHERE id=?', (transition_id,)).fetchone()
    if not row:
        raise FenceBlocked('Unknown transition')
    if row[0] == 'aborted':
        return
    if connection.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='regime_cutover_commits'").fetchone():
        if connection.execute('SELECT 1 FROM regime_cutover_commits WHERE transition_id=?',
                              (transition_id,)).fetchone():
            raise FenceBlocked('Committed cutover requires forward recovery, not abort')
    abort_transition(connection)
    connection.execute("UPDATE regime_transition_journal SET status='aborted' WHERE id=?", (transition_id,))


def pending(connection: sqlite3.Connection) -> list[dict]:
    try:
        finalized = connection.execute("SELECT 1 FROM sqlite_master WHERE name='regime_cutover_finalizations'").fetchone()
        if finalized:
            rows = connection.execute("""SELECT id,source_regime,target_regime,source_revision,evidence_sha256
                FROM regime_transition_journal WHERE status='reserved' AND NOT EXISTS
                (SELECT 1 FROM regime_cutover_finalizations f WHERE f.transition_id=regime_transition_journal.id)""").fetchall()
        else:
            rows = connection.execute("SELECT id,source_regime,target_regime,source_revision,evidence_sha256 FROM regime_transition_journal WHERE status='reserved'").fetchall()
    except sqlite3.OperationalError:
        return []
    return [dict(id=r[0], source=r[1], target=r[2], revision=r[3], evidence_sha256=r[4]) for r in rows]


def inspect_reservations(connection: sqlite3.Connection) -> dict:
    """Read-only administrator recovery view, without exposing reconciliation contents."""
    from .regime_operation_fence import inspect
    state = inspect(connection)
    reservations = pending(connection)
    inconsistent = (bool(reservations) != state['transitioning'] or len(reservations) > 1 or
                    any(item['source'] != state['regime'] or item['revision'] != state['revision']
                        for item in reservations))
    return {'regime': state['regime'], 'revision': state['revision'],
            'transitioning': state['transitioning'], 'reservations': reservations,
            'integrity_verified': not inconsistent, 'requires_operator_review': inconsistent}


def abort_verified(connection: sqlite3.Connection, *, transition_id: str,
                   expected_revision: int) -> dict:
    """Abort one exactly matching pending reservation in the caller's transaction."""
    _transaction(connection)
    if type(expected_revision) is not int or expected_revision < 0:
        raise ValueError('Invalid expected revision')
    status = inspect_reservations(connection)
    if not status['integrity_verified'] or not status['transitioning'] or status['revision'] != expected_revision:
        raise FenceBlocked('Transition reservation or revision inconsistent')
    if len(status['reservations']) != 1 or status['reservations'][0]['id'] != transition_id:
        raise FenceBlocked('Transition reservation identity mismatch')
    # A completed SQLite cutover changes the accounting epoch. Aborting its
    # reservation would reopen the barrier against a stale external mirror.
    # Never treat an already-committed cutover as an abortable reservation.
    if connection.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='regime_cutover_commits'").fetchone():
        if connection.execute('SELECT 1 FROM regime_cutover_commits WHERE transition_id=?',
                              (transition_id,)).fetchone():
            raise FenceBlocked('Committed cutover requires forward recovery, not abort')
    abort(connection, transition_id=transition_id)
    result = inspect_reservations(connection)
    if not result['integrity_verified'] or result['transitioning']:
        raise FenceBlocked('Transition reservation could not be safely cleared')
    return {'aborted': True, 'transition_id': transition_id,
            'regime': result['regime'], 'revision': result['revision']}
