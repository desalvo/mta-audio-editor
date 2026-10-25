"""Immutable provider observation journal, strictly separate from payment settlement.

The caller must obtain evidence directly from the authenticated provider adapter.
These records are untrusted for entitlements or transition approval: they provide
an auditable snapshot of a *matched observation*, not settlement certification.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3

from .regime_operation_fence import FenceBlocked

SCHEMA = '''CREATE TABLE IF NOT EXISTS regime_financial_evidence (
 evidence_id TEXT PRIMARY KEY,
 operation_id TEXT NOT NULL,
 provider TEXT NOT NULL CHECK(provider IN ('stripe','paypal')),
 provider_reference TEXT NOT NULL,
 digest TEXT NOT NULL,
 observed_json TEXT NOT NULL,
 created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
 FOREIGN KEY(operation_id) REFERENCES regime_payment_outbox(operation_id)
)'''


def record_observation(connection: sqlite3.Connection, operation_id: str, evidence: dict, *, evidence_id: str) -> dict:
    """Journal a matched provider observation in the caller's existing transaction.

    Never treats a caller-supplied dict as an authenticated settlement instruction.
    Remote probe, provider reversals, inbox and independent accounting checks must
    still be completed before any financial entitlement can be granted.
    """
    if not connection.in_transaction:
        raise FenceBlocked('Evidence journal requires caller transaction')
    if not isinstance(evidence_id, str) or not (1 <= len(evidence_id) <= 120):
        raise ValueError('Invalid evidence identifier')
    if not isinstance(evidence, dict) or evidence.get('provider') not in ('stripe', 'paypal'):
        raise FenceBlocked('Invalid provider observation')
    provider = evidence['provider']
    reference = evidence.get('reference')
    if not isinstance(reference, str) or not (1 <= len(reference) <= 200):
        raise FenceBlocked('Invalid provider reference')
    amount = evidence.get('amount_minor')
    currency = evidence.get('currency')
    if type(amount) is not int or amount < 0 or not isinstance(currency, str) or len(currency) != 3 or not currency.isalpha():
        raise FenceBlocked('Provider observation lacks amount or currency')
    if evidence.get('remote_payment_observed') is not True:
        raise FenceBlocked('Payment not independently observed')
    if evidence.get('local_ledger_reconciled') is not False or evidence.get('authorizes_entitlement') is not False or evidence.get('authorizes_cutover') is not False:
        raise FenceBlocked('Unsafe provider observation permissions')
    row = connection.execute('''SELECT provider,state,provider_reference FROM regime_payment_outbox
                                WHERE operation_id=?''', (operation_id,)).fetchone()
    if row is None or row[0] != provider or row[1] != 'confirmed' or row[2] != reference:
        raise FenceBlocked('Provider observation does not match confirmed outbox')
    receipt = connection.execute('''SELECT kind,regime FROM regime_fence_operations
                                   WHERE operation_id=?''', (operation_id,)).fetchone()
    if receipt is None or tuple(receipt) != ('checkout', 'COMMERCIAL'):
        raise FenceBlocked('Commercial checkout admission missing')
    payload = json.dumps(evidence, sort_keys=True, separators=(',', ':'), allow_nan=False)
    if len(payload) > 65536:
        raise FenceBlocked('Oversized provider observation')
    digest = hashlib.sha256(payload.encode()).hexdigest()
    connection.execute(SCHEMA)
    previous = connection.execute('SELECT operation_id,digest FROM regime_financial_evidence WHERE evidence_id=?',
                                  (evidence_id,)).fetchone()
    if previous:
        if tuple(previous) != (operation_id, digest):
            raise FenceBlocked('Conflicting observation replay')
        return {'evidence_id': evidence_id, 'created': False, 'ledger_reconciled': False}
    connection.execute('''INSERT INTO regime_financial_evidence
        (evidence_id,operation_id,provider,provider_reference,digest,observed_json)
        VALUES(?,?,?,?,?,?)''', (evidence_id, operation_id, provider, reference, digest, payload))
    return {'evidence_id': evidence_id, 'created': True, 'ledger_reconciled': False}


def audit_observations(connection: sqlite3.Connection) -> dict:
    """Read-only consistency audit; no observation can approve a regime switch."""
    tables = {r[0] for r in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if not {'regime_financial_evidence', 'regime_payment_outbox', 'regime_fence_operations'}.issubset(tables):
        return {'verified': False, 'inconsistencies': {'missing_schema': 1}, 'transition_safe': False}
    problems: dict[str, int] = {}
    for identifier, operation, provider, reference, digest, raw, matching_provider, state, matching_ref, kind, regime in connection.execute('''
        SELECT e.evidence_id,e.operation_id,e.provider,e.provider_reference,e.digest,e.observed_json,
               o.provider,o.state,o.provider_reference,f.kind,f.regime
        FROM regime_financial_evidence e
        LEFT JOIN regime_payment_outbox o ON e.operation_id=o.operation_id
        LEFT JOIN regime_fence_operations f ON e.operation_id=f.operation_id'''):
        reason = None
        if (provider, reference) != (matching_provider, matching_ref) or state != 'confirmed' or (kind, regime) != ('checkout', 'COMMERCIAL'):
            reason = 'orphan_or_mismatched'
        else:
            try:
                parsed = json.loads(raw)
                canonical = json.dumps(parsed, sort_keys=True, separators=(',', ':'), allow_nan=False)
                if hashlib.sha256(canonical.encode()).hexdigest() != digest or parsed.get('provider') != provider or parsed.get('reference') != reference:
                    reason = 'tampered'
                elif parsed.get('authorizes_entitlement') is not False or parsed.get('authorizes_cutover') is not False:
                    reason = 'unsafe_flags'
            except (ValueError, TypeError, AttributeError):
                reason = 'invalid_json'
        if reason:
            problems[reason] = problems.get(reason, 0) + 1
    return {'verified': not problems, 'inconsistencies': problems, 'transition_safe': False}
