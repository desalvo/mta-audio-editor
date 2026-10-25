"""Authenticated, economically empty terminal checkout settlement.

Creation remains confirmed: an expired/voided provider object existed. Only the
unpaid local order and its original fence are closed. Timeouts and browser
cancellation never enter this module as proof.
"""
import hashlib
import json

from .regime_operation_fence import FenceBlocked


def terminal_receipt(c,provider,order_id):
    if not c.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='checkout_terminal_receipts'").fetchone():return None
    return c.execute('SELECT provider_reference,outcome,digest FROM checkout_terminal_receipts WHERE provider=? AND order_id=?',(provider,order_id)).fetchone()


def _empty(c,provider,order):
    if order['status'] not in ('pending','cancelled') or order['paid_at'] is not None:
        raise FenceBlocked('Checkout already has a financial outcome')
    if provider=='stripe':
        if order['payment_intent'] is not None or order['refunded_cents']:
            raise FenceBlocked('Stripe order has economic evidence')
        credit='purchase:'+order['id']
    else:
        if order['refund_due_micro']:raise FenceBlocked('PayPal order has a refund obligation')
        credit='paypal:'+order['id']
        tables={r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        for table,query in (
            ('paypal_captures','SELECT 1 FROM paypal_captures WHERE order_id=? LIMIT 1'),
            ('paypal_refunds','SELECT 1 FROM paypal_refunds WHERE order_id=? LIMIT 1'),
            ('paypal_financial_holds','SELECT 1 FROM paypal_financial_holds WHERE order_id=? LIMIT 1'),
            ('subscription_repayment_allocations','SELECT 1 FROM subscription_repayment_allocations WHERE order_id=? LIMIT 1'),
        ):
            if table in tables and c.execute(query,(order['id'],)).fetchone():
                raise FenceBlocked('PayPal checkout has financial movements')
    if c.execute('SELECT 1 FROM resource_credits WHERE id=?',(credit,)).fetchone():
        raise FenceBlocked('Checkout already has a wallet movement')
    p=c.execute("SELECT user_id,amount_minor,currency,refunded_minor,held_minor,net_micro,funded FROM payment_reconciliation_positions WHERE provider=? AND order_id=?",(provider,order['id'])).fetchone()
    if p is not None and tuple(p)!=(order['user_id'],order['amount_cents'],'EUR',0,0,0,0):
        raise FenceBlocked('Checkout already has a financial position')


def settle_empty(c,provider,order,*,reference,outcome,intent=None,failed_charge_proof=None):
    """Internal boundary: caller authenticates canonical or signed proof first."""
    if not c.in_transaction:raise FenceBlocked('Terminal outcome requires a write transaction')
    if (provider,outcome) not in (('stripe','expired'),('stripe','canceled_intent'),('paypal','voided')):
        raise ValueError('Unsupported terminal provider outcome')
    from .payment_reconciliation import initialize,record_event,mark_applied,bind_object
    initialize(c)
    _empty(c,provider,order)
    expected=order['session_id'] if provider=='stripe' else order['provider_order']
    if reference!=expected:raise FenceBlocked('Terminal provider identity changed')
    operation='checkout:'+provider+':'+order['id']
    row=c.execute('''SELECT o.provider,o.state,o.provider_reference,o.attempts,
      f.kind,f.regime,f.revision,f.status,s.regime,s.revision,s.transitioning
      FROM regime_payment_outbox o JOIN regime_fence_operations f ON f.operation_id=o.operation_id
      CROSS JOIN regime_fence_state s WHERE o.operation_id=? AND s.singleton=1''',(operation,)).fetchone()
    if (row is None or tuple(row[:3])!=(provider,'confirmed',reference) or row[3]<1
        or tuple(row[4:6])!=('checkout','COMMERCIAL') or tuple(row[5:7])!=tuple(row[8:10]) or row[10]):
        raise FenceBlocked('Terminal checkout requires its original confirmed active-epoch receipt')
    from . import auth
    from .service_regime import read_regime
    configured=read_regime(auth.data_root()/'service-regime.json')
    if (configured.regime.value,configured.revision)!=tuple(row[5:7]):
        raise FenceBlocked('Terminal checkout regime mirror differs from its active epoch')
    c.execute('''CREATE TABLE IF NOT EXISTS checkout_terminal_receipts(
      provider TEXT NOT NULL,order_id TEXT NOT NULL,user_id INTEGER NOT NULL REFERENCES users(id),
      provider_reference TEXT NOT NULL,outcome TEXT NOT NULL,digest TEXT NOT NULL,
      PRIMARY KEY(provider,order_id))''')
    c.execute('''CREATE TRIGGER IF NOT EXISTS checkout_terminal_immutable
      BEFORE UPDATE ON checkout_terminal_receipts BEGIN SELECT RAISE(ABORT,'Immutable terminal checkout receipt'); END''')
    normalized={'type':'checkout.terminal','order_id':order['id'],'provider_reference':reference,
                'outcome':outcome,'intent':intent,'amount_minor':order['amount_cents'],'currency':'EUR'}
    if failed_charge_proof is not None:
        if provider!='stripe' or not intent:raise ValueError('Failed-charge proof requires Stripe intent')
        from .stripe_failed_charge_proof import validate
        validate(failed_charge_proof,intent,order['amount_cents'])
        normalized['failed_charge_proof']=failed_charge_proof
    raw=json.dumps(normalized,sort_keys=True,allow_nan=False).encode();digest=hashlib.sha256(raw).hexdigest()
    previous=terminal_receipt(c,provider,order['id'])
    if previous and tuple(previous)!=(reference,outcome,digest):raise FenceBlocked('Contradictory terminal checkout receipt')
    if row[7]=='closed' and previous is None:raise FenceBlocked('Closed checkout lacks terminal receipt')
    # A signed unpaid/expired notification can be resolved by newer canonical
    # terminal proof. A payment, refund, risk or disputed intent cannot vanish.
    benign=[]
    for event_id,encoded in c.execute("SELECT event_id,normalized_json FROM payment_reconciliation_events WHERE provider=? AND state='pending'",(provider,)):
        event=json.loads(encoded)
        related=(event.get('order_id')==order['id'] or event.get('provider_order')==reference
                 or (intent is not None and event.get('payment_intent')==intent))
        if not related:continue
        if (provider=='stripe' and event.get('type') in ('checkout.session.expired','checkout.session.async_payment_failed','checkout.session.completed')
            and event.get('payment_status')=='unpaid' and event.get('order_id')==order['id']
            and event.get('id')==reference and type(event.get('amount_total')) is int and event['amount_total']==order['amount_cents']
            and event.get('currency')=='eur' and event.get('client_reference_id')==order['id']
            and event.get('payment_intent') in (None,intent)):
            benign.append(event_id)
        else:raise FenceBlocked('Pending financial event contradicts terminal checkout')
    event_id='terminal:'+digest
    record_event(c,provider,event_id,digest,normalized)
    bind_object(c,provider,reference,order['id'])
    if failed_charge_proof is not None:
        bind_object(c,provider,intent,order['id'])
        for charge in failed_charge_proof['charges']:bind_object(c,provider,charge['id'],order['id'])
    if provider=='stripe':c.execute("UPDATE credit_purchase_orders SET status='cancelled',checkout_url=NULL WHERE id=?",(order['id'],))
    else:c.execute("UPDATE paypal_orders SET status='cancelled',checkout_url=NULL WHERE id=?",(order['id'],))
    c.execute('''INSERT OR IGNORE INTO payment_reconciliation_positions
      (provider,order_id,user_id,amount_minor,currency,refunded_minor,held_minor,net_micro,funded)
      VALUES(?,?,?,?,'EUR',0,0,0,0)''',(provider,order['id'],order['user_id'],order['amount_cents']))
    if previous is None:c.execute('INSERT INTO checkout_terminal_receipts VALUES(?,?,?,?,?,?)',(provider,order['id'],order['user_id'],reference,outcome,digest))
    from .regime_checkout_fence import settle_if_enrolled
    if row[7]=='open':settle_if_enrolled(c,provider,order['id'])
    mark_applied(c,provider,event_id,order['id'])
    for old in benign:mark_applied(c,provider,old,order['id'])
    if provider=='stripe':
        from .regime_stripe_inbox import prepare,mark_applied as inbox_applied
        for identifier in [event_id,*benign]:
            event_digest=c.execute("SELECT digest FROM payment_reconciliation_events WHERE provider='stripe' AND event_id=?",(identifier,)).fetchone()[0]
            if prepare(c,event_id=identifier,order_id=order['id'],payload_sha256=event_digest):
                if not c.execute("SELECT 1 FROM regime_provider_inbox WHERE provider='stripe' AND event_id=?",(identifier,)).fetchone():
                    inbox_applied(c,event_id=identifier,order_id=order['id'],payload_sha256=event_digest)
    return {'provider':provider,'order_id':order['id'],'status':'cancelled','outcome':outcome,
            'checkout_closed':True,'ledger_reconciled':True,'duplicate':previous is not None,'transition_authorized':False}


def block_paid_after_terminal(c,provider,order_id,event_id):
    """Keep contradictory authenticated money durable for operator review."""
    if terminal_receipt(c,provider,order_id) is None:return False
    c.execute("UPDATE payment_reconciliation_events SET order_id=? WHERE provider=? AND event_id=? AND state='pending'",(order_id,provider,event_id))
    return True


def stripe_identity(session,order):
    if (session.get('id')!=order['session_id'] or session.get('mode')!='payment'
        or type(session.get('amount_total')) is not int or session['amount_total']!=order['amount_cents']
        or session.get('currency')!='eur' or session.get('client_reference_id')!=order['id']
        or session.get('metadata',{}).get('mta_order')!=order['id']):
        raise ValueError('Terminal Stripe checkout identity mismatch')


def paypal_identity(document,order,*,require_empty=True):
    from .paypal_payments import _cents
    units=document.get('purchase_units')
    if document.get('id')!=order['provider_order'] or document.get('intent')!='CAPTURE' or not isinstance(units,list) or len(units)!=1:
        raise ValueError('Terminal PayPal checkout identity mismatch')
    unit=units[0]
    if unit.get('custom_id')!=order['id'] or unit.get('reference_id')!=order['id'] or _cents(unit['amount'])!=order['amount_cents']:
        raise ValueError('Terminal PayPal unit mismatch')
    payments=unit.get('payments',{})
    if (not isinstance(payments,dict) or set(payments)-{'captures','refunds','authorizations'}
        or (require_empty and any(payments.get(key) for key in ('captures','refunds','authorizations')))):
        raise ValueError('Terminal PayPal checkout has payment objects')


def audit(c):
    """Check terminal proofs against live local order, journal and zero position."""
    if not c.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='checkout_terminal_receipts'").fetchone():return []
    problems=[]
    for provider,order_id,user,reference,outcome,digest in c.execute('SELECT * FROM checkout_terminal_receipts'):
        if provider=='stripe':order=c.execute('SELECT user_id,status,paid_at,session_id FROM credit_purchase_orders WHERE id=?',(order_id,)).fetchone()
        elif provider=='paypal':order=c.execute('SELECT user_id,status,paid_at,provider_order FROM paypal_orders WHERE id=?',(order_id,)).fetchone()
        else:problems.append('unknown_provider');continue
        position=c.execute('SELECT funded,refunded_minor,held_minor,net_micro FROM payment_reconciliation_positions WHERE provider=? AND order_id=?',(provider,order_id)).fetchone()
        event=c.execute('SELECT normalized_json,state,order_id,digest FROM payment_reconciliation_events WHERE provider=? AND event_id=?',(provider,'terminal:'+digest)).fetchone()
        fence=c.execute('SELECT status FROM regime_fence_operations WHERE operation_id=?',('checkout:'+provider+':'+order_id,)).fetchone()
        dispatch=c.execute('SELECT state,provider_reference FROM regime_payment_outbox WHERE operation_id=?',('checkout:'+provider+':'+order_id,)).fetchone()
        valid=(order is not None and tuple(order)==(user,'cancelled',None,reference) and position is not None and tuple(position)==(0,0,0,0)
               and event is not None and tuple(event[1:])==('applied',order_id,digest) and fence is not None and fence[0]=='closed'
               and dispatch is not None and tuple(dispatch)==('confirmed',reference))
        if valid:
            try:
                data=json.loads(event[0]);raw=json.dumps(data,sort_keys=True,allow_nan=False).encode()
                valid=(hashlib.sha256(raw).hexdigest()==digest and data.get('outcome')==outcome and data.get('provider_reference')==reference
                       and (provider,outcome) in (('stripe','expired'),('stripe','canceled_intent'),('paypal','voided')))
                if valid and 'failed_charge_proof' in data:
                    from .stripe_failed_charge_proof import validate
                    amount=c.execute('SELECT amount_cents FROM credit_purchase_orders WHERE id=?',(order_id,)).fetchone()[0]
                    ids=validate(data['failed_charge_proof'],data.get('intent'),amount)|{data['intent']}
                    valid=provider=='stripe' and data.get('amount_minor')==amount and all(
                        c.execute("SELECT 1 FROM payment_reconciliation_objects WHERE provider='stripe' AND object_id=? AND order_id=?",(identifier,order_id)).fetchone() is not None
                        for identifier in ids)
            except (ValueError,TypeError,AttributeError):valid=False
        if not valid:problems.append(provider+':'+order_id)
    return problems
