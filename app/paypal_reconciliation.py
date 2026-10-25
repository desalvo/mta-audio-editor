"""Bounded, read-only PayPal refund discovery before atomic local settlement.

Orders v2 exposes a purchase unit's refund collection; each reference is read
again from Payments v2. Cumulative refund totals detect missing predecessors.
This snapshot does not certify absence of disputes or later provider changes.
"""
import hashlib
import re

from . import paypal_payments as paypal


def _identifier(value):
    if not isinstance(value,str) or re.fullmatch(r'[A-Z0-9]{6,64}',value) is None:
        raise ValueError('Invalid PayPal financial object ID')
    return value


def _payments(order):
    units=order.get('purchase_units')
    if not isinstance(units,list) or len(units)!=1 or not isinstance(units[0],dict):
        raise ValueError('PayPal reconciliation requires one purchase unit')
    payments=units[0].get('payments',{})
    if not isinstance(payments,dict):raise ValueError('Malformed PayPal payments')
    return payments


def discover(canonical,cfg):
    """Return normalized completed refunds; reject incomplete/unstable history."""
    payments=_payments(canonical)
    captures=payments.get('captures',[]);refunds=payments.get('refunds',[])
    if (not isinstance(captures,list) or not 1<=len(captures)<=100
        or not isinstance(refunds,list) or len(refunds)>1000):
        raise ValueError('PayPal history is missing or exceeds reconciliation bound')
    known={};totals={};cumulative={};history=[];seen=set()
    for capture in captures:
        cid=_identifier(capture.get('id'))
        if cid in known:raise ValueError('Repeated PayPal capture')
        actual=paypal._api(cfg,'GET','/v2/payments/captures/'+cid)
        if (actual.get('id')!=cid or actual.get('status')!=capture.get('status')
            or paypal._cents(actual['amount'])!=paypal._cents(capture['amount'])):
            raise ValueError('PayPal capture snapshot changed')
        related=actual.get('supplementary_data',{}).get('related_ids',{}).get('order_id')
        if related is not None and related!=canonical.get('id'):raise ValueError('PayPal capture order mismatch')
        known[cid]=capture;totals[cid]=0;cumulative[cid]=[]
    for refund in refunds:
        rid=_identifier(refund.get('id'))
        if rid in seen:raise ValueError('Repeated PayPal refund')
        seen.add(rid)
        actual=paypal._api(cfg,'GET','/v2/payments/refunds/'+rid)
        if actual.get('id')!=rid or actual.get('status')!=refund.get('status') or paypal._cents(actual['amount'])!=paypal._cents(refund['amount']):
            raise ValueError('PayPal refund snapshot changed')
        cid=paypal._refund_capture(actual,cfg['environment'])
        if cid not in known:raise ValueError('PayPal refund belongs to another capture')
        status=actual.get('status')
        if status in ('FAILED','CANCELLED'):continue
        if status!='COMPLETED':raise ValueError('Pending or unknown PayPal refund')
        amount=paypal._cents(actual['amount'])
        if amount<=0:raise ValueError('Invalid PayPal refund amount')
        total=paypal._cents(actual.get('seller_payable_breakdown',{}).get('total_refunded_amount',{}))
        if total<amount:raise ValueError('Invalid cumulative PayPal refund amount')
        totals[cid]+=amount;cumulative[cid].append(total)
        history.append({'type':'refund','refund_id':rid,'capture_id':cid,'amount_minor':amount,
                        'environment':cfg['environment'],
                        'merchant_fingerprint':hashlib.sha256(cfg['client_id'].encode()).hexdigest()})
    for cid,capture in known.items():
        gross=paypal._cents(capture['amount']);refunded=totals[cid];status=capture.get('status')
        if (gross<=0 or not 0<=refunded<=gross or (refunded and max(cumulative[cid])!=refunded)
            or (status=='COMPLETED' and refunded!=0)
            or (status=='PARTIALLY_REFUNDED' and not 0<refunded<gross)
            or (status=='REFUNDED' and refunded!=gross)
            or status not in ('COMPLETED','PARTIALLY_REFUNDED','REFUNDED')):
            raise ValueError('PayPal refund history changed or incomplete')
    # Repeat the order read after object discovery. A changed collection cannot
    # be quietly accepted, even if individual objects were valid when fetched.
    final=paypal._api(cfg,'GET','/v2/checkout/orders/'+_identifier(canonical.get('id')))
    if final!=canonical:raise ValueError('PayPal order changed during historical discovery')
    return sorted(history,key=lambda item:item['refund_id'])
