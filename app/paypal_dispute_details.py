"""Exact item allocations and private diagnostic movement observations.

A movement's initiation time is not completion proof. No function here releases
funds, estimates an allocation or treats a fee as customer credit.
"""
from datetime import datetime,timedelta,timezone
import hashlib
import json
import re


def _digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()


def item_allocations(transactions):
    from .paypal_dispute_history import HistoryBlocked
    from .paypal_payments import _cents
    supplied=['items' in row for row in transactions]
    if not any(supplied):return None,None
    if not all(supplied):raise HistoryBlocked('Incomplete per-capture disputed-item allocation')
    seen=set();rows=[];amounts={}
    for tx in transactions:
        items=tx['items']
        if not isinstance(items,list) or not 1<=len(items)<=100:raise HistoryBlocked('Invalid disputed-item collection')
        cid=tx.get('seller_transaction_id');amount=0
        for item in items:
            if not isinstance(item,dict):raise HistoryBlocked('Invalid disputed item')
            key=item.get('item_id')
            if not isinstance(key,str) or not 1<=len(key)<=255 or any(ord(c)<32 or ord(c)==127 for c in key) or key in seen:
                raise HistoryBlocked('Missing or repeated disputed-item identity')
            seen.add(key)
            quantity=item.get('item_quantity')
            if quantity is not None and (not isinstance(quantity,str) or re.fullmatch(r'[1-9][0-9]{0,9}',quantity) is None):
                raise HistoryBlocked('Invalid disputed-item quantity')
            cents=_cents(item.get('dispute_amount'))
            if cents<=0:raise HistoryBlocked('Invalid disputed-item amount')
            # The field is already the disputed amount of this item. Quantity
            # does not authorize multiplying the provider's monetary evidence.
            amount+=cents;rows.append((cid,key,cents))
        if len(rows)>1000:raise HistoryBlocked('Disputed-item allocation exceeds bound')
        amounts[cid]=amount
    return amounts,{'method':'provider_item_amounts','item_count':len(rows),'sha256':_digest(sorted(rows))}


def movement_review(document):
    from .paypal_dispute_history import HistoryBlocked
    from .paypal_payments import _cents
    outcome=document.get('dispute_outcome',{})
    if not isinstance(outcome,dict):raise HistoryBlocked('Malformed dispute outcome')
    for key in ('money_movements','fund_movements'):
        if key in document and (not isinstance(document[key],list) or len(document[key])>50):
            raise HistoryBlocked('Invalid PayPal movement collection')
    present=[key for key in ('money_movements','fund_movements') if document.get(key)]
    if not present and outcome.get('outcome_code')!='RESOLVED_WITH_PAYOUT':return None
    result=[];warnings=set()
    for source in present:
        rows=document[source]
        if not isinstance(rows,list) or not 1<=len(rows)<=50:raise HistoryBlocked('Invalid PayPal movement collection')
        for row in rows:
            if not isinstance(row,dict):raise HistoryBlocked('Invalid PayPal movement')
            party=row.get('party' if source=='fund_movements' else 'affected_party')
            direction=row.get('type');reason=row.get('reason')
            if party not in ('SELLER','BUYER','PAYMENT_PROCESSOR'):party='UNKNOWN';warnings.add('unsupported_or_missing_party')
            if direction not in ('DEBIT','CREDIT'):direction='UNKNOWN';warnings.add('unsupported_or_missing_direction')
            if reason not in ('DISPUTE_SETTLEMENT','DISPUTE_SETTLEMENT_FEE','DISPUTE_FEE','CHARGEBACK_FEE','REVERSED_TRANSACTION_FEE'):
                reason='UNKNOWN';warnings.add('unsupported_or_missing_reason')
            cents=None
            if 'amount' in row:cents=_cents(row['amount'])
            else:warnings.add('missing_fiat_amount')
            if row.get('asset'):warnings.add('unsupported_asset')
            stamp=row.get('initiated_time');initiated=None
            if isinstance(stamp,str) and re.fullmatch(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,3})?(?:Z|[+-]\d{2}:\d{2})',stamp):
                try:initiated=(datetime.fromisoformat(stamp.replace('Z','+00:00'))-datetime(1970,1,1,tzinfo=timezone.utc))//timedelta(milliseconds=1)
                except (ValueError,OverflowError):pass
            if initiated is None or initiated<0:initiated=None;warnings.add('missing_or_invalid_initiation')
            result.append({'source':source,'party':party,'direction':direction,'reason':reason,
                           'amount_minor':cents,'amount_minor_text':str(cents) if cents is not None else None,'currency':'EUR' if cents is not None else None,'initiated_ms':initiated})
    if not result:warnings.add('payout_without_movement_details')
    # Both old and new arrays may describe the same transfer; no sum/deduplication
    # is asserted, and neither array binds a completed transaction identifier.
    return {'schema':'paypal-movement-review-1','settlement_proven':False,'reason':'completion_and_unique_transaction_binding_missing',
            'evidence_sha256':_digest({key:document.get(key) for key in ('money_movements','fund_movements','dispute_outcome')}),
            'observations':result,'warnings':sorted(warnings)}


def admin_reviews(c,order_id):
    """Bounded safe observations only; never return the provider's documents."""
    from .regime_operation_fence import FenceBlocked
    rows=c.execute("SELECT event_id,normalized_json,state FROM payment_reconciliation_events WHERE provider='paypal' AND order_id=? ORDER BY created_at DESC,event_id DESC LIMIT 201",(order_id,)).fetchall()
    result=[];seen=set()
    for row in rows[:200]:
        data=json.loads(row[1])
        if not isinstance(data,dict):raise FenceBlocked('Movement observation journal cannot be verified')
        review=data.get('movement_review')
        if review is None:continue
        if (not isinstance(review,dict) or review.get('schema')!='paypal-movement-review-1' or review.get('settlement_proven') is not False
            or not isinstance(review.get('observations'),list) or len(review['observations'])>100
            or not re.fullmatch(r'[a-f0-9]{64}',str(review.get('evidence_sha256','')))):
            raise FenceBlocked('Movement observation journal cannot be verified')
        key=review['evidence_sha256']
        if key in seen:continue
        seen.add(key)
        # Persisted fields originate solely from movement_review's fixed DTO.
        # Revalidate on read too, so corruption never reaches an admin renderer.
        safe=[]
        for item in review['observations']:
            if (not isinstance(item,dict) or item.get('source') not in ('money_movements','fund_movements')
                or item.get('party') not in ('SELLER','BUYER','PAYMENT_PROCESSOR','UNKNOWN')
                or item.get('direction') not in ('DEBIT','CREDIT','UNKNOWN')
                or item.get('reason') not in ('DISPUTE_SETTLEMENT','DISPUTE_SETTLEMENT_FEE','DISPUTE_FEE','CHARGEBACK_FEE','REVERSED_TRANSACTION_FEE','UNKNOWN')
                or (item.get('amount_minor') is not None and (type(item['amount_minor']) is not int or item['amount_minor']<0 or item.get('currency')!='EUR'))
                or item.get('amount_minor_text')!=(str(item['amount_minor']) if item.get('amount_minor') is not None else None)
                or (item.get('initiated_ms') is not None and (type(item['initiated_ms']) is not int or not 0<=item['initiated_ms']<=253402300799999))):
                raise FenceBlocked('Movement observation fields cannot be verified')
            safe.append({key:item.get(key) for key in ('source','party','direction','reason','amount_minor','amount_minor_text','currency','initiated_ms')})
        result.append({'event_id':row[0],'pending':row[2]=='pending','updated_ms':data.get('updated_ms'),
                       'settlement_proven':False,'evidence_sha256':key,'observations':safe})
        if len(result)==20:break
    return {'items':result,'scope':'canonical_dispute_observations_only','settlement_proven':False,
            'truncated':len(rows)>200 or len(result)==20}
