"""Exact subscription refund receivables and immutable repayment allocations.

Repayments are separate from wallet credits. Their effective coverage follows
the authenticated payment position, so refunds/holds reopen the same debt and
do not create recursively duplicated receivables.
"""
import re
import time

from .regime_operation_fence import FenceBlocked


def initialize(c):
    c.execute('''CREATE TABLE IF NOT EXISTS paypal_subscription_reversals(
      refund_id TEXT PRIMARY KEY,order_id TEXT NOT NULL,user_id INTEGER NOT NULL,
      period_start INTEGER NOT NULL,amount_micro INTEGER NOT NULL)''')
    c.execute('''CREATE TABLE IF NOT EXISTS subscription_repayment_targets(
      order_id TEXT PRIMARY KEY,refund_id TEXT NOT NULL,quoted_micro INTEGER NOT NULL CHECK(quoted_micro>0),
      FOREIGN KEY(order_id) REFERENCES paypal_orders(id),
      FOREIGN KEY(refund_id) REFERENCES paypal_subscription_reversals(refund_id))''')
    c.execute('''CREATE TABLE IF NOT EXISTS subscription_repayment_allocations(
      order_id TEXT PRIMARY KEY,refund_id TEXT NOT NULL,amount_micro INTEGER NOT NULL CHECK(amount_micro>=0),
      created_at INTEGER NOT NULL,FOREIGN KEY(order_id) REFERENCES paypal_orders(id),
      FOREIGN KEY(refund_id) REFERENCES paypal_subscription_reversals(refund_id))''')
    c.execute('''CREATE TABLE IF NOT EXISTS subscription_payment_basis(
      order_id TEXT PRIMARY KEY REFERENCES paypal_orders(id) ON DELETE CASCADE,
      user_id INTEGER NOT NULL,period_start INTEGER NOT NULL,fee_micro INTEGER NOT NULL CHECK(fee_micro>=0),
      gross_micro INTEGER NOT NULL CHECK(gross_micro>0),surplus_micro INTEGER NOT NULL CHECK(surplus_micro>=0),
      CHECK(fee_micro+surplus_micro=gross_micro))''')
    for table in ('paypal_subscription_reversals','subscription_repayment_targets','subscription_repayment_allocations','subscription_payment_basis'):
        # Table names are a fixed internal allowlist; no identifier comes from users.
        c.execute(f'''CREATE TRIGGER IF NOT EXISTS {table}_immutable_update
          BEFORE UPDATE ON {table} BEGIN SELECT RAISE(ABORT,'Immutable subscription repayment'); END''')
        primary='refund_id' if table=='paypal_subscription_reversals' else 'order_id'
        c.execute(f'''CREATE TRIGGER IF NOT EXISTS {table}_immutable_delete
          BEFORE DELETE ON {table} WHEN mta_subscription_erasure('{table}',OLD.{primary})=0
          BEGIN SELECT RAISE(ABORT,'Immutable subscription repayment'); END''')


def authorize_account_erasure(c,uid,actor):
    """Permit only this retired owner's records in an approved erasure txn.

    The connection-local function disappears on close and is never persisted as
    a setting or exposed through payment APIs. Unrelated owners stay protected.
    """
    if not c.in_transaction:raise FenceBlocked('Account erasure requires a write transaction')
    tables={row[0] for row in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if 'subscription_repayment_targets' not in tables:return
    allowed={'paypal_subscription_reversals':{r[0] for r in c.execute('SELECT refund_id FROM paypal_subscription_reversals WHERE user_id=?',(uid,))},
             'subscription_repayment_targets':{r[0] for r in c.execute('SELECT t.order_id FROM subscription_repayment_targets t JOIN paypal_orders o ON o.id=t.order_id WHERE o.user_id=?',(uid,))},
             'subscription_repayment_allocations':{r[0] for r in c.execute('SELECT a.order_id FROM subscription_repayment_allocations a JOIN paypal_orders o ON o.id=a.order_id WHERE o.user_id=?',(uid,))},
             'subscription_payment_basis':{r[0] for r in c.execute('SELECT order_id FROM subscription_payment_basis WHERE user_id=?',(uid,))} if 'subscription_payment_basis' in tables else set()}
    if not any(allowed.values()):return
    admin=c.execute('SELECT role,active FROM users WHERE id=?',(actor,)).fetchone()
    owner=c.execute('SELECT role,active FROM users WHERE id=?',(uid,)).fetchone()
    lifecycle=c.execute('SELECT state FROM account_lifecycle WHERE user_id=?',(uid,)).fetchone()
    if (admin is None or tuple(admin)!=('admin',1) or owner is None or owner[0]=='admin' or owner[1]
        or lifecycle is None or lifecycle[0] not in ('deleted','expired','erasing')):
        raise FenceBlocked('Approved retired-account erasure required for subscription records')
    c.create_function('mta_subscription_erasure',2,lambda table,key:int(key in allowed.get(table,set())))


def rows(c,uid=None):
    tables={r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if 'paypal_subscription_reversals' not in tables:return []
    if uid is None:
        sources=c.execute('SELECT refund_id,order_id,user_id,period_start,amount_micro FROM paypal_subscription_reversals ORDER BY period_start,refund_id').fetchall()
    else:
        sources=c.execute('SELECT refund_id,order_id,user_id,period_start,amount_micro FROM paypal_subscription_reversals WHERE user_id=? ORDER BY period_start,refund_id',(uid,)).fetchall()
    result=[]
    for rid,order,user,period,amount in sources:
        if type(amount) is not int or amount<0:raise FenceBlocked('Invalid subscription reversal receivable')
        issue = _collection_issue(c, order, user, period)
        paid=0;payments=[]
        if 'subscription_repayment_allocations' in tables:
            for oid,allocated in c.execute('SELECT order_id,amount_micro FROM subscription_repayment_allocations WHERE refund_id=? ORDER BY created_at,order_id',(rid,)):
                if issue:
                    payments.append({'order_id':oid,'allocated_micro':None,'covered_micro':None,
                                     'refund_due_micro':None})
                    continue
                position=c.execute("SELECT p.net_micro,o.user_id,o.kind,o.status FROM payment_reconciliation_positions p JOIN paypal_orders o ON o.id=p.order_id WHERE p.provider='paypal' AND p.order_id=?",(oid,)).fetchone()
                if position is None or tuple(position[1:])!=(user,'subscription_reversal','paid') or not 0<=allocated<=amount:
                    raise FenceBlocked('Subscription repayment position or owner mismatch')
                coverage=min(allocated,max(0,position[0]),amount-paid);paid+=coverage
                payments.append({'order_id':oid,'allocated_micro':allocated,'covered_micro':coverage,
                                 'refund_due_micro':max(0,position[0]-coverage)})
        pending=None;checkout_url=None;reference_known=False
        if 'subscription_repayment_targets' in tables:
            active=c.execute("SELECT t.order_id,o.user_id,o.checkout_url,o.provider_order FROM subscription_repayment_targets t JOIN paypal_orders o ON o.id=t.order_id WHERE t.refund_id=? AND o.status NOT IN ('paid','cancelled','canceled','failed','refunded') ORDER BY o.created_at",(rid,)).fetchall()
            if len(active)>1:raise FenceBlocked('Multiple active subscription repayment checkouts')
            if active:
                if active[0][1]!=user:raise FenceBlocked('Subscription repayment checkout owner mismatch')
                pending=active[0][0];checkout_url=active[0][2];reference_known=bool(active[0][3])
        result.append({'refund_id':rid,'order_id':order,'user_id':user,'period_start':period,
                       'amount_micro':None if issue else amount,'covered_micro':None if issue else paid,
                       'due_micro':None if issue else amount-paid,
                       'collection_verified':issue is None,'collection_issue':issue,
                       'pending_order_id':pending,'pending_checkout_url':checkout_url,'pending_reference_known':reference_known,'payments':payments})
    return result


def sync(c):
    """Recompute refund liabilities after a repayment refund/hold/release."""
    for source in rows(c):
        if not source['collection_verified']:
            continue  # Unknown coverage cannot reduce a recorded refund obligation.
        for payment in source['payments']:
            c.execute('UPDATE paypal_orders SET refund_due_micro=? WHERE id=?',
                      (payment['refund_due_micro'],payment['order_id']))


def quote(c,uid,refund_id,expected_micro=None):
    if not isinstance(refund_id,str) or re.fullmatch(r'[A-Z0-9]{6,64}',refund_id) is None:
        raise ValueError('Invalid subscription refund reference')
    source=next((row for row in rows(c,uid) if row['refund_id']==refund_id),None)
    if source is not None and not source['collection_verified']:
        raise ValueError('Original subscription obligation requires verified original evidence')
    if source is None or source['due_micro']<=0:raise ValueError('No unpaid subscription reversal')
    if expected_micro is not None and (type(expected_micro) is not int or expected_micro!=source['due_micro']):
        raise ValueError('Subscription reversal amount changed; refresh the page')
    return source


def allocate(c,order):
    if not c.in_transaction:raise FenceBlocked('Subscription repayment requires a write transaction')
    target=c.execute('SELECT refund_id FROM subscription_repayment_targets WHERE order_id=?',(order['id'],)).fetchone()
    if target is None:raise FenceBlocked('Subscription repayment target missing')
    source=next((row for row in rows(c,order['user_id']) if row['refund_id']==target[0]),None)
    if source is None:raise FenceBlocked('Subscription repayment owner changed')
    if not source['collection_verified']:
        raise FenceBlocked('Original subscription evidence no longer verifies repayment')
    gross=order['amount_cents']*10000;allocated=min(gross,source['due_micro'])
    stamp=max(time.time_ns(),c.execute('SELECT coalesce(max(created_at),0)+1 FROM subscription_repayment_allocations').fetchone()[0])
    c.execute('INSERT INTO subscription_repayment_allocations VALUES(?,?,?,?)',
              (order['id'],target[0],allocated,stamp))
    return gross-allocated


def freeze_original_payment(c, order, surplus_micro):
    """Freeze the actual fee applied by fulfillment, never infer it from later rates."""
    if not c.in_transaction:
        raise FenceBlocked('Original subscription basis requires payment transaction')
    gross = order['amount_cents'] * 10000
    if type(surplus_micro) is not int or not 0 <= surplus_micro <= gross:
        raise FenceBlocked('Invalid original subscription surplus')
    values = (order['id'], order['user_id'], order['period_start'], gross-surplus_micro, gross, surplus_micro)
    prior = c.execute('SELECT * FROM subscription_payment_basis WHERE order_id=?', (order['id'],)).fetchone()
    if prior and tuple(prior) != values:
        raise FenceBlocked('Conflicting original subscription payment basis')
    c.execute('INSERT OR IGNORE INTO subscription_payment_basis VALUES(?,?,?,?,?,?)', values)


def original_loss_position(c, order):
    """Signed full-capture reversals and completed refunds, capped at fee.

    Dispute outcomes/protection and partial reversals are not collection authority. A full capture
    loss subsumes refunds of that capture; the same principal is never added twice.
    """
    from .subscription_basis_audit import original_basis_issue
    issue = original_basis_issue(c, order)
    if issue == 'original_payment_basis_missing':
        return None
    if issue:
        raise FenceBlocked('Original subscription payment evidence does not verify')
    basis = c.execute('SELECT * FROM subscription_payment_basis WHERE order_id=?', (order['id'],)).fetchone()
    total = 0
    holds = c.execute("SELECT 1 FROM sqlite_master WHERE name='paypal_financial_holds'").fetchone()
    for capture in c.execute('SELECT id,amount_cents FROM paypal_captures WHERE order_id=?', (order['id'],)):
        refunded = c.execute('SELECT coalesce(sum(amount_cents),0) FROM paypal_refunds WHERE capture_id=?', (capture['id'],)).fetchone()[0]
        full = holds and c.execute("SELECT 1 FROM paypal_financial_holds WHERE capture_id=? AND order_id=? AND status='permanent' AND kind='reversal' AND amount_cents=? LIMIT 1",
                                  (capture['id'],order['id'],capture['amount_cents'])).fetchone()
        total += capture['amount_cents'] if full else refunded
    return (min(basis['fee_micro'], max(0, total*10000-basis['surplus_micro'])),
            max(0,basis['surplus_micro']-total*10000))


def _collection_issue(c, order_id, user_id, period_start):
    """Stored legacy receivables alone never authorize another collection."""
    order = c.execute('SELECT * FROM paypal_orders WHERE id=?', (order_id,)).fetchone()
    if order is None or (order['user_id'], order['period_start']) != (user_id, period_start):
        return 'original_obligation_identity_unproved'
    from .subscription_basis_audit import original_basis_issue
    issue = original_basis_issue(c, order)
    if issue:
        return issue
    amounts = [r[0] for r in c.execute('SELECT amount_micro FROM paypal_subscription_reversals WHERE order_id=?',
                                     (order_id,))]
    if (any(type(n) is not int or n < 0 for n in amounts)
            or sum(amounts) > original_loss_position(c, order)[0]):
        return 'original_obligation_allocation_unproved'
    return None


def accrue_original_loss(c, order, hold_id):
    """Allocate one immutable incremental obligation within the original fee cap."""
    if not c.in_transaction:
        raise FenceBlocked('Subscription loss requires authenticated payment transaction')
    position = original_loss_position(c, order)
    if position is None:
        return False  # legacy payment requires independent original basis evidence
    target, remaining_surplus = position
    c.execute('UPDATE paypal_orders SET refund_due_micro=min(refund_due_micro,?) WHERE id=?',
              (remaining_surplus,order['id']))
    allocated = c.execute('SELECT coalesce(sum(amount_micro),0) FROM paypal_subscription_reversals WHERE order_id=?', (order['id'],)).fetchone()[0]
    if allocated > target:
        raise FenceBlocked('Subscription obligation exceeds proved original loss')
    due = target-allocated
    if due:
        import hashlib
        reference = 'LOSS' + hashlib.sha256((order['id']+'|'+hold_id).encode()).hexdigest().upper()[:60]
        c.execute('INSERT INTO paypal_subscription_reversals VALUES(?,?,?,?,?)',
                  (reference,order['id'],order['user_id'],order['period_start'],due))
    return True


def original_loss_review(c):
    """Read-only gaps: partial/legacy permanent losses never become guessed debt."""
    tables = {r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if not {'paypal_orders', 'paypal_financial_holds'} <= tables:
        return {'verified': True, 'unresolved': []}
    gaps = []
    for order in c.execute("SELECT DISTINCT o.* FROM paypal_orders o JOIN paypal_financial_holds h ON h.order_id=o.id WHERE o.kind='subscription' AND h.status='permanent'"):
        basis = c.execute('SELECT * FROM subscription_payment_basis WHERE order_id=?', (order['id'],)).fetchone() if 'subscription_payment_basis' in tables else None
        if basis is None:
            gaps.append({'order_id': order['id'], 'reason': 'original_payment_basis_missing'})
            continue
        movement = c.execute('''SELECT 1 FROM paypal_financial_holds h JOIN paypal_captures p ON p.id=h.capture_id
          WHERE h.order_id=? AND h.status='permanent' AND h.kind!='reversal'
          AND NOT EXISTS(SELECT 1 FROM paypal_financial_holds f WHERE f.capture_id=p.id
            AND f.order_id=h.order_id AND f.status='permanent' AND f.kind='reversal'
            AND f.amount_cents=p.amount_cents) LIMIT 1''', (order['id'],)).fetchone()
        if movement:
            gaps.append({'order_id': order['id'], 'reason': 'permanent_dispute_movement_unproved'})
            continue
        partial = c.execute("""SELECT 1 FROM paypal_financial_holds h JOIN paypal_captures p ON p.id=h.capture_id
          WHERE h.order_id=? AND h.status='permanent' AND h.amount_cents<p.amount_cents
          AND NOT EXISTS(SELECT 1 FROM paypal_financial_holds f WHERE f.capture_id=p.id
            AND f.order_id=h.order_id AND f.status='permanent' AND f.kind='reversal' AND f.amount_cents=p.amount_cents) LIMIT 1""", (order['id'],)).fetchone()
        if partial:
            gaps.append({'order_id': order['id'], 'reason': 'partial_permanent_loss_allocation_unproved'})
    return {'verified': not gaps, 'unresolved': gaps}


def original_loss_target(c, order):
    position = original_loss_position(c, order)
    return position[0] if position is not None else None
