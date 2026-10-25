"""Read-only, fail-closed administrative review of unresolved checkout dispatches."""
from __future__ import annotations

import sqlite3

from .regime_operation_fence import FenceBlocked

_STATES = ('pending', 'uncertain', 'confirmed', 'cancelled')


def review(connection: sqlite3.Connection, *, limit: int = 100, offset: int = 0) -> dict:
    """Return unresolved dispatches without modifying a financial record.

    A confirmed provider order is not proof that funds settled; keep the
    originating checkout fence open until payment fulfillment is reconciled.
    """
    if type(limit) is not int or type(offset) is not int or not 1 <= limit <= 500 or not 0 <= offset <= 1_000_000:
        raise ValueError('Invalid outbox pagination')
    required = {'regime_payment_outbox', 'regime_fence_operations'}
    present = {r[0] for r in connection.execute("SELECT name FROM sqlite_master WHERE type='table' AND name IN ('regime_payment_outbox','regime_fence_operations')")}
    if present != required:
        raise FenceBlocked('Checkout or operation ledger missing')
    totals = dict(connection.execute('SELECT state, COUNT(*) FROM regime_payment_outbox GROUP BY state'))
    if set(totals) - set(_STATES):
        raise FenceBlocked('Unknown checkout outbox state')
    broken = connection.execute('''SELECT COUNT(*) FROM regime_payment_outbox o
        LEFT JOIN regime_fence_operations f ON f.operation_id=o.operation_id
        WHERE f.operation_id IS NULL OR f.kind!='checkout' OR f.regime!='COMMERCIAL'
           OR o.provider NOT IN ('stripe','paypal')''').fetchone()[0]
    rows = connection.execute('''SELECT o.operation_id,o.provider,o.state,o.attempts,
        o.provider_reference,f.status,f.regime,f.revision
        FROM regime_payment_outbox o
        LEFT JOIN regime_fence_operations f ON f.operation_id=o.operation_id
        WHERE o.state IN ('pending','uncertain','cancelled') OR f.status='open' OR f.operation_id IS NULL
        ORDER BY o.operation_id LIMIT ? OFFSET ?''', (limit,offset)).fetchall()
    unresolved_count = connection.execute('''SELECT COUNT(*) FROM regime_payment_outbox o
        LEFT JOIN regime_fence_operations f ON f.operation_id=o.operation_id
        WHERE o.state IN ('pending','uncertain','cancelled') OR f.status='open' OR f.operation_id IS NULL''').fetchone()[0]
    return {'ready_for_transition': False, 'unresolved_count': unresolved_count,
            'invalid_receipts': broken, 'state_counts': {s:totals.get(s,0) for s in _STATES},
            'items':[dict(zip(('operation_id','provider','state','attempts','provider_reference',
                               'fence_status','regime','revision'),tuple(r))) for r in rows],
            'limit':limit, 'offset':offset,
            'note':'Provider creation outcome does not establish financial settlement; transition remains disabled.'}


def audit_checkout_integrity(connection: sqlite3.Connection) -> dict:
    """Cross-check every commercial dispatch against its admission receipt.

    A consistent snapshot is not authorization for transition: unknown provider
    settlement and uninstrumented legacy records must still be reconciled.
    Never mutate financial records.
    """
    required = {'regime_payment_outbox', 'regime_fence_operations', 'regime_fence_state'}
    present = {r[0] for r in connection.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    )}
    if not required.issubset(present):
        raise FenceBlocked('Incomplete regime financial schema')
    problems = dict(connection.execute('''
       SELECT reason,COUNT(*) FROM (
        SELECT CASE
         WHEN f.operation_id IS NULL THEN 'missing_receipt'
         WHEN f.kind!='checkout' OR f.regime!='COMMERCIAL' THEN 'invalid_receipt'
         WHEN o.provider NOT IN ('stripe','paypal') THEN 'invalid_provider'
         WHEN o.state NOT IN ('pending','uncertain','confirmed','cancelled') THEN 'invalid_state'
         WHEN o.state='pending' AND o.attempts!=0 THEN 'pending_with_attempts'
         WHEN o.state IN ('uncertain','confirmed','cancelled') AND o.attempts<1 THEN 'dispatched_without_attempt'
         WHEN o.state='confirmed' AND (o.provider_reference IS NULL OR length(o.provider_reference)=0) THEN 'missing_provider_reference'
         WHEN o.state!='confirmed' AND o.provider_reference IS NOT NULL THEN 'unexpected_provider_reference'
         WHEN o.state IN ('pending','uncertain') AND f.status!='open' THEN 'unresolved_checkout_closed'
         ELSE NULL END AS reason FROM regime_payment_outbox o
         LEFT JOIN regime_fence_operations f ON f.operation_id=o.operation_id
       ) WHERE reason IS NOT NULL GROUP BY reason
    '''))
    # Historical records can predate uniqueness enforcement. Duplicate remote
    # checkout IDs never prove that both local economic obligations were paid.
    reused = connection.execute("""SELECT COALESCE(SUM(n - 1), 0) FROM (
        SELECT COUNT(*) AS n FROM regime_payment_outbox
        WHERE provider_reference IS NOT NULL
        GROUP BY provider, provider_reference HAVING COUNT(*) > 1
    )""").fetchone()[0]
    if reused:
        problems['reused_provider_reference'] = int(reused)
    outstanding = connection.execute('''SELECT COUNT(*) FROM regime_payment_outbox o
         LEFT JOIN regime_fence_operations f ON f.operation_id=o.operation_id
         WHERE o.state IN ('pending','uncertain','cancelled') OR f.status='open' OR f.operation_id IS NULL''').fetchone()[0]
    return {'verified': not bool(problems), 'inconsistencies': problems,
            'outstanding_dispatches': outstanding, 'transition_safe': False}
