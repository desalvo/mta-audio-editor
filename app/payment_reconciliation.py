"""Transactional, authenticated-event accounting for credit purchases.

Only provider adapters call this module after authenticating the transport. The
observation journal remains diagnostic; arbitrary observations cannot fund users.
All DDL and financial mutations participate in the caller's write transaction.
Amounts are EUR cents because the existing credit product is quoted in EUR.
"""
from __future__ import annotations

import hashlib
import json
import time

from .regime_operation_fence import FenceBlocked


def initialize(c):
    if not c.in_transaction:
        raise FenceBlocked('Financial events require a write transaction')
    for sql in (
        '''CREATE TABLE IF NOT EXISTS payment_reconciliation_events(
          provider TEXT NOT NULL,event_id TEXT NOT NULL,digest TEXT NOT NULL,
          normalized_json TEXT NOT NULL,order_id TEXT,state TEXT NOT NULL
          CHECK(state IN ('pending','applied')),created_at INTEGER NOT NULL,
          PRIMARY KEY(provider,event_id))''',
        '''CREATE TABLE IF NOT EXISTS payment_reconciliation_positions(
          provider TEXT NOT NULL,order_id TEXT NOT NULL,user_id INTEGER NOT NULL,
          amount_minor INTEGER NOT NULL CHECK(amount_minor>=0),currency TEXT NOT NULL,
          refunded_minor INTEGER NOT NULL DEFAULT 0 CHECK(refunded_minor>=0),
          held_minor INTEGER NOT NULL DEFAULT 0 CHECK(held_minor>=0),
          net_micro INTEGER NOT NULL DEFAULT 0,funded INTEGER NOT NULL DEFAULT 0,
          PRIMARY KEY(provider,order_id))''',
        '''CREATE TABLE IF NOT EXISTS payment_reconciliation_disputes(
          provider TEXT NOT NULL,dispute_id TEXT NOT NULL,order_id TEXT NOT NULL,
          amount_minor INTEGER NOT NULL,status TEXT NOT NULL,event_created INTEGER NOT NULL,
          PRIMARY KEY(provider,dispute_id))''',
        '''CREATE TABLE IF NOT EXISTS payment_reconciliation_objects(
          provider TEXT NOT NULL,object_id TEXT NOT NULL,order_id TEXT NOT NULL,
          PRIMARY KEY(provider,object_id))''',
        '''CREATE TABLE IF NOT EXISTS payment_reconciliation_movements(
          provider TEXT NOT NULL,event_id TEXT NOT NULL,credit_id TEXT NOT NULL UNIQUE,
          order_id TEXT NOT NULL,delta_micro INTEGER NOT NULL,
          PRIMARY KEY(provider,event_id),
          FOREIGN KEY(credit_id) REFERENCES resource_credits(id))''',
    ):
        c.execute(sql)
    c.execute('''CREATE TRIGGER IF NOT EXISTS payment_events_immutable_payload
      BEFORE UPDATE OF provider,event_id,digest,normalized_json,created_at ON payment_reconciliation_events
      BEGIN SELECT RAISE(ABORT,'Immutable financial event payload'); END''')
    c.execute('''CREATE TRIGGER IF NOT EXISTS payment_events_no_rebind
      BEFORE UPDATE OF order_id,state ON payment_reconciliation_events
      WHEN (OLD.order_id IS NOT NULL AND NEW.order_id IS NOT OLD.order_id)
        OR (OLD.state='applied' AND NEW.state!='applied')
      BEGIN SELECT RAISE(ABORT,'Financial event cannot be rebound or reopened'); END''')


def record_event(c, provider, event_id, digest, normalized):
    initialize(c)
    if provider not in ('stripe','paypal') or not isinstance(event_id,str) or not 1<=len(event_id)<=200:
        raise ValueError('Invalid financial event identity')
    raw=json.dumps(normalized,sort_keys=True,separators=(',',':'),allow_nan=False)
    old=c.execute('SELECT digest,normalized_json,state FROM payment_reconciliation_events WHERE provider=? AND event_id=?',
                  (provider,event_id)).fetchone()
    if old:
        if tuple(old[:2])!=(digest,raw):
            raise FenceBlocked('Financial event identity reused with conflicting payload')
        return old[2]=='applied'
    c.execute("INSERT INTO payment_reconciliation_events VALUES(?,?,?,?,NULL,'pending',?)",
              (provider,event_id,digest,raw,int(time.time())))
    return False


def bind_object(c, provider, object_id, order_id):
    if not isinstance(object_id,str) or not 1<=len(object_id)<=200:
        raise ValueError('Invalid provider financial object')
    old=c.execute('SELECT order_id FROM payment_reconciliation_objects WHERE provider=? AND object_id=?',
                  (provider,object_id)).fetchone()
    if old and old[0]!=order_id:
        raise FenceBlocked('Financial object already belongs to another order')
    c.execute('INSERT OR IGNORE INTO payment_reconciliation_objects VALUES(?,?,?)',(provider,object_id,order_id))


def mark_applied(c,provider,event_id,order_id):
    c.execute("UPDATE payment_reconciliation_events SET order_id=?,state='applied' WHERE provider=? AND event_id=?",
              (order_id,provider,event_id))


def stripe_normalize(payload):
    kind=payload['type'];obj=payload.get('data',{}).get('object')
    if not isinstance(obj,dict):raise ValueError('Invalid Stripe event object')
    fields=('id','payment_intent','amount_refunded','amount','currency','status','payment_status',
            'amount_total','client_reference_id')
    result={k:obj[k] for k in fields if k in obj}
    result['type']=kind
    if kind.startswith('checkout.session.'):
        result['order_id']=obj.get('metadata',{}).get('mta_order')
    if kind.startswith('charge.dispute.'):
        stamp=payload.get('created')
        if type(stamp) is not int or stamp<0:raise ValueError('Missing dispute event timestamp')
        result['event_created']=stamp
    return result


def _stripe_position(c,order):
    old=c.execute("SELECT * FROM payment_reconciliation_positions WHERE provider='stripe' AND order_id=?",(order['id'],)).fetchone()
    if old is None:
        funded=order['status']=='paid'
        refunded=order['refunded_cents'] if funded else 0
        if not 0<=refunded<=order['amount_cents']:raise FenceBlocked('Invalid legacy refund balance')
        if funded:
            purchase=c.execute('SELECT user_id,delta_micro FROM resource_credits WHERE id=?',('purchase:'+order['id'],)).fetchone()
            refunds=c.execute('SELECT coalesce(sum(delta_micro),0) FROM resource_credits WHERE user_id=? AND reason=?',
                              (order['user_id'],'Stripe credit refund: '+order['id'])).fetchone()[0]
            if purchase is None or tuple(purchase)!=(order['user_id'],order['amount_cents']*10000) or refunds!=-refunded*10000:
                raise FenceBlocked('Legacy Stripe money requires explicit reconciliation')
        c.execute('''INSERT INTO payment_reconciliation_positions
          (provider,order_id,user_id,amount_minor,currency,refunded_minor,net_micro,funded)
          VALUES('stripe',?,?,?,'EUR',?,?,?)''',
          (order['id'],order['user_id'],order['amount_cents'],refunded,(order['amount_cents']-refunded)*10000 if funded else 0,int(funded)))
        old=c.execute("SELECT * FROM payment_reconciliation_positions WHERE provider='stripe' AND order_id=?",(order['id'],)).fetchone()
    if (old['user_id'],old['amount_minor'],old['currency'])!=(order['user_id'],order['amount_cents'],'EUR'):
        raise FenceBlocked('Financial position identity drift')
    return old


def _stripe_apply(c,event_id,data,order):
    from .regime_checkout_fence import verify_enrolled_payment,settle_if_enrolled
    from .regime_stripe_inbox import prepare,mark_applied as inbox_applied
    verify_enrolled_payment(c,'stripe',order['id'])
    event=c.execute("SELECT digest FROM payment_reconciliation_events WHERE provider='stripe' AND event_id=?",(event_id,)).fetchone()
    enrolled=prepare(c,event_id=event_id,order_id=order['id'],payload_sha256=event[0])
    kind=data['type'];p=_stripe_position(c,order)
    funded=p['funded'];refunded=p['refunded_minor'];held=p['held_minor']
    if kind in ('checkout.session.completed','checkout.session.async_payment_succeeded'):
        if (data.get('payment_status')!='paid' or type(data.get('amount_total')) is not int
            or data['amount_total']!=order['amount_cents'] or data.get('currency')!='eur'
            or data.get('client_reference_id')!=order['id']):raise ValueError('Payment amount or identity mismatch')
        if order['session_id'] is not None and data.get('id')!=order['session_id']:raise ValueError('Payment session mismatch')
        intent=data.get('payment_intent')
        if not isinstance(intent,str) or not intent.startswith('pi_'):raise ValueError('Missing payment intent')
        if order['payment_intent'] and order['payment_intent']!=intent:raise FenceBlocked('Payment intent changed')
        if c.execute('SELECT 1 FROM credit_purchase_orders WHERE payment_intent=? AND id!=?',(intent,order['id'])).fetchone():
            raise FenceBlocked('Payment intent already belongs to another order')
        bind_object(c,'stripe',intent,order['id']);bind_object(c,'stripe',data['id'],order['id'])
        c.execute("UPDATE credit_purchase_orders SET status='paid',paid_at=coalesce(paid_at,?),payment_intent=?,session_id=? WHERE id=?",
                  (int(time.time()),intent,data['id'],order['id']))
        funded=1
    elif kind=='charge.refunded':
        amount=data.get('amount_refunded')
        if type(amount) is not int or not 0<=amount<=p['amount_minor'] or data.get('currency')!='eur':raise ValueError('Invalid refund')
        if 'amount' in data and (type(data['amount']) is not int or data['amount']!=p['amount_minor']):raise ValueError('Refund charge amount mismatch')
        refunded=max(refunded,amount)  # cumulative snapshots can arrive out of order
        c.execute('UPDATE credit_purchase_orders SET refunded_cents=? WHERE id=?',(refunded,order['id']))
    elif kind.startswith('charge.dispute.'):
        amount=data.get('amount');status=data.get('status');did=data.get('id');created=data['event_created']
        statuses={'needs_response','under_review','won','lost','warning_needs_response','warning_under_review','warning_closed'}
        if (type(amount) is not int or not 0<amount<=p['amount_minor'] or data.get('currency')!='eur'
            or status not in statuses or not isinstance(did,str) or not did.startswith('dp_')):raise ValueError('Invalid dispute')
        previous=c.execute("SELECT order_id,amount_minor,status,event_created FROM payment_reconciliation_disputes WHERE provider='stripe' AND dispute_id=?",(did,)).fetchone()
        if previous and tuple(previous[:2])!=(order['id'],amount):raise FenceBlocked('Dispute identity changed')
        terminal={'won','lost','warning_closed'}
        update=previous is None or created>previous[3]
        if previous and status!=previous[2]:
            if previous[2] in terminal:
                if status in terminal:raise FenceBlocked('Conflicting terminal dispute outcomes')
                update=False
            elif created==previous[3]:raise FenceBlocked('Ambiguous dispute event order')
        if update:
            c.execute('''INSERT INTO payment_reconciliation_disputes VALUES('stripe',?,?,?,?,?)
              ON CONFLICT(provider,dispute_id) DO UPDATE SET status=excluded.status,event_created=excluded.event_created''',
              (did,order['id'],amount,status,created))
        held=c.execute("SELECT coalesce(sum(amount_minor),0) FROM payment_reconciliation_disputes WHERE provider='stripe' AND order_id=? AND status NOT IN ('won','warning_closed')",(order['id'],)).fetchone()[0]
    # Overlapping refund and dispute exposure never removes more than the purchase.
    target=max(0,p['amount_minor']-min(p['amount_minor'],refunded+held))*10000 if funded else 0
    delta=target-p['net_micro']
    if delta:
        if not p['funded'] and funded:credit_id='purchase:'+order['id'];reason='Stripe credit purchase: '+order['id']
        elif kind=='charge.refunded':credit_id='refund:'+event_id;reason='Stripe credit refund: '+order['id']
        else:credit_id='reconcile:stripe:'+event_id;reason='Stripe dispute adjustment: '+order['id']
        c.execute('INSERT INTO resource_credits VALUES(?,?,?,?,?,?)',(credit_id,order['user_id'],delta,None,reason,int(time.time())))
        c.execute("INSERT INTO payment_reconciliation_movements VALUES('stripe',?,?,?,?)",(event_id,credit_id,order['id'],delta))
    c.execute("UPDATE payment_reconciliation_positions SET funded=?,refunded_minor=?,held_minor=?,net_micro=? WHERE provider='stripe' AND order_id=?",
              (funded,refunded,held,target,order['id']))
    if not p['funded'] and funded:settle_if_enrolled(c,'stripe',order['id'])
    if enrolled:inbox_applied(c,event_id=event_id,order_id=order['id'],payload_sha256=event[0])
    c.execute('INSERT OR IGNORE INTO credit_payment_events VALUES(?,?)',(event_id,int(time.time())))
    mark_applied(c,'stripe',event_id,order['id'])


def process_stripe(c,payload,raw):
    """Called only after Stripe HMAC verification, under BEGIN IMMEDIATE."""
    data=stripe_normalize(payload);event_id=payload['id'];digest=hashlib.sha256(raw).hexdigest()
    if record_event(c,'stripe',event_id,digest,data):return {'received':True,'duplicate':True}
    # Historic applied events do not acquire invented new financial authority.
    if c.execute('SELECT 1 FROM credit_payment_events WHERE id=?',(event_id,)).fetchone():
        mark_applied(c,'stripe',event_id,None);return {'received':True,'duplicate':True}
    kind=data['type']
    if kind.startswith('checkout.session.'):
        order=c.execute('SELECT * FROM credit_purchase_orders WHERE id=?',(data.get('order_id'),)).fetchone()
        if order is None:raise ValueError('Unknown credit purchase')
        from .checkout_terminal_outcomes import block_paid_after_terminal,stripe_identity,settle_empty
        if kind in ('checkout.session.expired','checkout.session.async_payment_failed'):
            obj=payload['data']['object'];stripe_identity(obj,order)
            if obj.get('payment_status')!='unpaid':raise ValueError('Invalid unpaid Stripe notification')
            if kind=='checkout.session.expired' and obj.get('status')=='expired' and 'payment_intent' in obj and obj['payment_intent'] is None:
                result=settle_empty(c,'stripe',order,reference=obj['id'],outcome='expired')
                c.execute('INSERT OR IGNORE INTO credit_payment_events VALUES(?,?)',(event_id,int(time.time())))
                return {'received':True,**result}
            return {'received':True,'pending':True}
        if data.get('payment_status')=='paid' and block_paid_after_terminal(c,'stripe',order['id'],event_id):
            return {'received':True,'pending':True,'conflict':True}
        if data.get('payment_status')!='paid':return {'received':True,'pending':True}
    else:
        intent=data.get('payment_intent')
        if not isinstance(intent,str) or not intent.startswith('pi_'):raise ValueError('Missing reversal payment intent')
        orders=c.execute('SELECT * FROM credit_purchase_orders WHERE payment_intent=?',(intent,)).fetchall()
        if len(orders)>1:raise FenceBlocked('Ambiguous legacy payment intent')
        if not orders:return {'received':True,'pending':True}
        order=orders[0]
    _stripe_apply(c,event_id,data,order)
    # Replayed after funding, in the very same transaction: no spendable window
    # exists between applying an out-of-order payment and its pending reversals.
    if kind.startswith('checkout.session.'):
        intent=data['payment_intent']
        for pending_id,normalized in c.execute("SELECT event_id,normalized_json FROM payment_reconciliation_events WHERE provider='stripe' AND state='pending' ORDER BY created_at,event_id").fetchall():
            pending=json.loads(normalized)
            if pending.get('payment_intent')==intent:
                if pending['type'].startswith('checkout.session.'):
                    if pending.get('order_id')==order['id']:mark_applied(c,'stripe',pending_id,order['id'])
                else:_stripe_apply(c,pending_id,pending,order)
    return {'received':True}


def report(c,*,limit=50,offset=0):
    """Read-only financial positions and pending authenticated events; no cutover."""
    if type(limit) is not int or not 1<=limit<=200 or type(offset) is not int or offset<0:raise ValueError('Invalid report pagination')
    tables={row[0] for row in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    required={'payment_reconciliation_events','payment_reconciliation_positions','payment_reconciliation_movements'}
    if not required<=tables:return {'verified':False,'pending':None,'positions':[],'transition_safe':False,'issues':['schema_unavailable']}
    pending=c.execute("SELECT count(*) FROM payment_reconciliation_events WHERE state='pending'").fetchone()[0]
    rows=c.execute('''SELECT provider,order_id,user_id,amount_minor,currency,refunded_minor,held_minor,net_micro,funded
      FROM payment_reconciliation_positions ORDER BY provider,order_id LIMIT ? OFFSET ?''',(limit,offset)).fetchall()
    keys=('provider','order_id','user_id','amount_minor','currency','refunded_minor','held_minor','net_micro','funded')
    issues=[]
    from .checkout_terminal_outcomes import audit as terminal_audit
    if terminal_audit(c):issues.append('terminal_checkout_receipt_mismatch')
    mismatches=c.execute('''SELECT count(*) FROM payment_reconciliation_movements m
      LEFT JOIN resource_credits r ON r.id=m.credit_id WHERE r.id IS NULL OR r.delta_micro!=m.delta_micro
      OR NOT EXISTS(SELECT 1 FROM payment_reconciliation_positions p WHERE p.provider=m.provider
        AND p.order_id=m.order_id AND p.user_id=r.user_id)''').fetchone()[0]
    if mismatches:issues.append('ledger_movement_mismatch')
    invalid=c.execute('''SELECT count(*) FROM payment_reconciliation_positions WHERE currency!='EUR'
      OR refunded_minor>amount_minor OR net_micro!=CASE WHEN funded=1
      THEN max(0,amount_minor-min(amount_minor,refunded_minor+held_minor))*10000 ELSE 0 END''').fetchone()[0]
    if invalid:issues.append('invalid_position')
    wallet_drift=0
    for provider,order_id,user_id,net in c.execute('SELECT provider,order_id,user_id,net_micro FROM payment_reconciliation_positions'):
        if provider=='stripe':
            actual=c.execute('''SELECT coalesce(sum(delta_micro),0) FROM resource_credits
              WHERE user_id=? AND (id=? OR reason=? OR reason=?)''',
              (user_id,'purchase:'+order_id,'Stripe credit refund: '+order_id,'Stripe dispute adjustment: '+order_id)).fetchone()[0]
        else:
            if 'paypal_orders' not in tables:wallet_drift+=1;continue
            purpose=c.execute('SELECT kind FROM paypal_orders WHERE id=?',(order_id,)).fetchone()
            if purpose is None:wallet_drift+=1;continue
            if purpose[0]!='credits':continue
            actual=c.execute('''SELECT coalesce(sum(delta_micro),0) FROM resource_credits
              WHERE user_id=? AND (id=? OR reason=? OR reason=?)''',
              (user_id,'paypal:'+order_id,'PayPal credit refund: '+order_id,'PayPal risk adjustment: '+order_id)).fetchone()[0]
        if actual!=net:wallet_drift+=1
    if wallet_drift:issues.append('wallet_position_drift')
    active=0
    if 'payment_reconciliation_disputes' in tables:
        active+=c.execute("SELECT count(*) FROM payment_reconciliation_disputes WHERE status NOT IN ('won','lost','warning_closed')").fetchone()[0]
    if 'paypal_financial_holds' in tables:
        active+=c.execute("SELECT count(*) FROM paypal_financial_holds WHERE status IN ('held','uncertain')").fetchone()[0]
    from .subscription_receivables import rows as reversal_rows
    receivables=None;repayment_refunds=None
    try:
        reversals=reversal_rows(c)
        receivables=sum(row['due_micro'] for row in reversals)
        repayment_refunds=sum(payment['refund_due_micro'] for row in reversals for payment in row['payments'])
    except FenceBlocked:
        issues.append('subscription_repayment_unverifiable')
    subscription_risk=c.execute("SELECT coalesce(sum(p.held_minor),0)*10000 FROM payment_reconciliation_positions p JOIN paypal_orders o ON p.provider='paypal' AND p.order_id=o.id WHERE o.kind='subscription'").fetchone()[0] if 'paypal_orders' in tables else 0
    from .subscription_receivables import original_loss_review
    original_losses=original_loss_review(c)
    if not original_losses['verified']:issues.append('subscription_original_loss_unverified')
    positions=[dict(zip(keys,row)) for row in rows]
    from .checkout_terminal_outcomes import terminal_receipt
    for position in positions:
        receipt=terminal_receipt(c,position['provider'],position['order_id'])
        position['checkout_outcome']=receipt[1] if receipt else None
        if position['provider']=='paypal':
            from .paypal_dispute_details import admin_reviews
            position['movement_reviews']=admin_reviews(c,position['order_id'])
    return {'verified':not issues,'pending':pending,'subscription_reversal_due_micro':receivables,'subscription_repayment_refund_due_micro':repayment_refunds,'subscription_risk_micro':subscription_risk,'subscription_original_loss_review':original_losses,'active_disputes':active,'positions':positions,
            'total':c.execute('SELECT count(*) FROM payment_reconciliation_positions').fetchone()[0],
            'issues':issues,'transition_safe':False,'scope':'authenticated events; future reversals remain possible'}
