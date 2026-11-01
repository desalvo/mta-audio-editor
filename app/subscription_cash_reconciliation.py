"""Authenticated complete cash readback for one original subscription payment.

No uploaded observation, amount, caller date range or T-code alone can collect
money. The exact canonical captures, completed refunds, final cases, original
quote, provider freshness and two complete balance-affecting scans must agree.
"""
from datetime import datetime, timedelta, timezone
import hashlib
import json
import re
import time
from urllib.parse import urlencode

from . import auth, paypal_payments as paypal
from .regime_operation_fence import FenceBlocked

MAX_READS = 256
MAX_SECONDS = 90
MAX_WINDOWS = 36
MAX_ROWS = 10000
_TYPE = 'subscription_cash_position'
_MOVEMENT = 'subscription_cash_movement'


def _encode(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False)


def _sha(value):
    return hashlib.sha256(_encode(value).encode()).hexdigest()


def _instant(value):
    if not isinstance(value,str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|[+-]\d{2}:\d{2})',value):
        raise ValueError('Verified reporting timestamp required')
    return datetime.fromisoformat(value.replace('Z','+00:00'))


def _stamp(value):
    return value.astimezone(timezone.utc).isoformat(timespec='seconds').replace('+00:00','Z')


def journal_version(c,order_id):
    """Include previously unbound evidence for the exact original captures."""
    captures={r[0] for r in c.execute('SELECT id FROM paypal_captures WHERE order_id=?',(order_id,))}
    rows=[]
    if not c.execute("SELECT 1 FROM sqlite_master WHERE name='payment_reconciliation_events'").fetchone():return _sha(rows)
    for eid,digest,raw,state,oid in c.execute("SELECT event_id,digest,normalized_json,state,order_id FROM payment_reconciliation_events WHERE provider='paypal' ORDER BY event_id"):
        data=json.loads(raw)
        if data.get('type') in (_TYPE,_MOVEMENT,'paypal_cash_position'):continue
        if oid==order_id or data.get('capture_id') in captures:
            rows.append((eid,digest,state,oid))
    return _sha(rows)


def position(c,order):
    """Validate the latest immutable proof against current source evidence."""
    if not c.execute("SELECT 1 FROM sqlite_master WHERE name='payment_reconciliation_events'").fetchone():return None
    from . import paypal_cash_history
    if paypal_cash_history.has_receipt(c,order['id']):return paypal_cash_history.position(c,order)
    candidates=[]
    for raw,digest in c.execute("SELECT normalized_json,digest FROM payment_reconciliation_events WHERE provider='paypal' AND order_id=? AND state='applied'",(order['id'],)):
        value=json.loads(raw)
        if value.get('type')!=_TYPE:continue
        if (_sha(value)!=digest or value.get('schema')!='mta-subscription-cash-position-1'
                or value.get('order_id')!=order['id'] or value.get('user_id')!=order['user_id']
                or value.get('environment')!=order['environment'] or value.get('merchant_fingerprint')!=order['client_fingerprint']):
            raise FenceBlocked('Original subscription cash receipt cannot be verified')
        candidates.append(value)
    if not candidates:return None
    from .subscription_receivables import original_quote
    basis=original_quote(c,order)
    current=journal_version(c,order['id'])
    candidates=[x for x in candidates if x.get('basis')==basis and x.get('journal_version')==current]
    if not candidates:return None
    latest=max(_instant(x['end_date']) for x in candidates)
    candidates=[x for x in candidates if _instant(x['end_date'])==latest]
    if len({x['source_sha256'] for x in candidates})!=1:raise FenceBlocked('Conflicting subscription cash snapshots')
    value=candidates[0]
    target=value.get('fee_loss_micro');surplus=value.get('remaining_surplus_micro')
    if (type(target) is not int or not 0<=target<=basis['fee_micro'] or type(surplus) is not int
            or not 0<=surplus<=basis['surplus_micro'] or value.get('source_sha256')!=_sha(value.get('movements'))):
        raise FenceBlocked('Original subscription cash totals cannot be verified')
    loss=(order['amount_cents']-sum(_money(row) for row in value['movements']))*10000
    if (not 0<=loss<=basis['gross_micro'] or target!=min(basis['fee_micro'],max(0,loss-basis['surplus_micro']))
            or surplus!=max(0,basis['surplus_micro']-loss)):
        raise FenceBlocked('Subscription cash receipt does not conserve original principal')
    for row in value['movements']:
        claim=_movement_claim(order,row)
        stored=c.execute("SELECT digest,normalized_json,state,order_id FROM payment_reconciliation_events WHERE provider='paypal' AND event_id=?",('reconcile:subscription-movement:'+row['transaction_id'],)).fetchone()
        binding=c.execute("SELECT order_id FROM payment_reconciliation_objects WHERE provider='paypal' AND object_id=?",('cash-movement:'+row['transaction_id'],)).fetchone()
        if tuple(stored or ())!=(_sha(claim),_encode(claim),'applied',order['id']) or tuple(binding or ())!=(order['id'],):
            raise FenceBlocked('Subscription cash movement claim cannot be verified')
    return value


def _movement_claim(order,row):
    return {'type':_MOVEMENT,'order_id':order['id'],'user_id':order['user_id'],
            'environment':order['environment'],'merchant_fingerprint':order['client_fingerprint'],
            'movement':{k:row.get(k) for k in ('transaction_id','event_code','paypal_reference_id','paypal_reference_id_type','currency','amount')}}


def has_receipt(c,order_id):
    if not c.execute("SELECT 1 FROM sqlite_master WHERE name='payment_reconciliation_events'").fetchone():return False
    return any(json.loads(row[0]).get('type') in (_TYPE,'paypal_cash_position') for row in c.execute("SELECT normalized_json FROM payment_reconciliation_events WHERE provider='paypal' AND order_id=? AND state='applied'",(order_id,)))


def _collect(cfg,start,end,account,budget):
    """Never filter by transaction ID: every related cash movement must appear."""
    from .paypal_merchant_history import normalize
    result={};left=start;windows=0
    while left<end:
        windows+=1
        if windows>MAX_WINDOWS:raise ValueError('Original subscription exceeds reporting history bound')
        right=min(left+timedelta(days=31),end);page=1;expected=None;seen={}
        while True:
            budget[0]+=1
            if budget[0]>MAX_READS or time.monotonic()>budget[1]:raise ValueError('Subscription cash readback budget exhausted')
            query={'start_date':_stamp(left),'end_date':_stamp(right),'fields':'transaction_info',
                   'balance_affecting_records_only':'Y','page_size':100,'page':page}
            response=paypal._api(cfg,'GET','/v1/reporting/transactions?'+urlencode(query))
            if time.monotonic()>budget[1]:raise ValueError('Subscription cash readback deadline exceeded')
            if (not isinstance(response,dict) or response.get('account_number')!=account
                    or _instant(response.get('start_date'))!=left or _instant(response.get('end_date'))!=right
                    or _instant(response.get('last_refreshed_datetime'))<end):
                raise ValueError('Complete fresh original-merchant reporting required')
            count=response.get('total_items');pages=response.get('total_pages');data=response.get('transaction_details')
            if (type(count) is not int or not 0<=count<=MAX_ROWS or type(pages) is not int
                    or pages not in ({0,1} if count==0 else {(count+99)//100})
                    or response.get('page')!=page or type(response.get('page')) is not int
                    or not isinstance(data,list) or len(data)>100 or page>max(1,pages)):
                raise ValueError('Complete subscription cash pages required')
            signature=(count,pages,response['last_refreshed_datetime'])
            if expected is None:expected=signature
            if expected!=signature:raise ValueError('Subscription reporting changed during paging')
            for raw in data:
                row=normalize(raw);identifier=row['transaction_id']
                row.pop('paypal_account_id',None)
                if identifier in seen:raise ValueError('Reporting transaction identity is ambiguous')
                initiated=_instant(row.get('transaction_initiation_date'));updated=_instant(row.get('transaction_updated_date'))
                if not left<=initiated<=right or updated<initiated or updated>end:
                    raise ValueError('Reporting movement lies outside verified history')
                seen[identifier]=row
            if page==max(1,pages):
                if len(seen)!=count:raise ValueError('Subscription cash history is incomplete')
                break
            if len(data)!=100:raise ValueError('Subscription cash page is incomplete')
            page+=1
        for key,row in seen.items():
            if key in result and result[key]!=row:raise ValueError('Reporting identity changed across windows')
            result[key]=row
        if len(result)>MAX_ROWS:raise ValueError('Subscription cash history exceeds bound')
        left=right
    return sorted(result.values(),key=lambda x:x['transaction_id'])


def _money(row):
    value=row['amount'];negative=value.startswith('-')
    n=paypal._cents({'currency_code':row['currency'],'value':value[1:] if negative else value})
    return -n if negative else n


def _fee(code):
    return re.fullmatch(r'T01\d{2}',code) is not None or code in ('T1108','T1109')


def _principal(rows,canonical,refunds,risks,required_losses):
    units=canonical['purchase_units'];payments=units[0]['payments']
    captures={x['id']:paypal._cents(x['amount']) for x in payments['captures']}
    known_refunds={x['refund_id']:(x['capture_id'],x['amount_minor']) for x in refunds}
    if any(x['status'] not in ('released','permanent') for x in risks):
        raise ValueError('Resolve provisional or ambiguous subscription disputes first')
    by_id={x['transaction_id']:x for x in rows};selected={};related=set(captures)
    # Follow provider-owned references only, including adjustments to prior
    # movements. Payer-controlled invoice/subject/note fields are never links.
    children={}
    for row in rows:children.setdefault(row.get('paypal_reference_id'),[]).append(row)
    pending=list(captures)
    while pending:
        for row in children.get(pending.pop(),[]):
            if row['transaction_id'] in related:continue
            if row.get('paypal_reference_id_type')!='TXN':raise ValueError('Subscription movement reference type is not verified')
            related.add(row['transaction_id']);pending.append(row['transaction_id'])
    root={};totals={cid:0 for cid in captures};debits={cid:0 for cid in captures}
    temporary={cid:0 for cid in captures};reported_refunds=set()
    for identifier in sorted(related):
        row=by_id.get(identifier)
        if row is None:raise ValueError('Original subscription capture missing from reporting')
        if row['currency']!='EUR' or row['status'] not in ('S','V'):
            raise ValueError('Completed EUR subscription movements required')
        amount=_money(row);code=row['event_code']
        if identifier in captures:
            if code!='T0006' or amount!=captures[identifier]:raise ValueError('Reporting capture does not match original payment')
            if (row.get('paypal_reference_id_type'),row.get('paypal_reference_id')) not in {('ODR',canonical['id']),('TXN',identifier)}:
                raise ValueError('Reporting capture does not bind the original order')
            root[identifier]=identifier
        else:
            parent=row.get('paypal_reference_id')
            # Resolve any depth without relying on lexical transaction IDs.
            visited={identifier}
            while parent not in captures:
                if parent in visited or parent not in by_id:raise ValueError('Subscription movement reference is cyclic or incomplete')
                visited.add(parent);previous=by_id[parent]
                if _fee(previous['event_code']):raise ValueError('Fee adjustment cannot become subscription principal')
                if previous.get('paypal_reference_id_type')!='TXN':raise ValueError('Subscription movement has no original capture')
                parent=previous.get('paypal_reference_id')
            root[identifier]=parent
            if _fee(code):continue  # provider fees never become customer principal
            if code=='T1107':
                if known_refunds.get(identifier)!=(parent,-amount) or amount>=0:raise ValueError('Reporting refund contradicts canonical history')
                reported_refunds.add(identifier)
            elif code in ('T1106','T1201','T1207'):
                if amount>=0:raise ValueError('Subscription loss debit direction required')
                debits[parent]-=amount
            elif code in ('T1202','T1205'):
                if amount<=0:raise ValueError('Subscription reimbursement credit direction required')
            elif code=='T1208':
                if not amount:raise ValueError('Subscription adjustment amount required')
            elif code in ('T1110','T1111'):
                if (code=='T1110' and amount>=0) or (code=='T1111' and amount<=0):
                    raise ValueError('Temporary subscription hold direction is not verified')
                temporary[parent]+=amount
            else:raise ValueError('Unclassified subscription principal movement')
        selected[identifier]=row;totals[root[identifier]]+=amount
    if reported_refunds!=set(known_refunds):raise ValueError('Reporting omits a canonical subscription refund')
    for cid,gross in captures.items():
        if temporary[cid]:raise ValueError('Temporary subscription cash holds require resolution')
        expected=max(required_losses.get(cid,0),sum(x['amount_minor'] for x in risks if x['capture_id']==cid and x['status']=='permanent'))
        refunded=sum(amount for capture,amount in known_refunds.values() if capture==cid)
        # A final reversal can subsume an already completed refund. Require
        # coverage of the loss once, using actual cash rather than adding holds.
        if debits[cid]<max(0,min(gross,expected)-refunded):raise ValueError('Reporting omits a known subscription loss movement')
        if not 0<=totals[cid]<=gross:raise ValueError('Subscription cash principal is not conserved')
        if by_id[cid]['status']=='V' and totals[cid]==gross:raise ValueError('Reversed capture lacks its actual debit')
    return sum(captures.values())-sum(totals.values()),[selected[k] for k in sorted(selected)]


def reconcile(order_id,*,expected_owner=None):
    """GET-only provider proof, followed by one original-account transaction."""
    from .subscription_receivables import original_quote,accrue_original_loss,sync
    with auth.db() as c:
        order=c.execute('SELECT * FROM paypal_orders WHERE id=?',(order_id,)).fetchone();cfg=paypal._keys(c)
        if order is None or order['kind']!='subscription' or order['status']!='paid' or (expected_owner is not None and (type(expected_owner) is not int or expected_owner!=order['user_id'])):
            raise ValueError('Original paid subscription unavailable')
        order=dict(order);basis=original_quote(c,order);version=journal_version(c,order_id)
        required={}
        if c.execute("SELECT 1 FROM sqlite_master WHERE name='paypal_financial_holds'").fetchone():
            for cid,amount in c.execute("SELECT capture_id,max(amount_cents) FROM paypal_financial_holds WHERE order_id=? AND status='permanent' GROUP BY capture_id",(order_id,)):
                required[cid]=amount
        observed=max((created for eid,raw,created in c.execute("SELECT event_id,normalized_json,created_at FROM payment_reconciliation_events WHERE provider='paypal' AND order_id=?",(order_id,))
                      if not eid.startswith('reconcile:') and json.loads(raw).get('type') in ('risk','refund','capture')),default=0)
    if (cfg['environment'],hashlib.sha256(cfg['client_id'].encode()).hexdigest())!=(order['environment'],order['client_fingerprint']):
        raise FenceBlocked('Original subscription merchant required')
    end=datetime.fromtimestamp(int(time.time())-3*3600,timezone.utc)
    start=datetime.fromtimestamp(order['created_at']-300,timezone.utc)
    if not start<end or observed>end.timestamp():raise ValueError('Subscription movements are not yet covered by reporting freshness')
    pid=order['provider_order'];canonical=paypal._api(cfg,'GET','/v2/checkout/orders/'+pid)
    if canonical.get('id')!=pid or canonical.get('status')!='COMPLETED':raise ValueError('Original completed subscription required')
    units=canonical.get('purchase_units')
    if not isinstance(units,list) or len(units)!=1 or units[0].get('custom_id')!=order_id or units[0].get('reference_id')!=order_id or paypal._cents(units[0]['amount'])!=order['amount_cents']:
        raise ValueError('Original subscription identity mismatch')
    account=units[0].get('payee',{}).get('merchant_id')
    if not isinstance(account,str) or not account:raise ValueError('Canonical subscription merchant account required')
    from .paypal_reconciliation import discover
    from .paypal_dispute_history import discover as discover_risks
    refunds=discover(canonical,cfg);risks=discover_risks(canonical,cfg)
    if any(x['updated_ms']>end.timestamp()*1000 for x in risks):raise ValueError('Subscription case is newer than reporting coverage')
    with auth.db() as c:
        stored={row[0]:row[1] for row in c.execute('SELECT id,amount_cents FROM paypal_captures WHERE order_id=?',(order_id,))}
    actual={row['id']:paypal._cents(row['amount']) for row in units[0]['payments']['captures']}
    if stored!=actual or sum(actual.values())!=order['amount_cents']:raise FenceBlocked('Original subscription captures changed')
    budget=[0,time.monotonic()+MAX_SECONDS]
    first=_collect(cfg,start,end,account,budget);second=_collect(cfg,start,end,account,budget)
    if first!=second:raise FenceBlocked('Subscription cash history changed during readback')
    loss,movements=_principal(first,canonical,refunds,risks,required)
    if (paypal._api(cfg,'GET','/v2/checkout/orders/'+pid)!=canonical
            or discover(canonical,cfg)!=refunds or discover_risks(canonical,cfg)!=risks):
        raise FenceBlocked('Subscription canonical history changed during cash readback')
    gross=loss*10000;target=min(basis['fee_micro'],max(0,gross-basis['surplus_micro']))
    value={'type':_TYPE,'schema':'mta-subscription-cash-position-1','order_id':order_id,'user_id':order['user_id'],
           'environment':cfg['environment'],'merchant_fingerprint':order['client_fingerprint'],'account':account,
           'start_date':_stamp(start),'end_date':_stamp(end),'basis':basis,'journal_version':version,
           'movements':movements,'source_sha256':_sha(movements),'fee_loss_micro':target,
           'remaining_surplus_micro':max(0,basis['surplus_micro']-gross)}
    with auth.db() as c:
        c.execute('BEGIN IMMEDIATE');current=c.execute('SELECT * FROM paypal_orders WHERE id=?',(order_id,)).fetchone()
        if current is None or any(current[k]!=order[k] for k in order if k!='refund_due_micro') or paypal._keys(c)!=cfg or journal_version(c,order_id)!=version:
            raise FenceBlocked('Original subscription changed during cash readback')
        if original_quote(c,current)!=basis:raise FenceBlocked('Original subscription quote changed during cash readback')
        from .regime_checkout_fence import verify_enrolled_payment
        verify_enrolled_payment(c,'paypal',order_id)
        from .payment_reconciliation import record_event,mark_applied,bind_object
        for row in movements:
            mid=row['transaction_id'];bind_object(c,'paypal','cash-movement:'+mid,order_id)
            claim=_movement_claim(current,row);eid='reconcile:subscription-movement:'+mid
            record_event(c,'paypal',eid,_sha(claim),claim);mark_applied(c,'paypal',eid,order_id)
        resolved=[]
        # A conflicting final case remains in the immutable audit. Only this
        # complete, fresh cash proof can settle its financial consequence; the
        # old final hold is never used to collect the same principal twice.
        final_cases={row['hold_id']:row for row in risks}
        for eid,digest,raw,oid in c.execute("SELECT event_id,digest,normalized_json,order_id FROM payment_reconciliation_events WHERE provider='paypal' AND state='pending'").fetchall():
            data=json.loads(raw)
            if oid!=order_id and data.get('capture_id') not in actual:continue
            if data.get('type')!='risk':continue
            final=final_cases.get(data.get('hold_id'))
            if (oid not in (None,order_id) or final is None or data.get('kind')!='dispute' or final['status'] not in ('released','permanent')
                    or any(data.get(k)!=final[k] for k in ('hold_id','capture_id','amount_minor','environment','merchant_fingerprint'))
                    or type(data.get('updated_ms')) is not int or data['updated_ms']>final['updated_ms']):
                raise FenceBlocked('Pending subscription risk is not covered by final canonical cash proof')
            mark_applied(c,'paypal',eid,order_id);resolved.append((eid,digest))
        value['journal_version']=journal_version(c,order_id)
        value['resolved_risk_events']=sorted(resolved)
        prior=position(c,current)
        event='reconcile:subscription-cash:'+_sha(value)
        if prior is None or prior['source_sha256']!=value['source_sha256']:
            record_event(c,'paypal',event,_sha(value),value);mark_applied(c,'paypal',event,order_id)
        paypal._record_position(c,current,'capture:'+pid)
        accrue_original_loss(c,current,event);sync(c)
        pending=bool(c.execute("SELECT 1 FROM payment_reconciliation_events WHERE provider='paypal' AND order_id=? AND state='pending'",(order_id,)).fetchone())
    return {'original_subscription_loss_reconciled':True,'financial_review_pending':pending,
            'fee_loss_micro':target,'cash_history_end':_stamp(end),'transition_authorized':False}
