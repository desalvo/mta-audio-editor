"""Read-only original subscription evidence, including pre-reversal legacy gaps.

Today's fee, mutable refund balances and provider observations cannot recover
the original split between applied fee and surplus. Missing proof stays open.
"""
from __future__ import annotations


def review(c, *, limit=50, offset=0):
    if type(limit) is not int or not 1 <= limit <= 200 or type(offset) is not int or offset < 0:
        raise ValueError('Invalid subscription evidence pagination')
    # A caller's write/read transaction is preserved. Standalone diagnostics use
    # one read snapshot and release it without committing any caller mutations.
    own_snapshot = not c.in_transaction
    if own_snapshot:
        c.execute('BEGIN')
    try:
        return _review(c, limit, offset)
    finally:
        if own_snapshot:
            c.rollback()


def _review(c, limit, offset):
    tables = {r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    # A partial legacy schema is an unavailable audit, never a verified empty
    # result. Explicit projections also make failures ordinary database errors.
    projections = {
        'paypal_orders': 'SELECT id,user_id,period_start,amount_cents,kind,status,paid_at FROM paypal_orders LIMIT 0',
        'paypal_captures': 'SELECT id,order_id,amount_cents FROM paypal_captures LIMIT 0',
        'subscription_payment_basis': 'SELECT order_id,user_id,period_start,fee_micro,gross_micro,surplus_micro FROM subscription_payment_basis LIMIT 0',
        'payment_reconciliation_positions': 'SELECT provider,order_id,user_id,amount_minor,currency,funded FROM payment_reconciliation_positions LIMIT 0',
    }
    for table, sql in projections.items():
        if table in tables:
            c.execute(sql)
    result = {'verified': True, 'checked': 0, 'total': 0, 'items': [],
              'limit': limit, 'offset': offset, 'transition_safe': False,
              'automatic_reconstruction_allowed': False}
    def gap(order_id, reason):
        index = result['total']
        if offset <= index < offset + limit:
            result['items'].append({'order_id': order_id, 'reason': reason})
        result['total'] += 1
        result['verified'] = False

    if 'paypal_orders' not in tables:
        if 'subscription_payment_basis' in tables:
            gap(None, 'subscription_order_schema_missing')
        return result
    if 'paypal_captures' not in tables:
        gap(None, 'subscription_capture_schema_missing')
        return result
    orders = c.execute("""SELECT o.* FROM paypal_orders o WHERE o.kind='subscription'
        AND (o.status='paid' OR o.paid_at IS NOT NULL
             OR EXISTS(SELECT 1 FROM paypal_captures p WHERE p.order_id=o.id))
        ORDER BY o.id""")
    for order in orders:
        result['checked'] += 1
        if (type(order['user_id']) is not int or type(order['period_start']) is not int
                or type(order['amount_cents']) is not int or order['amount_cents'] <= 0):
            gap(order['id'], 'original_payment_identity_invalid')
            continue
        basis = c.execute('SELECT * FROM subscription_payment_basis WHERE order_id=?',
                          (order['id'],)).fetchone() if 'subscription_payment_basis' in tables else None
        if basis is None:
            gap(order['id'], 'original_payment_basis_missing')
            continue
        fields = ('fee_micro', 'gross_micro', 'surplus_micro')
        if (any(type(basis[k]) is not int or basis[k] < 0 for k in fields)
                or basis['fee_micro'] + basis['surplus_micro'] != basis['gross_micro']
                or (basis['user_id'], basis['period_start'], basis['gross_micro']) !=
                (order['user_id'], order['period_start'], order['amount_cents'] * 10000)):
            gap(order['id'], 'original_payment_basis_conflict')
            continue
        captures = c.execute('SELECT amount_cents FROM paypal_captures WHERE order_id=?',
                             (order['id'],)).fetchall()
        if (not captures or any(type(p[0]) is not int or p[0] <= 0 for p in captures)
                or sum(p[0] for p in captures) != order['amount_cents']):
            gap(order['id'], 'original_capture_total_unproved')
            continue
        position = c.execute("""SELECT user_id,amount_minor,currency,funded
            FROM payment_reconciliation_positions WHERE provider='paypal' AND order_id=?""",
                             (order['id'],)).fetchone() if 'payment_reconciliation_positions' in tables else None
        if position is None or tuple(position) != (order['user_id'], order['amount_cents'], 'EUR', 1):
            gap(order['id'], 'original_funding_position_unproved')
    if 'subscription_payment_basis' in tables:
        for row in c.execute("""SELECT b.order_id FROM subscription_payment_basis b
            LEFT JOIN paypal_orders o ON o.id=b.order_id
            WHERE o.id IS NULL OR o.kind!='subscription' OR
              (o.status!='paid' AND o.paid_at IS NULL AND
               NOT EXISTS(SELECT 1 FROM paypal_captures p WHERE p.order_id=o.id)) ORDER BY b.order_id"""):
            result['checked'] += 1
            gap(row[0], 'original_payment_basis_unbound')
    return result
