"""Durable, conservative dispatch ledger for commercial checkout requests.

This records local intent; it never performs provider network calls. A timed-out
provider request remains uncertain until reconciliation with that provider.
"""
from __future__ import annotations

import sqlite3

from .regime_operation_fence import FenceBlocked

SCHEMA = '''
CREATE TABLE IF NOT EXISTS regime_payment_outbox (
 operation_id TEXT PRIMARY KEY,
 provider TEXT NOT NULL CHECK(provider IN ('stripe','paypal')),
 request_key TEXT NOT NULL UNIQUE,
 state TEXT NOT NULL CHECK(state IN ('pending','uncertain','confirmed','cancelled')),
 attempts INTEGER NOT NULL DEFAULT 0 CHECK(attempts>=0),
 provider_reference TEXT,
 FOREIGN KEY(operation_id) REFERENCES regime_fence_operations(operation_id)
)
'''


def enqueue(connection: sqlite3.Connection, *, provider: str, order_id: str, request_key: str) -> dict:
    """Enroll dispatch intent in the caller-owned checkout creation transaction."""
    if not connection.in_transaction:
        raise FenceBlocked('Outbox enrollment requires checkout transaction')
    if provider not in ('stripe', 'paypal') or not isinstance(order_id, str) or not order_id or len(order_id) > 120:
        raise ValueError('Invalid checkout order')
    if not isinstance(request_key, str) or not (1 <= len(request_key) <= 160):
        raise ValueError('Invalid idempotency key')
    op_id = f'checkout:{provider}:{order_id}'
    receipt = connection.execute('''SELECT kind,regime,status FROM regime_fence_operations
                                  WHERE operation_id=?''', (op_id,)).fetchone()
    if receipt is None or tuple(receipt) != ('checkout', 'COMMERCIAL', 'open'):
        raise FenceBlocked('Commercial checkout admission required before dispatch')
    connection.execute(SCHEMA)
    old = connection.execute('SELECT provider,request_key,state FROM regime_payment_outbox WHERE operation_id=?', (op_id,)).fetchone()
    if old:
        if old[:2] != (provider,request_key):
            raise FenceBlocked('Checkout outbox identity conflict')
        return {'operation_id':op_id, 'state':old[2], 'created':False}
    try:
        connection.execute("INSERT INTO regime_payment_outbox(operation_id,provider,request_key,state) VALUES(?,?,?,'pending')",
                           (op_id,provider,request_key))
    except sqlite3.IntegrityError as exc:
        raise FenceBlocked('Outbox idempotency key already reserved') from exc
    return {'operation_id':op_id, 'state':'pending', 'created':True}


def mark_attempt_uncertain(connection: sqlite3.Connection, operation_id: str) -> None:
    """Record a dispatch attempt BEFORE network I/O; no blind auto-retry.

    Must be committed before the external provider request. A crash after commit
    is indistinguishable from one after an accepted request, so reconciliation
    is mandatory before another dispatch.
    """
    if not connection.in_transaction:
        raise FenceBlocked('Outbox update requires transaction')
    from .regime_outcome_receipt import require_open_commercial_checkout
    require_open_commercial_checkout(connection, operation_id)
    changed = connection.execute('''UPDATE regime_payment_outbox SET state='uncertain',attempts=attempts+1
                                    WHERE operation_id=? AND state='pending' ''', (operation_id,)).rowcount
    if changed != 1:
        raise FenceBlocked('Outbox is not pending; reconcile provider before retry')


def _require_unique_provider_reference(connection: sqlite3.Connection, operation_id: str,
                                       provider: str, provider_reference: str) -> None:
    """Reject reuse of one remote payment object by multiple local checkout orders.

    Existing duplicate legacy records remain inspectable rather than causing
    migration failure; integrity audits detect them and block transition.
    """
    other = connection.execute("""SELECT operation_id FROM regime_payment_outbox
        WHERE provider=? AND provider_reference=? AND operation_id!=? LIMIT 1""",
        (provider, provider_reference, operation_id)).fetchone()
    if other is not None:
        raise FenceBlocked('Provider reference already assigned to another checkout')


def confirm(connection: sqlite3.Connection, operation_id: str, *, provider_reference: str) -> None:
    # Confirm a dispatched checkout, never a merely queued request.

    # Requires an open commercial checkout receipt. Repeated confirmation with
    # the same remote reference is idempotent; contradictory references fail.
    if not connection.in_transaction:
        raise FenceBlocked('Confirmation requires transaction')
    if not isinstance(provider_reference, str) or not (1 <= len(provider_reference) <= 200):
        raise ValueError('Invalid provider reference')
    from .regime_outcome_receipt import require_open_commercial_checkout
    require_open_commercial_checkout(connection, operation_id)
    row = connection.execute('''SELECT o.state,o.provider_reference,f.kind,f.regime,f.status
        FROM regime_payment_outbox o LEFT JOIN regime_fence_operations f
        ON f.operation_id=o.operation_id WHERE o.operation_id=?''', (operation_id,)).fetchone()
    if row is None or tuple(row[2:]) != ('checkout','COMMERCIAL','open'):
        raise FenceBlocked('Open commercial checkout receipt required')
    state, existing_reference = row[:2]
    provider = connection.execute('SELECT provider FROM regime_payment_outbox WHERE operation_id=?',
                                  (operation_id,)).fetchone()[0]
    _require_unique_provider_reference(connection, operation_id, provider, provider_reference)
    if state == 'confirmed' and existing_reference == provider_reference:
        return
    if state != 'uncertain':
        raise FenceBlocked('Cannot confirm checkout without dispatched attempt')
    connection.execute("UPDATE regime_payment_outbox SET state='confirmed',provider_reference=? WHERE operation_id=?",
                       (provider_reference,operation_id))


def reconcile_verified_outcome(connection: sqlite3.Connection, operation_id: str, *,
                               provider: str, outcome: str, provider_reference: str | None = None) -> dict:
    """Record an externally VERIFIED checkout creation outcome.

    Caller must authenticate/verify the provider response before invoking this
    method. This never triggers network I/O, settles money, closes a fence, or
    reopens an uncertain dispatch for automatic retry.
    """
    if not connection.in_transaction:
        raise FenceBlocked('Provider reconciliation requires transaction')
    from .regime_outcome_receipt import require_open_commercial_checkout
    require_open_commercial_checkout(connection, operation_id)
    if provider not in ('stripe', 'paypal') or outcome not in ('confirmed', 'not_created'):
        raise ValueError('Invalid verified provider outcome')
    row = connection.execute('''SELECT provider,state,provider_reference,attempts
                                FROM regime_payment_outbox WHERE operation_id=?''',
                             (operation_id,)).fetchone()
    if row is None or row[0] != provider:
        raise FenceBlocked('Unknown or mismatched checkout provider')
    _, state, existing_reference, attempts = tuple(row)
    if outcome == 'confirmed':
        if not isinstance(provider_reference, str) or not (1 <= len(provider_reference) <= 200):
            raise ValueError('Provider confirmation requires a valid reference')
        _require_unique_provider_reference(connection, operation_id, provider, provider_reference)
        if state == 'cancelled' or (state == 'confirmed' and existing_reference != provider_reference):
            raise FenceBlocked('Contradictory provider confirmation')
        if state not in ('uncertain', 'confirmed'):
            raise FenceBlocked('No dispatch attempt to reconcile')
        connection.execute('''UPDATE regime_payment_outbox
                              SET state='confirmed',provider_reference=? WHERE operation_id=?''',
                           (provider_reference, operation_id))
        return {'operation_id':operation_id,'state':'confirmed','changed':state != 'confirmed'}
    if provider_reference is not None:
        raise ValueError('Negative outcome must not contain a provider reference')
    if state == 'cancelled':
        return {'operation_id':operation_id,'state':'cancelled','changed':False}
    if state != 'uncertain' or attempts < 1:
        raise FenceBlocked('Checkout cannot be cancelled without verified negative outcome for an attempted dispatch')
    connection.execute("UPDATE regime_payment_outbox SET state='cancelled' WHERE operation_id=?", (operation_id,))
    # The parent operation deliberately remains open until a separate operator
    # reconciliation verifies the order, finance ledger, and provider events.
    return {'operation_id':operation_id,'state':'cancelled','changed':True}
