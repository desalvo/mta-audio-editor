"""Read-only, deterministic regime-transition plan. No financial mutation.

A plan is *never* an authorization to switch regimes. It is a tamper-evident
snapshot to assist manual reconciliation and downstream integration tests.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path

from .regime_reconciliation import readiness_report
from .service_regime import Regime, read_regime
from .noncommercial_statements import list_statements


def _canonical(obj: dict) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode('utf-8')


def build_plan(connection: sqlite3.Connection, *, target: str, config_path: Path) -> dict:
    state = read_regime(config_path)
    destination = Regime(target)
    connection.execute('SAVEPOINT regime_readonly_plan')
    try:
        audit = readiness_report(connection, current=state.regime.value, target=destination.value)
        statements = list_statements(connection)
        # Do not claim automatic readiness even if inventory is empty: webhooks and
        # workers are external to the SQLite snapshot and need a shared fence.
        snapshot = {
            'schema_version': 1,
            'from': state.regime.value,
            'to': destination.value,
            'revision': state.revision,
            'inventory': audit['inventory'],
            'unresolved': audit['unresolved'],
            'statement_hashes': [x['sha256'] for x in statements],
            'requires_shared_job_payment_webhook_fence': True,
            'requires_manual_settlement_review': True,
            'ready_for_transition': False,
            'mutates_accounting': False,
            'mutates_billing': False,
        }
        return {**snapshot, 'sha256': hashlib.sha256(_canonical(snapshot)).hexdigest()}
    finally:
        connection.execute('ROLLBACK TO SAVEPOINT regime_readonly_plan')
        connection.execute('RELEASE SAVEPOINT regime_readonly_plan')


def verify_plan(plan: dict) -> bool:
    if not isinstance(plan, dict) or 'sha256' not in plan:
        return False
    digest = plan['sha256']
    if not isinstance(digest, str) or len(digest) != 64:
        return False
    body = {key: value for key, value in plan.items() if key != 'sha256'}
    return hashlib.sha256(_canonical(body)).hexdigest() == digest and body.get('ready_for_transition') is False
