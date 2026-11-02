"""Complete authenticated original-payment cash, independent of payout labels.

Raw final case documents prove scope/finality, never money or guessed per-case
allocations. The existing bounded merchant reader proves exact capture cash.
All effects, unique claims and evidence closure commit with ordinary funding.
"""
from datetime import datetime, timezone
import hashlib
import json
import time

from . import auth, paypal_payments as paypal, subscription_cash_reconciliation as cash
from .regime_operation_fence import FenceBlocked

TYPE='paypal_cash_position'
SCHEMA='mta-paypal-cash-position-1'


def has_receipt(c,oid):
    if not c.execute("SELECT 1 FROM sqlite_master WHERE name='payment_reconciliation_events'").fetchone():return False
    found = False
    for row in c.execute("SELECT normalized_json FROM payment_reconciliation_events WHERE provider='paypal' AND order_id=? AND state='applied'",(oid,)):
        try:
            evidence = json.loads(row[0])
        except (ValueError, TypeError) as exc:
            raise FenceBlocked('Original PayPal evidence cannot be verified') from exc
        if not isinstance(evidence, dict):
            raise FenceBlocked('Original PayPal evidence cannot be verified')
        found = found or evidence.get('type') == TYPE
    return found


def position(c,order):
    if not has_receipt(c,order['id']):return None
    values=[]
    for raw,digest in c.execute("SELECT normalized_json,digest FROM payment_reconciliation_events WHERE provider='paypal' AND order_id=? AND state='applied'",(order['id'],)):
        p=json.loads(raw)
        if p.get('type')!=TYPE:continue
        if (cash._sha(p)!=digest or p.get('schema')!=SCHEMA
                or any(p.get(k)!=order[v] for k,v in [('order_id','id'),('user_id','user_id'),('kind','kind'),('environment','environment'),('merchant_fingerprint','client_fingerprint')])):
            raise FenceBlocked('Original PayPal cash proof cannot be verified')
        if p.get('journal_version')==cash.journal_version(c,order['id']):values.append(p)
    if not values:return None
    end=max(cash._instant(x['end_date']) for x in values);values=[x for x in values if cash._instant(x['end_date'])==end]
    if len({x['source_sha256'] for x in values})!=1:raise FenceBlocked('Conflicting original PayPal cash proof')
    p=values[0];net=sum(cash._money(row) for row in p['movements'])
    stored={x[0]:x[1] for x in c.execute('SELECT id,amount_cents FROM paypal_captures WHERE order_id=?',(order['id'],))}
    if (p.get('captures')!=stored or p['source_sha256']!=cash._sha(p['movements'])
            or type(p.get('net_minor')) is not int or net!=p['net_minor'] or not 0<=net<=order['amount_cents']):
        raise FenceBlocked('Original PayPal cash principal changed')
    for did,case in p['cases'].items():
        value={'type':'paypal_cash_case','order_id':order['id'],'case_id':did,**case}
        claim=c.execute("SELECT digest,normalized_json,state,order_id FROM payment_reconciliation_events WHERE provider='paypal' AND event_id=?",('reconcile:cash-case:'+cash._sha(value),)).fetchone()
        binding=c.execute("SELECT order_id FROM payment_reconciliation_objects WHERE provider='paypal' AND object_id=?",('cash-case:'+did,)).fetchone()
        if tuple(claim or ())!=(cash._sha(value),cash._encode(value),'applied',order['id']) or tuple(binding or ())!=(order['id'],):
            raise FenceBlocked('Original PayPal case claim changed')
    for row in p['movements']:
        claim=cash._movement_claim(order,row)
        event=c.execute("SELECT digest,normalized_json,state,order_id FROM payment_reconciliation_events WHERE provider='paypal' AND event_id=?",('reconcile:subscription-movement:'+row['transaction_id'],)).fetchone()
        binding=c.execute("SELECT order_id FROM payment_reconciliation_objects WHERE provider='paypal' AND object_id=?",('cash-movement:'+row['transaction_id'],)).fetchone()
        if tuple(event or ())!=(cash._sha(claim),cash._encode(claim),'applied',order['id']) or tuple(binding or ())!=(order['id'],):
            raise FenceBlocked('Original PayPal cash movement claim changed')
    if order['kind']=='subscription':
        from .subscription_receivables import original_quote
        basis=original_quote(c,order);loss=(order['amount_cents']-net)*10000
        if (p.get('basis')!=basis or p.get('fee_loss_micro')!=min(basis['fee_micro'],max(0,loss-basis['surplus_micro']))
                or p.get('remaining_surplus_micro')!=max(0,basis['surplus_micro']-loss)):
            raise FenceBlocked('Original PayPal fee conservation changed')
    return p


def _cases(documents,captures,end):
    from .paypal_dispute_details import item_allocations,movement_review
    result={}
    for did,doc in documents.items():
        stamp=cash._instant(doc.get('update_time'))
        outcome=doc.get('dispute_outcome',{})
        if (doc.get('status')!='RESOLVED' or not isinstance(outcome,dict)
                or outcome.get('outcome_code') not in ('RESOLVED_BUYER_FAVOUR','RESOLVED_SELLER_FAVOUR','CANCELED_BY_BUYER','RESOLVED_WITH_PAYOUT') or stamp>end):
            raise ValueError('Final PayPal case within reporting coverage required')
        tx=doc['disputed_transactions'];ids=[x['seller_transaction_id'] for x in tx]
        if any(cid not in captures for cid in ids):raise FenceBlocked('PayPal case crosses original payment')
        total=paypal._cents(doc.get('dispute_amount'))
        if not 0<total<=sum(captures[cid] for cid in ids):raise ValueError('Invalid final PayPal dispute principal')
        for x in tx:
            if 'gross_amount' in x and paypal._cents(x['gross_amount'])!=captures[x['seller_transaction_id']]:raise ValueError('PayPal case capture gross mismatch')
        items,_=item_allocations(tx)
        if items is not None and (sum(items.values())!=total or any(not 0<items[cid]<=captures[cid] for cid in ids)):
            raise ValueError('Contradictory explicit PayPal case allocation')
        movement_review(doc)  # Validate structure; initiation/payout fields never authorize cash.
        result[did]={'document_sha256':cash._sha(doc),'captures':sorted(ids),'amount_minor':total,
                     'updated_ms':int(stamp.timestamp()*1000),'outcome':outcome['outcome_code'],
                     'item_amounts':items}  # no proportional case allocation
    return result


def _case_coverage(cases,movements,captures,refunds):
    by_id={x['transaction_id']:x for x in movements};debits={cid:0 for cid in captures};changed=set()
    for row in movements:
        cid=row['transaction_id']
        while cid not in captures:cid=by_id[cid]['paypal_reference_id']
        if row['event_code'] in ('T1106','T1201','T1207'):
            debits[cid]-=cash._money(row);changed.add(cid)
        if row['event_code'] in ('T1202','T1205','T1208'):changed.add(cid)
    returned={cid:sum(r['amount_minor'] for r in refunds if r['capture_id']==cid) for cid in captures}
    for case in cases.values():
        ids=case['captures']
        if case['outcome']=='RESOLVED_WITH_PAYOUT' and not changed.intersection(ids):
            raise FenceBlocked('Final payout lacks an actual completed principal movement')
        if case['outcome']=='RESOLVED_BUYER_FAVOUR':
            items=case['item_amounts'] or ({ids[0]:case['amount_minor']} if len(ids)==1 else None)
            if items is not None:
                if any(debits[cid]<max(0,amount-returned[cid]) for cid,amount in items.items()):
                    raise FenceBlocked('Final buyer case lacks its completed loss coverage')
            elif sum(debits[cid]+returned[cid] for cid in ids)<case['amount_minor']:
                raise FenceBlocked('Final multicapture loss coverage is incomplete')


class CashContext:
    def __init__(self,order,cfg,canonical,refunds,cases,proof,version,basis):
        self.order=order;self.cfg=cfg;self.canonical=canonical;self.refunds=refunds
        self.cases=cases;self.proof=proof;self.version=version;self.basis=basis

    def verify(self,c,order,cfg,canonical):
        if (dict(order)!=self.order or cfg!=self.cfg or canonical!=self.canonical
                or cash.journal_version(c,order['id'])!=self.version):
            raise FenceBlocked('Original payment changed during PayPal cash acquisition')
        from .regime_checkout_fence import verify_enrolled_payment
        if not verify_enrolled_payment(c,'paypal',order['id']):raise FenceBlocked('Original new-release checkout admission required')
        if order['kind']=='subscription':
            from .subscription_receivables import original_quote
            if original_quote(c,order)!=self.basis:raise FenceBlocked('Original fee changed during cash acquisition')
        for raw, in c.execute("SELECT normalized_json FROM payment_reconciliation_events WHERE provider='paypal' AND order_id=? AND state='applied'",(order['id'],)):
            previous=json.loads(raw)
            if previous.get('type')=='paypal_cash_case' and previous['case_id'] not in self.cases:
                raise FenceBlocked('PayPal cash history omits previously proved case')
        if c.execute("SELECT 1 FROM sqlite_master WHERE name='paypal_financial_holds'").fetchone():
            for hid, in c.execute("SELECT hold_id FROM paypal_financial_holds WHERE order_id=? AND kind='dispute'",(order['id'],)):
                if hid.split(':')[1] not in self.cases:raise FenceBlocked('PayPal cash history omits known case')
        for raw, in c.execute("SELECT normalized_json FROM payment_reconciliation_events WHERE provider='paypal' AND order_id=? AND state='pending'",(order['id'],)):
            data=json.loads(raw)
            if data.get('type')=='paypal_history_gap' and not set(data.get('required_dispute_ids',[]))<=set(self.cases):
                raise FenceBlocked('PayPal cash history omits observed case')

    def finalize(self,c,order):
        from .payment_reconciliation import record_event,mark_applied,bind_object
        p=dict(self.proof);oid=order['id'];ids=set(p['captures'])
        # Exact canonical final cases close financial consequences only. Raw
        # final outcomes/holds are preserved, including contradictory snapshots.
        for eid,raw,bound in c.execute("SELECT event_id,normalized_json,order_id FROM payment_reconciliation_events WHERE provider='paypal' AND state='pending'").fetchall():
            data=json.loads(raw)
            if bound!=oid and data.get('capture_id') not in ids:continue
            if data.get('type')!='risk':continue
            hid=data.get('hold_id','');case=self.cases.get(hid.split(':')[1] if hid.startswith('dispute:') else '')
            if (case is None or bound not in (None,oid) or data.get('capture_id') not in case['captures']
                    or data.get('kind')!='dispute' or data.get('environment')!=order['environment']
                    or data.get('merchant_fingerprint')!=order['client_fingerprint']
                    or type(data.get('updated_ms')) is not int or data['updated_ms']>case['updated_ms']
                    or type(data.get('amount_minor')) is not int or not 0<data['amount_minor']<=min(case['amount_minor'],p['captures'][data['capture_id']])):
                raise FenceBlocked('Pending risk not covered by final original cash')
            mark_applied(c,'paypal',eid,oid)
        for did,case in sorted(self.cases.items()):
            bind_object(c,'paypal','cash-case:'+did,oid)
            value={'type':'paypal_cash_case','order_id':oid,'case_id':did,**case}
            eid='reconcile:cash-case:'+cash._sha(value)
            record_event(c,'paypal',eid,cash._sha(value),value);mark_applied(c,'paypal',eid,oid)
        for row in p['movements']:
            mid=row['transaction_id'];bind_object(c,'paypal','cash-movement:'+mid,oid)
            value=cash._movement_claim(order,row);eid='reconcile:subscription-movement:'+mid
            record_event(c,'paypal',eid,cash._sha(value),value);mark_applied(c,'paypal',eid,oid)
        p['journal_version']=cash.journal_version(c,oid)
        prior=position(c,order);eid='reconcile:paypal-cash:'+cash._sha(p)
        if prior is None or prior['source_sha256']!=p['source_sha256'] or prior['cases']!=p['cases']:
            record_event(c,'paypal',eid,cash._sha(p),p);mark_applied(c,'paypal',eid,oid)
        if order['kind']=='credits':
            actual=c.execute('''SELECT coalesce(sum(delta_micro),0) FROM resource_credits WHERE user_id=?
              AND (id=? OR reason=? OR reason=?)''',(order['user_id'],'paypal:'+oid,'PayPal credit refund: '+oid,'PayPal risk adjustment: '+oid)).fetchone()[0]
            delta=p['net_minor']*10000-actual
            if delta:
                credit='paypal-cash:'+eid
                c.execute('INSERT INTO resource_credits VALUES(?,?,?,?,?,?)',(credit,order['user_id'],delta,None,'PayPal risk adjustment: '+oid,int(time.time())))
                c.execute("INSERT INTO payment_reconciliation_movements VALUES('paypal',?,?,?,?)",(eid,credit,oid,delta))
        paypal._record_position(c,order,'capture:'+order['provider_order'])
        if order['kind']=='subscription':
            from .subscription_receivables import accrue_original_loss
            accrue_original_loss(c,order,eid)
        from .subscription_receivables import sync
        sync(c)


def reconcile(oid,*,expected_owner=None,_webhook_event_id=None,_webhook_digest=None,
              _expected_provider_order=None,_expected_config=None,_merchant_context=None):
    from . import paypal_dispute_history as disputes
    from .paypal_reconciliation import discover,_identifier
    with auth.db() as c:
        paypal.init(c);c.execute('BEGIN IMMEDIATE')
        from .payment_reconciliation import initialize
        initialize(c)
        row=c.execute('SELECT * FROM paypal_orders WHERE id=?',(oid,)).fetchone();cfg=paypal._keys(c)
        if (row is None or row['status'] not in ('paid','pending') or (expected_owner is not None
                and (type(expected_owner) is not int or row['user_id']!=expected_owner))):raise ValueError('Original PayPal payment unavailable')
        order=dict(row);version=cash.journal_version(c,oid);basis=None;required={}
        if ((_expected_provider_order is not None and order['provider_order']!=_expected_provider_order)
                or (_expected_config is not None and cfg!=_expected_config)):
            raise FenceBlocked('Original PayPal callback identity changed')
        if order['kind']=='subscription':
            from .subscription_receivables import original_quote
            basis=original_quote(c,order)
        if c.execute("SELECT 1 FROM sqlite_master WHERE name='paypal_financial_holds'").fetchone():
            required={x[0]:x[1] for x in c.execute("SELECT capture_id,max(amount_cents) FROM paypal_financial_holds WHERE order_id=? AND status='permanent' GROUP BY capture_id",(oid,))}
        observed=max((x[0] for x in c.execute("SELECT created_at FROM payment_reconciliation_events WHERE provider='paypal' AND order_id=? AND state='pending' AND event_id NOT LIKE 'reconcile:%'",(oid,))),default=0)
    if (cfg['environment'],hashlib.sha256(cfg['client_id'].encode()).hexdigest())!=(order['environment'],order['client_fingerprint']):raise FenceBlocked('Original PayPal cash merchant required')
    end=datetime.fromtimestamp(int(time.time())-10800,timezone.utc);start=datetime.fromtimestamp(order['created_at']-300,timezone.utc)
    if not start<end or observed>end.timestamp():raise ValueError('PayPal cash coverage is not yet fresh')
    canonical=paypal._api(cfg,'GET','/v2/checkout/orders/'+_identifier(order['provider_order']))
    units=canonical.get('purchase_units',[])
    if (canonical.get('id')!=order['provider_order'] or canonical.get('status')!='COMPLETED' or len(units)!=1
            or any(units[0].get(k)!=oid for k in ('custom_id','reference_id')) or paypal._cents(units[0]['amount'])!=order['amount_cents']):raise FenceBlocked('Original PayPal cash order identity mismatch')
    account=units[0].get('payee',{}).get('merchant_id')
    if not isinstance(account,str) or not account:raise ValueError('Canonical original PayPal account required')
    refunds=discover(canonical,cfg);documents=disputes.documents(canonical,cfg)
    captures={x['id']:paypal._cents(x['amount']) for x in units[0]['payments']['captures']}
    if sum(captures.values())!=order['amount_cents']:raise ValueError('Original PayPal captures do not conserve gross')
    cases=_cases(documents,captures,end)
    budget=[0,time.monotonic()+cash.MAX_SECONDS]
    first=cash._collect(cfg,start,end,account,budget);second=cash._collect(cfg,start,end,account,budget)
    if first!=second:raise FenceBlocked('PayPal cash history changed during acquisition')
    # Per-capture cash is exact even when a final multicapture case has no item
    # allocation. Never invent per-case splits or count payout observations.
    loss,movements=cash._principal(first,canonical,refunds,[],required)
    _case_coverage(cases,movements,captures,refunds)
    if discover(canonical,cfg)!=refunds or disputes.documents(canonical,cfg)!=documents:
        raise FenceBlocked('PayPal canonical history changed during cash acquisition')
    net=order['amount_cents']-loss;refunded=sum(x['amount_minor'] for x in refunds)
    if net>order['amount_cents']-refunded:raise FenceBlocked('PayPal reimbursement exceeds original retained principal')
    p={'type':TYPE,'schema':SCHEMA,'order_id':oid,'user_id':order['user_id'],'kind':order['kind'],
       'environment':order['environment'],'merchant_fingerprint':order['client_fingerprint'],'account':account,
       'captures':captures,'cases':cases,'start_date':cash._stamp(start),'end_date':cash._stamp(end),
       'movements':movements,'source_sha256':cash._sha(movements),'net_minor':net}
    if basis is not None:p.update(basis=basis,fee_loss_micro=min(basis['fee_micro'],max(0,loss*10000-basis['surplus_micro'])),remaining_surplus_micro=max(0,basis['surplus_micro']-loss*10000))
    context=CashContext(order,cfg,canonical,refunds,cases,p,version,basis)
    result=paypal.fulfill(oid,canonical,webhook_event_id=_webhook_event_id,webhook_digest=_webhook_digest,
                          _reconciliation=(order,cfg,refunds),_cash_context=context,_merchant_context=_merchant_context)
    with auth.db() as c:
        pending=bool(c.execute("SELECT 1 FROM payment_reconciliation_events WHERE provider='paypal' AND order_id=? AND state='pending'",(oid,)).fetchone())
    return {**result,'provider':'paypal','ledger_reconciled':result.get('status')=='paid','financial_review_pending':pending,
            'cash_history_end':p['end_date'],'cash_net_minor':net,'history_scope':'original_complete_cash_and_final_cases','transition_authorized':False}
