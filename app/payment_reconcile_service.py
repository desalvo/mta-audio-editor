"""Authenticated owner/admin GET reconciliation; never captures/refunds money.

Expected money, identities and credentials come from the local database, never
from browser-supplied observations. Provider I/O precedes every write lock. All
Stripe pages must validate before a journal/credit transaction can start.
"""
from __future__ import annotations

import hashlib
import json
import time
from urllib.parse import urlencode

import httpx

from . import auth
from .regime_operation_fence import FenceBlocked
from .regime_provider_probe import _get, _reference, ProviderProbeError
from .regime_provider_settlement import verify_stripe_settlement


def _pages(client,path,headers,params,*,max_items=None):
    items=[];seen=set();cursor=None
    for _ in range(100):
        query={**params,'limit':100}
        if cursor:query['starting_after']=cursor
        page=_get(client,'https://api.stripe.com/v1/'+path+'?'+urlencode(query),headers)
        data=page.get('data')
        if not isinstance(data,list) or type(page.get('has_more')) is not bool:raise ProviderProbeError('Incomplete provider history')
        for item in data:
            if not isinstance(item,dict):raise ProviderProbeError('Malformed provider history')
            identifier=_reference(item.get('id'))
            if identifier in seen:raise ProviderProbeError('Provider pagination repeated an object')
            seen.add(identifier);items.append(item)
            if max_items is not None and len(items)>max_items:raise ProviderProbeError('Provider history exceeds reconciliation bound')
        if not page['has_more']:return items
        if max_items is not None and len(items)>=max_items:raise ProviderProbeError('Provider history exceeds reconciliation bound')
        if not data:raise ProviderProbeError('Empty provider continuation')
        cursor=data[-1]['id']
    raise ProviderProbeError('Provider history exceeds reconciliation bound')


def reconcile_stripe(order_id,*,client,expected_owner=None):
    from . import credit_purchases as shop
    from .payment_reconciliation import process_stripe
    from .regime_financial_evidence import record_observation
    with auth.db() as c:
        shop.init(c)
        row=c.execute('SELECT * FROM credit_purchase_orders WHERE id=?',(order_id,)).fetchone()
        key=auth._open(c.execute('SELECT secret_key FROM credit_payment_config WHERE id=1').fetchone()[0])
        if row is None or (expected_owner is not None and (type(expected_owner) is not int or row['user_id']!=expected_owner)):
            raise ValueError('Payment unavailable')
        initial=dict(row)
    session_id=_reference(initial['session_id'])
    if not session_id.startswith('cs_') or not key.startswith(('sk_test_','sk_live_')):
        raise ProviderProbeError('Invalid Stripe reference or credentials')
    headers={'Authorization':'Bearer '+key}
    first=_get(client,'https://api.stripe.com/v1/checkout/sessions/'+session_id,headers)
    if first.get('status')!='complete' or first.get('payment_status')!='paid':
        return _stripe_unpaid(initial,key,first,client=client)
    observation=verify_stripe_settlement(session_id,key,initial['amount_cents'],'EUR',client=client)
    headers={'Authorization':'Bearer '+key}
    session=_get(client,'https://api.stripe.com/v1/checkout/sessions/'+session_id,headers)
    if (session.get('id')!=session_id or session.get('payment_intent')!=observation['payment_intent']
        or session.get('status')!='complete' or session.get('payment_status')!='paid'
        or session.get('amount_total')!=initial['amount_cents'] or session.get('currency')!='eur'
        or session.get('client_reference_id')!=order_id
        or session.get('metadata',{}).get('mta_order')!=order_id):raise ProviderProbeError('Canonical checkout identity mismatch')
    intent=_get(client,'https://api.stripe.com/v1/payment_intents/'+observation['payment_intent'],headers)
    charge_id=_reference(intent.get('latest_charge'))
    charge=_get(client,'https://api.stripe.com/v1/charges/'+charge_id,headers)
    if (intent.get('id')!=observation['payment_intent'] or charge.get('id')!=charge_id
        or charge.get('payment_intent')!=observation['payment_intent']
        or type(charge.get('amount')) is not int or charge['amount']!=initial['amount_cents']
        or charge.get('currency')!='eur' or charge.get('paid') is not True
        or charge.get('captured') is not True):raise ProviderProbeError('Canonical charge identity mismatch')
    refunds=_pages(client,'refunds',headers,{'charge':charge_id})
    total=0
    for refund in refunds:
        if (refund.get('charge')!=charge_id or refund.get('payment_intent')!=observation['payment_intent']
            or type(refund.get('amount')) is not int or refund['amount']<=0 or refund.get('currency')!='eur'):
            raise ProviderProbeError('Refund identity mismatch')
        if refund.get('status')=='succeeded':total+=refund['amount']
        elif refund.get('status') not in ('failed','canceled'):raise ProviderProbeError('Pending or unknown provider refund')
    if type(charge.get('amount_refunded')) is not int or total!=charge['amount_refunded'] or not 0<=total<=initial['amount_cents']:
        raise ProviderProbeError('Refund history changed or incomplete')
    disputes=_pages(client,'disputes',headers,{'charge':charge_id})
    for dispute in disputes:
        if dispute.get('charge')!=charge_id or dispute.get('payment_intent')!=observation['payment_intent']:
            raise ProviderProbeError('Dispute identity mismatch')
    # A stable content identity prevents repeated snapshots from funding twice.
    document={'session':session,'charge':charge,'refunds':refunds,'disputes':disputes}
    snapshot=hashlib.sha256(json.dumps(document,sort_keys=True,allow_nan=False).encode()).hexdigest()
    observation={**observation,'charge_id':charge_id,'refunded_minor':total,
                 'dispute_ids':sorted(x['id'] for x in disputes),'snapshot_digest':snapshot}
    with auth.db() as c:
        c.execute('BEGIN IMMEDIATE')
        current=c.execute('SELECT * FROM credit_purchase_orders WHERE id=?',(order_id,)).fetchone()
        immutable=('user_id','amount_cents','session_id','credit_value_micro')
        if current is None or any(current[k]!=initial[k] for k in immutable):raise FenceBlocked('Order changed during provider reconciliation')
        if auth._open(c.execute('SELECT secret_key FROM credit_payment_config WHERE id=1').fetchone()[0])!=key:
            raise FenceBlocked('Provider configuration changed during reconciliation')
        operation='checkout:stripe:'+order_id
        evidence=record_observation(c,operation,observation,evidence_id='stripe:'+snapshot)
        events=[{'id':'reconcile:paid:'+snapshot,'type':'checkout.session.completed','data':{'object':session}},
                {'id':'reconcile:refund:'+snapshot,'type':'charge.refunded','data':{'object':charge}}]
        events.extend({'id':'reconcile:dispute:'+hashlib.sha256((snapshot+x['id']).encode()).hexdigest(),
                       'type':'charge.dispute.updated','created':int(time.time()),'data':{'object':x}} for x in disputes)
        for event in events:
            if event['type']=='charge.dispute.updated':
                previous=c.execute("SELECT normalized_json FROM payment_reconciliation_events WHERE provider='stripe' AND event_id=?",(event['id'],)).fetchone()
                if previous:event['created']=json.loads(previous[0])['event_created']
            raw=json.dumps(event,sort_keys=True,allow_nan=False).encode()
            process_stripe(c,event,raw)
        return {'provider':'stripe','order_id':order_id,'ledger_reconciled':True,
                'evidence_id':evidence['evidence_id'],'snapshot_digest':snapshot,
                'refunds':len(refunds),'disputes':len(disputes),'transition_authorized':False}


def reconcile_paypal(order_id,*,expected_owner=None):
    from . import paypal_payments as paypal
    with auth.db() as c:
        paypal.init(c)
        row=c.execute('SELECT * FROM paypal_orders WHERE id=?',(order_id,)).fetchone();cfg=paypal._keys(c)
        if row is None or (expected_owner is not None and (type(expected_owner) is not int or row['user_id']!=expected_owner)):
            raise ValueError('Payment unavailable')
        order=dict(row)
    if order['environment']!=cfg['environment'] or order['client_fingerprint']!=hashlib.sha256(cfg['client_id'].encode()).hexdigest():
        raise FenceBlocked('PayPal merchant configuration changed')
    pid=_reference(order['provider_order'])
    canonical=paypal._api(cfg,'GET','/v2/checkout/orders/'+pid)
    if canonical.get('status')!='COMPLETED':return _paypal_unpaid(order,cfg,canonical)
    from .paypal_reconciliation import discover
    from .paypal_dispute_history import discover as disputes,record_gap
    try:
        history=discover(canonical,cfg)
        risk_history=disputes(canonical,cfg)
    except (ValueError,KeyError,TypeError,AttributeError) as exc:
        record_gap(order,cfg,getattr(exc,'observed',()))
        raise ValueError('PayPal dispute history is incomplete; refresh or contact the administrator') from None
    try:result=paypal.fulfill(order_id,canonical,_reconciliation=(order,cfg,history),_disputes=risk_history)
    except (FenceBlocked,ValueError):
        record_gap(order,cfg,{x['hold_id'].split(':')[1] for x in risk_history})
        raise
    with auth.db() as c:
        pending=bool(c.execute("SELECT 1 FROM payment_reconciliation_events WHERE provider='paypal' AND order_id=? AND state='pending' LIMIT 1",(order_id,)).fetchone())
    return {**result,'provider':'paypal','ledger_reconciled':result.get('status')=='paid','refunds':len(history),'disputes':len({x['hold_id'].split(':')[1] for x in risk_history}),'financial_review_pending':pending,'history_scope':'known_order_captures_and_disputes','transition_authorized':False}


def _stripe_unpaid(order,key,session,*,client):
    from .checkout_terminal_outcomes import stripe_identity,settle_empty
    stripe_identity(session,order)
    if session.get('status') not in ('open','complete','expired') or session.get('payment_status')!='unpaid':
        raise ProviderProbeError('Unknown or contradictory Stripe checkout state')
    intent=session.get('payment_intent')
    if 'payment_intent' not in session:raise ProviderProbeError('Incomplete Stripe checkout proof')
    headers={'Authorization':'Bearer '+key};terminal=False;outcome='expired';failed_proof=None
    if intent is None:terminal=session['status']=='expired'
    elif session['status'] in ('expired','complete'):
        intent=_reference(intent)
        if not intent.startswith('pi_'):raise ProviderProbeError('Invalid Stripe intent reference')
        document=_get(client,'https://api.stripe.com/v1/payment_intents/'+intent,headers)
        if (document.get('id')!=intent or type(document.get('amount')) is not int or document['amount']!=order['amount_cents']
            or document.get('currency')!='eur'):raise ProviderProbeError('Unpaid Stripe intent identity mismatch')
        if document.get('status')=='canceled':
            if (type(document.get('amount_received')) is not int or document['amount_received']!=0
                or type(document.get('amount_capturable')) is not int or document['amount_capturable']!=0
                or 'latest_charge' not in document):
                raise ProviderProbeError('Canceled Stripe intent has unresolved charge history')
            from .stripe_failed_charge_proof import prove
            charges=_pages(client,'charges',headers,{'payment_intent':intent},max_items=100)
            failed_proof=prove(client,key,intent,order['amount_cents'],document,charges)
            terminal=True;outcome='expired' if session['status']=='expired' else 'canceled_intent'
        elif document.get('status') not in ('requires_payment_method','requires_confirmation','requires_action','processing','requires_capture'):
            raise ProviderProbeError('Contradictory Stripe payment intent status')
    final=_get(client,'https://api.stripe.com/v1/checkout/sessions/'+_reference(order['session_id']),headers)
    if final!=session:raise ProviderProbeError('Stripe unpaid snapshot changed')
    if not terminal:return {'provider':'stripe','order_id':order['id'],'status':'pending','outcome':'provider_pending','checkout_closed':False,'ledger_reconciled':False,'transition_authorized':False}
    with auth.db() as c:
        c.execute('BEGIN IMMEDIATE')
        current=c.execute('SELECT * FROM credit_purchase_orders WHERE id=?',(order['id'],)).fetchone()
        if current is None or any(current[k]!=order[k] for k in ('user_id','amount_cents','session_id','credit_value_micro')):
            raise FenceBlocked('Stripe order changed during terminal readback')
        if auth._open(c.execute('SELECT secret_key FROM credit_payment_config WHERE id=1').fetchone()[0])!=key:
            raise FenceBlocked('Stripe configuration changed during terminal readback')
        return settle_empty(c,'stripe',current,reference=session['id'],outcome=outcome,intent=intent,failed_charge_proof=failed_proof)


def _paypal_unpaid(order,cfg,document):
    from . import paypal_payments as paypal
    from .checkout_terminal_outcomes import paypal_identity,settle_empty
    paypal_identity(document,order)
    if document.get('status') not in ('CREATED','SAVED','APPROVED','VOIDED','PAYER_ACTION_REQUIRED','PENDING_APPROVAL'):
        raise ProviderProbeError('Unknown PayPal checkout state')
    final=paypal._api(cfg,'GET','/v2/checkout/orders/'+_reference(order['provider_order']))
    if final!=document:raise ProviderProbeError('PayPal unpaid snapshot changed')
    if document['status']!='VOIDED':return {'provider':'paypal','order_id':order['id'],'status':'pending','outcome':'provider_pending','checkout_closed':False,'ledger_reconciled':False,'transition_authorized':False}
    with auth.db() as c:
        c.execute('BEGIN IMMEDIATE')
        current=c.execute('SELECT * FROM paypal_orders WHERE id=?',(order['id'],)).fetchone()
        if current is None or any(current[k]!=order[k] for k in ('user_id','kind','period_start','amount_cents','environment','client_fingerprint','provider_order')):
            raise FenceBlocked('PayPal order changed during terminal readback')
        if paypal._keys(c)!=cfg:raise FenceBlocked('PayPal configuration changed during terminal readback')
        return settle_empty(c,'paypal',current,reference=document['id'],outcome='voided')


def reconcile_checkout(provider,order_id,*,expected_owner=None):
    if not isinstance(order_id,str) or not 1<=len(order_id)<=120:raise ValueError('Invalid order ID')
    if expected_owner is not None:
        from .owner_payments import initialize
        with auth.db() as c:
            initialize(c)
            if provider=='stripe':row=c.execute('SELECT user_id,session_id FROM credit_purchase_orders WHERE id=?',(order_id,)).fetchone()
            elif provider=='paypal':row=c.execute('SELECT user_id,provider_order FROM paypal_orders WHERE id=?',(order_id,)).fetchone()
            else:raise ValueError('Payment unavailable')
            if row is None or type(expected_owner) is not int or row[0]!=expected_owner or not row[1]:
                raise ValueError('Payment unavailable')
    if provider=='stripe':
        with httpx.Client(timeout=15,follow_redirects=False) as client:return reconcile_stripe(order_id,client=client,expected_owner=expected_owner)
    if provider=='paypal':return reconcile_paypal(order_id,expected_owner=expected_owner)
    raise ValueError('Unsupported payment provider')
