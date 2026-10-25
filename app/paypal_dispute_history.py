"""Bounded authenticated dispute discovery for the exact captures of one order.

No provider mutation, arbitrary URL following, proportional allocation or payout
inference. Returned records enter the original fulfillment transaction.
"""
from datetime import datetime,timedelta,timezone
import hashlib
import json
import re
import uuid
from urllib.parse import parse_qs,urlencode,urlsplit

from . import paypal_payments as paypal

MAX_DISPUTES=1000
MAX_PAGES=50
MAX_READS=512


class HistoryBlocked(ValueError):
    """Authenticated history cannot safely establish the local money result."""


def identifier(value):
    if not isinstance(value,str) or re.fullmatch(r'[A-Za-z0-9-]{1,100}',value) is None:
        raise HistoryBlocked('Invalid PayPal dispute identity')
    return value


def normalize(document,cfg,*,captures=None):
    if not isinstance(document,dict):raise HistoryBlocked('Malformed PayPal dispute')
    did=identifier(document.get('dispute_id'));transactions=document.get('disputed_transactions')
    if not isinstance(transactions,list) or not 1<=len(transactions)<=100:
        raise HistoryBlocked('Missing or excessive PayPal dispute allocation')
    from .paypal_dispute_details import item_allocations,movement_review
    if any(not isinstance(tx,dict) for tx in transactions):raise HistoryBlocked('Malformed dispute transaction')
    item_amounts,allocation_proof=item_allocations(transactions)
    allocations={}
    for tx in transactions:
        if not isinstance(tx,dict):raise HistoryBlocked('Malformed PayPal dispute transaction')
        cid=tx.get('seller_transaction_id')
        if not isinstance(cid,str) or re.fullmatch(r'[A-Z0-9]{6,64}',cid) is None or cid in allocations:
            raise HistoryBlocked('Invalid or repeated PayPal dispute capture')
        if captures is not None and cid not in captures:raise HistoryBlocked('PayPal dispute crosses the original order')
        if 'gross_amount' in tx and captures is not None and paypal._cents(tx['gross_amount'])!=captures[cid]:
            raise HistoryBlocked('PayPal dispute transaction gross mismatch')
        if item_amounts is not None:amount=item_amounts[cid]
        elif len(transactions)==1:amount=paypal._cents(document.get('dispute_amount'))
        else:
            # Gross transaction amount is not a partial dispute allocation.
            # Only a dispute equal to the full sum has an exact allocation.
            amount=paypal._cents(tx.get('gross_amount'))
            if captures is not None and amount!=captures[cid]:raise HistoryBlocked('PayPal dispute capture gross mismatch')
        if amount<=0 or (captures is not None and amount>captures[cid]):raise HistoryBlocked('Invalid PayPal dispute amount')
        allocations[cid]=amount
    if sum(allocations.values())!=paypal._cents(document.get('dispute_amount')):
        raise HistoryBlocked('Partial multicapture dispute requires exact allocation evidence')
    stamp=document.get('update_time')
    if not isinstance(stamp,str) or re.fullmatch(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,3})?(?:Z|[+-]\d{2}:\d{2})',stamp) is None:
        raise HistoryBlocked('Invalid PayPal dispute update time')
    try:
        moment=datetime.fromisoformat(stamp.replace('Z','+00:00'));origin=datetime(1970,1,1,tzinfo=timezone.utc)
        updated=(moment-origin)//timedelta(milliseconds=1)
    except (ValueError,OverflowError) as exc:raise HistoryBlocked('Invalid PayPal dispute update time') from exc
    if updated<0:raise HistoryBlocked('Invalid PayPal dispute update time')
    state='held'
    if document.get('status')=='RESOLVED':
        outcome=document.get('dispute_outcome',{})
        if not isinstance(outcome,dict):raise HistoryBlocked('Malformed PayPal dispute outcome')
        code=outcome.get('outcome_code')
        if code in ('RESOLVED_SELLER_FAVOUR','CANCELED_BY_BUYER'):state='released'
        elif code=='RESOLVED_BUYER_FAVOUR':state='permanent'
        else:state='uncertain'
        if any(document.get(k) for k in ('money_movements','fund_movements')):state='uncertain'
        if 'amount_refunded' in outcome and paypal._cents(outcome['amount_refunded']) not in (0,sum(allocations.values())):state='uncertain'
    elif document.get('status') not in ('OPEN','WAITING_FOR_BUYER_RESPONSE','WAITING_FOR_SELLER_RESPONSE','UNDER_REVIEW'):
        state='uncertain'
    review=movement_review(document)
    fingerprint=hashlib.sha256(cfg['client_id'].encode()).hexdigest()
    return [{'type':'risk','hold_id':'dispute:'+did+(':'+cid if len(allocations)>1 else ''),
             'capture_id':cid,'amount_minor':amount,'status':state,'updated_ms':updated,'kind':'dispute',
             'environment':cfg['environment'],'merchant_fingerprint':fingerprint,
             **({'allocation_proof':allocation_proof} if allocation_proof else {}),
             **({'movement_review':review} if review else {})}
            for cid,amount in sorted(allocations.items())]


def _read(cfg,path,budget):
    budget[0]+=1
    if budget[0]>MAX_READS:raise HistoryBlocked('PayPal dispute discovery exceeds request bound')
    return paypal._api(cfg,'GET',path)


def _list(cfg,cid,budget,observed):
    items={};page=1;seen=set()
    while page<=MAX_PAGES:
        query={'disputed_transaction_id':cid,'page_size':50,'page':page}
        response=_read(cfg,'/v1/customer/disputes?'+urlencode(query),budget)
        if not isinstance(response,dict) or not isinstance(response.get('items'),list) or len(response['items'])>50:
            raise HistoryBlocked('Incomplete PayPal dispute collection')
        for row in response['items']:
            if not isinstance(row,dict):raise HistoryBlocked('Malformed PayPal dispute collection')
            did=identifier(row.get('dispute_id'));observed.add(did)
            if did in items:raise HistoryBlocked('Repeated PayPal dispute in collection')
            items[did]=row
            if len(items)>MAX_DISPUTES:raise HistoryBlocked('PayPal dispute collection exceeds object bound')
        links=response.get('links',[])
        if not isinstance(links,list) or len(links)>10 or any(not isinstance(x,dict) for x in links):raise HistoryBlocked('Malformed PayPal pagination')
        nextlinks=[x for x in links if x.get('rel')=='next']
        if not nextlinks:return items
        if len(nextlinks)!=1 or not response['items']:raise HistoryBlocked('Invalid PayPal continuation')
        link=nextlinks[0];raw=link.get('href')
        if not isinstance(raw,str) or any(ord(x)<=32 or ord(x)==127 or x=='\\' for x in raw):raise HistoryBlocked('Invalid PayPal continuation URL')
        url=urlsplit(raw);params=parse_qs(url.query,keep_blank_values=True)
        if (url.scheme!='https' or url.netloc!=urlsplit(paypal.BASES[cfg['environment']]).netloc
            or url.path!='/v1/customer/disputes' or url.fragment or link.get('method','GET')!='GET'
            or set(params)!={'disputed_transaction_id','page_size','page'}
            or params['disputed_transaction_id']!=[cid] or params['page_size']!=['50']
            or params['page']!=[str(page+1)] or raw in seen):
            raise HistoryBlocked('PayPal continuation changed the original query')
        seen.add(raw);page+=1
    raise HistoryBlocked('PayPal dispute history exceeds page bound')


def _discover(canonical,cfg,observed):
    captures={x['id']:paypal._cents(x['amount']) for x in canonical['purchase_units'][0]['payments']['captures']}
    budget=[0];first={cid:_list(cfg,cid,budget,observed) for cid in captures};documents={};members={}
    if sum(map(len,first.values()))>2000:raise HistoryBlocked('PayPal dispute references exceed bound')
    for cid,collection in first.items():
        for did,summary in collection.items():
            members.setdefault(did,set()).add(cid)
            if did not in documents:
                if len(documents)>=MAX_DISPUTES:raise HistoryBlocked('PayPal dispute history exceeds object bound')
                detail=_read(cfg,'/v1/customer/disputes/'+did,budget)
                if not isinstance(detail,dict) or detail.get('dispute_id')!=did:raise HistoryBlocked('PayPal dispute readback identity mismatch')
                documents[did]=detail
            detail=documents[did]
            for field in ('status','update_time','dispute_amount'):
                if field not in summary or summary[field]!=detail.get(field):raise HistoryBlocked('PayPal dispute summary changed')
    rows=[]
    for did,detail in documents.items():
        normalized=normalize(detail,cfg,captures=captures)
        if {x['capture_id'] for x in normalized}!=members[did]:raise HistoryBlocked('PayPal filtered dispute collection is incomplete')
        rows.extend(normalized)
    # Re-read every detail and complete filtered collection, including empties.
    for did,detail in documents.items():
        if _read(cfg,'/v1/customer/disputes/'+did,budget)!=detail:raise HistoryBlocked('PayPal dispute changed during discovery')
    if {cid:_list(cfg,cid,budget,observed) for cid in captures}!=first:raise HistoryBlocked('PayPal dispute collection changed during discovery')
    if _read(cfg,'/v2/checkout/orders/'+canonical['id'],budget)!=canonical:raise HistoryBlocked('PayPal order changed during dispute discovery')
    return rows


def discover(canonical,cfg):
    observed=set()
    try:return _discover(canonical,cfg,observed)
    except (ValueError,KeyError,TypeError,AttributeError) as exc:
        blocked=HistoryBlocked('PayPal dispute history cannot be verified')
        blocked.observed=sorted(observed)
        raise blocked from exc


def record_gap(initial,cfg,observed=()):
    """No failed observation is mistaken for a complete financial history."""
    from .payment_reconciliation import record_event
    from .regime_operation_fence import FenceBlocked
    safe={'type':'paypal_history_gap','order_id':initial['id'],'required_dispute_ids':sorted(set(observed)),'environment':cfg['environment'],
          'merchant_fingerprint':hashlib.sha256(cfg['client_id'].encode()).hexdigest()}
    raw=json.dumps(safe,sort_keys=True).encode();event='reconcile:history-gap:'+uuid.uuid4().hex
    with paypal.auth.db() as c:
        c.execute('BEGIN IMMEDIATE')
        current=c.execute('SELECT * FROM paypal_orders WHERE id=?',(initial['id'],)).fetchone()
        if current is None or any(current[k]!=initial[k] for k in ('user_id','kind','period_start','amount_cents','environment','client_fingerprint','provider_order')) or paypal._keys(c)!=cfg:
            raise FenceBlocked('PayPal original order changed during history discovery')
        # One durable gap per original order; a later verified complete snapshot
        # closes it atomically with its actual ledger result.
        from .payment_reconciliation import initialize
        initialize(c)
        for row in c.execute("SELECT normalized_json FROM payment_reconciliation_events WHERE provider='paypal' AND order_id=? AND state='pending'",(initial['id'],)):
            prior=json.loads(row[0])
            if prior.get('type')=='paypal_history_gap' and set(observed)<=set(prior.get('required_dispute_ids',[])):return
        record_event(c,'paypal',event,hashlib.sha256(raw).hexdigest(),safe)
        c.execute("UPDATE payment_reconciliation_events SET state='pending',order_id=? WHERE provider='paypal' AND event_id=?",(initial['id'],event))


def close_gaps(c,local_id):
    from .payment_reconciliation import mark_applied
    for event,raw in c.execute("SELECT event_id,normalized_json FROM payment_reconciliation_events WHERE provider='paypal' AND order_id=? AND state='pending'",(local_id,)).fetchall():
        if json.loads(raw).get('type')=='paypal_history_gap':mark_applied(c,'paypal',event,local_id)
