"""Validate the original commercial checkout admission before external reconciliation.

A provider outcome can be recorded only against a still-open checkout admitted
under the original commercial epoch. This check never settles financial entries.
"""
from __future__ import annotations
import sqlite3
from .regime_operation_fence import FenceBlocked


def require_open_commercial_checkout(connection: sqlite3.Connection, operation_id: str) -> None:
    if not connection.in_transaction:
        raise FenceBlocked('Checkout reconciliation requires transaction')
    row = connection.execute('''SELECT f.kind, f.regime, f.revision, f.status,
                                      s.regime, s.revision, s.transitioning
                               FROM regime_fence_operations f
                               CROSS JOIN regime_fence_state s
                               WHERE f.operation_id=? AND s.singleton=1''',
                             (operation_id,)).fetchone()
    if row is None or tuple(row[:2]) != ('checkout', 'COMMERCIAL') or row[3] != 'open':
        raise FenceBlocked('Open commercial checkout admission is required')
    # Stale events are not silently attached to the newly selected regime.
    # During a reserved transition, all reconciliations are deferred.
    if row[6]:
        raise FenceBlocked('Service regime transition in progress')
    if (row[1], row[2]) != (row[4], row[5]):
        raise FenceBlocked('Checkout receipt belongs to a different regime epoch')
