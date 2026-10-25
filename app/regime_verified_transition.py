"""Read-only, database-derived authority for service-regime reservations.

No external caller-provided ``ready`` flag is accepted as financial clearance.
This module deliberately fails closed until all economic/worker entry points
are instrumented and provider settlements have been reconciled.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3

from .regime_operation_fence import FenceBlocked, inspect
from .regime_reconciliation import combined_readiness
from .regime_transition_journal import reserve


def verified_reservation(connection: sqlite3.Connection, *, transition_id: str,
                         target: str, expected_revision: int) -> dict:
    """Derive evidence from current DB in caller-owned BEGIN IMMEDIATE.

    The same write transaction is held through inventory, fence inspection and
    reservation: no writer can change these DB rows between the checks.
    A passing report must explicitly prove full instrumented entry coverage.
    """
    if not connection.in_transaction:
        raise FenceBlocked('BEGIN IMMEDIATE is required')
    state = inspect(connection)
    if state['revision'] != expected_revision or state['transitioning']:
        raise FenceBlocked('Regime revision conflict or active transition')
    report = combined_readiness(connection, current=state['regime'], target=target)
    if (report.get('unresolved') or
            report.get('ready_for_automatic_transition') is not True or
            report.get('fence', {}).get('all_entry_points_instrumented') is not True or
            report.get('metered_job_coverage', {}).get('verified') is not True or
            report.get('checkout_integrity', {}).get('verified') is not True or
            report.get('checkout_integrity', {}).get('transition_safe') is not True):
        raise FenceBlocked('Verified financial and worker reconciliation is incomplete')
    snapshot = json.dumps(report, sort_keys=True, separators=(',', ':'), allow_nan=False)
    evidence = {'ready': True, 'unresolved': [],
                'source': 'database-transactional-audit',
                'snapshot_sha256': hashlib.sha256(snapshot.encode()).hexdigest()}
    return reserve(connection, transition_id=transition_id, target=target,
                   expected_revision=expected_revision, evidence=evidence)
