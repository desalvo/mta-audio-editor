"""Reconcile a verified negative dispatch against a never-funded local order.

This is not a refund or an assertion based on a timeout. Only an authenticated
provider verification recorded as ``cancelled`` qualifies; never close an order
with evidence of payment, capture or refund.
"""
from __future__ import annotations

import sqlite3

from .regime_operation_fence import FenceBlocked, settle


def close_verified_noncreated_checkout(connection: sqlite3.Connection, *, provider: str, order_id: str) -> dict:
    """Close one financially empty checkout within caller-owned write transaction.

    The caller must first verify the provider's negative outcome and record it
    in the outbox. Requires BEGIN IMMEDIATE in the surrounding code, not network.
    """
    if not connection.in_transaction:
        raise FenceBlocked('A caller-owned write transaction is required')
    if provider not in ('stripe', 'paypal') or not isinstance(order_id, str) or not (1 <= len(order_id) <= 120):
        raise ValueError('Invalid provider or order ID')
    op_id = f'checkout:{provider}:{order_id}'
    state = connection.execute('''SELECT o.state,o.attempts,o.provider_reference,f.kind,f.regime,f.status
        FROM regime_payment_outbox o JOIN regime_fence_operations f ON f.operation_id=o.operation_id
        WHERE o.operation_id=? AND o.provider=?''', (op_id,provider)).fetchone()
    if state is None or tuple(state[:3])[0] != 'cancelled' or state[1] < 1 or state[2] is not None or tuple(state[3:5]) != ('checkout','COMMERCIAL'):
        raise FenceBlocked('Verified negative commercial provider outcome required')
    if state[5] == 'closed':
        return {'operation_id':op_id,'closed':False,'already_closed':True}
    if state[5] != 'open':
        raise FenceBlocked('Invalid checkout receipt')
    table = 'credit_purchase_orders' if provider == 'stripe' else 'paypal_orders'
    known = {r[0] for r in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if table not in known:
        raise FenceBlocked('Missing local economic order table')
    if provider == 'stripe':
        row = connection.execute('''SELECT status,paid_at,payment_intent,refunded_cents
            FROM credit_purchase_orders WHERE id=?''',(order_id,)).fetchone()
        if row is None or row[0] not in ('pending','cancelled','canceled','failed') or row[1] is not None or row[2] is not None or row[3] != 0:
            raise FenceBlocked('Stripe order has unresolved economic evidence')
        changed = connection.execute("UPDATE credit_purchase_orders SET status='cancelled' WHERE id=? AND status='pending' AND paid_at IS NULL AND payment_intent IS NULL AND refunded_cents=0",(order_id,)).rowcount if row[0]=='pending' else 0
    else:
        row=connection.execute('''SELECT status,paid_at,provider_order,refund_due_micro
            FROM paypal_orders WHERE id=?''',(order_id,)).fetchone()
        if row is None or row[0] not in ('pending','cancelled','canceled','failed') or row[1] is not None or row[2] is not None or row[3] != 0:
            raise FenceBlocked('PayPal order has unresolved economic evidence')
        if not {'paypal_captures','paypal_refunds'}.issubset(known):
            raise FenceBlocked('PayPal economic schema incomplete')
        if connection.execute('SELECT 1 FROM paypal_captures WHERE order_id=? LIMIT 1',(order_id,)).fetchone() or connection.execute('SELECT 1 FROM paypal_refunds WHERE order_id=? LIMIT 1',(order_id,)).fetchone():
            raise FenceBlocked('PayPal financial movements exist')
        changed = connection.execute("UPDATE paypal_orders SET status='cancelled' WHERE id=? AND status='pending' AND paid_at IS NULL AND provider_order IS NULL AND refund_due_micro=0",(order_id,)).rowcount if row[0]=='pending' else 0
    if row[0]=='pending' and changed != 1:
        raise FenceBlocked('Economic order changed concurrently')
    settle(connection,op_id)
    return {'operation_id':op_id,'closed':True,'already_closed':False}
