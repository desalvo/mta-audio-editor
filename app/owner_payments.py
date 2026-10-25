"""Private local checkout recovery, never a complete provider statement."""
import re
from urllib.parse import urlsplit

from . import auth
from .regime_operation_fence import FenceBlocked

TERMINAL = ('paid', 'refunded', 'cancelled', 'canceled', 'failed')


def initialize(c):
    from . import credit_purchases, paypal_payments
    credit_purchases.init(c)
    paypal_payments.init(c)


def guard_pending(c, uid, kind, period=None):
    """Caller owns BEGIN IMMEDIATE; both schemas must already exist."""
    if kind == 'credits':
        stripe = c.execute('SELECT status FROM credit_purchase_orders WHERE user_id=?', (uid,))
        if any(row['status'] not in TERMINAL for row in stripe):
            raise FenceBlocked('An unresolved credit checkout exists; open your payment history')
        rows = c.execute("SELECT status FROM paypal_orders WHERE user_id=? AND kind='credits'", (uid,))
    elif kind == 'subscription':
        rows = c.execute("SELECT status FROM paypal_orders WHERE user_id=? AND kind='subscription' AND period_start=?", (uid, period))
    else:
        return  # Reversal targets have their own immutable pending-order guard.
    if any(row['status'] not in TERMINAL for row in rows):
        raise FenceBlocked('An unresolved checkout exists; open your payment history')


def safe_url(value, provider, environment=None):
    if not isinstance(value, str) or not value or any(ord(ch) <= 32 or ord(ch) == 127 or ch == '\\' for ch in value):
        return None
    try:
        target = urlsplit(value)
        allowed = 'checkout.stripe.com' if provider == 'stripe' else (
            'www.sandbox.paypal.com' if environment == 'sandbox' else 'www.paypal.com' if environment == 'live' else None)
        if target.scheme == 'https' and target.hostname == allowed and allowed and not target.username and not target.password and target.port in (None, 443):
            return value
    except ValueError:
        pass
    return None


def history(uid, offset=0, limit=20):
    if type(offset) is not int or offset < 0 or offset > 1000000 or type(limit) is not int or not 1 <= limit <= 50:
        raise ValueError('Invalid payment page')
    from .service_regime import commercial_allowed
    commercial = commercial_allowed()
    with auth.db() as c:
        initialize(c)
        rows = c.execute('''SELECT id,'stripe' AS provider,'credits' AS kind,amount_cents,created_at,status,
            session_id AS reference,checkout_url,NULL AS environment FROM credit_purchase_orders WHERE user_id=?
            UNION ALL SELECT id,'paypal',kind,amount_cents,created_at,status,provider_order,checkout_url,environment
            FROM paypal_orders WHERE user_id=? ORDER BY created_at DESC,provider,id LIMIT ? OFFSET ?''',
            (uid, uid, limit + 1, offset)).fetchall()
        tables={row[0] for row in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        review=set();risk={}
        if 'payment_reconciliation_events' in tables:
            for row in rows[:limit]:
                if c.execute("SELECT 1 FROM payment_reconciliation_events WHERE provider=? AND order_id=? AND state='pending' LIMIT 1",(row['provider'],row['id'])).fetchone():
                    review.add((row['provider'],row['id']))
        if 'payment_reconciliation_positions' in tables:
            for row in rows[:limit]:
                position=c.execute('SELECT held_minor FROM payment_reconciliation_positions WHERE provider=? AND order_id=? AND user_id=?',(row['provider'],row['id'],uid)).fetchone()
                if position:risk[(row['provider'],row['id'])]=position[0]
        # This is deliberately independent of the selected history page.
        held = any(row[0] not in TERMINAL for row in c.execute('''SELECT status FROM credit_purchase_orders WHERE user_id=?
            UNION ALL SELECT status FROM paypal_orders WHERE user_id=? AND kind='credits' ''', (uid, uid)))
    items = []
    for row in rows[:limit]:
        pending = row['status'] not in TERMINAL
        known = isinstance(row['reference'], str) and bool(re.fullmatch(r'cs_[A-Za-z0-9_]{1,110}' if row['provider']=='stripe' else r'[A-Z0-9]{6,64}', row['reference']))
        items.append({key: row[key] for key in ('id', 'provider', 'kind', 'amount_cents', 'created_at', 'status')})
        items[-1].update(financial_held_minor=risk.get((row['provider'],row['id']),0),financial_review_pending=(row['provider'],row['id']) in review,
                         can_verify=commercial and known, needs_admin=pending and not known,
                         checkout_url=safe_url(row['checkout_url'], row['provider'], row['environment']) if commercial and pending and known else None)
    return {'items': items, 'next_offset': offset + limit if len(rows) > limit else None,
            'credit_checkout_pending': held, 'commercial_payments': commercial, 'scope': 'local_checkout_records'}


def verify(uid, provider, order_id):
    from .service_regime import require_commercial
    from .payment_reconcile_service import reconcile_checkout
    require_commercial('payment verification')
    # Caller identity is checked again inside the initial provider snapshot,
    # before network I/O; immutable owner checks still protect the final write.
    reconcile_checkout(provider, order_id, expected_owner=uid)
    return {'verified': True}
