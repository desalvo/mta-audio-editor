"""Operator-only authenticated report -> original canonical ledger recovery."""
from dataclasses import dataclass
from datetime import datetime
import hashlib
import json

from . import auth, paypal_payments as paypal, paypal_settlement_reports as reports
from .regime_operation_fence import FenceBlocked


def _encode(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)


def _sha(value):
    return hashlib.sha256(_encode(value).encode()).hexdigest()


@dataclass(frozen=True)
class ReportContext:
    actor: int
    order: dict
    configuration: dict
    account: str
    allocations: dict
    provenance: dict

    def verify(self, c, order, cfg, canonical=None):
        admin = c.execute('SELECT role,active FROM users WHERE id=?', (self.actor,)).fetchone()
        current = c.execute('SELECT * FROM paypal_orders WHERE id=?',(self.order['id'],)).fetchone()
        if (tuple(admin or ()) != ('admin', 1) or cfg != self.configuration
                or paypal._keys(c) != self.configuration or current is None
                or any(order[k] != value or current[k] != value for k, value in self.order.items())):
            raise FenceBlocked('Original report recovery context changed')
        if canonical is not None:
            units = canonical.get('purchase_units', [])
            if len(units) != 1 or units[0].get('payee', {}).get('merchant_id') != self.account:
                raise FenceBlocked('Canonical report merchant changed')

    def resolve(self, document, allocations, captures):
        """No report can waive an open case, missing allocation or wrong capture."""
        did = document['dispute_id']
        if (document.get('status') != 'RESOLVED' or document.get('dispute_outcome', {}).get('outcome_code')
                not in {'RESOLVED_WITH_PAYOUT', 'RESOLVED_SELLER_FAVOUR'}):
            return {}
        selected = {cid: self.allocations[(did,cid)] for cid in allocations if (did,cid) in self.allocations}
        if not selected:
            return {}
        case_ids = {cid for case,cid in self.allocations if case == did}
        if set(selected) != set(allocations) or case_ids != set(allocations) or captures is None:
            raise FenceBlocked('Report case allocation incomplete')
        for cid, proof in selected.items():
            created=datetime.fromisoformat(document['create_time'].replace('Z','+00:00'))
            updated=datetime.fromisoformat(document['update_time'].replace('Z','+00:00'))
            if (proof['amount_minor'] != allocations[cid] or proof['capture_gross_minor'] != captures[cid]
                    or datetime.fromisoformat(proof['case_filed_at']) != created
                    or not created <= updated <= datetime.fromisoformat(proof['report_end'])):
                raise FenceBlocked('Report does not prove exact original case principal')
        return {cid: {'schema': 'mta-paypal-defended-settlement-1', 'account': self.account,
                      'actor_id':self.actor,'case_id': did, 'capture_id': cid, **selected[cid],
                      'case_document_sha256': _sha(document), 'source': self.provenance}
                for cid in selected}

    def allocate(self, document, captures):
        """Exact report rows can allocate a partial case; gross ratios cannot."""
        did = document['dispute_id']
        ids = [row['seller_transaction_id'] for row in document['disputed_transactions']]
        selected = {cid: self.allocations[(did, cid)]['amount_minor']
                    for cid in ids if (did, cid) in self.allocations}
        if not selected:
            return None
        if set(selected) != set(ids) or not self.resolve(document, selected, captures):
            raise FenceBlocked('Complete resolved report allocation required')
        return selected

    def claim(self, c, rows):
        """A completed provider movement can belong to one original case only."""
        from .payment_reconciliation import record_event,mark_applied,bind_object
        for row in rows:
            proof=row.get('settlement_report_proof')
            if proof is None:
                continue
            expected=self.allocations.get((proof['case_id'],proof['capture_id']))
            if (expected is None or proof['source'] != self.provenance or proof['actor_id'] != self.actor
                    or any(proof[k] != value for k,value in expected.items())):
                raise FenceBlocked('Original report allocation changed')
            claim={'type':'report_settlement_claim','order_id':self.order['id'],'account':self.account,
                   'case_id':proof['case_id'],'capture_id':proof['capture_id'],
                   'movement_id':proof['movement_id'],'amount_minor':proof['amount_minor'],
                   'completed_at':proof['completed_at']}
            event='reconcile:report-movement:'+proof['movement_id']
            record_event(c,'paypal',event,_sha(claim),claim)
            bind_object(c,'paypal','report-movement:'+proof['movement_id'],self.order['id'])
            mark_applied(c,'paypal',event,self.order['id'])


def _verified_replay(c, document_sha, environment, fingerprint, order_id):
    """Read original applied receipts, their unique money claims and real holds.

    This is replay of an immutable decision, never authority for a new document.
    Rechecked in the money transaction before accepting a replay observation.
    """
    rows = {}
    tables = {row[0] for row in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if 'payment_reconciliation_events' not in tables:
        return rows
    events = c.execute("""SELECT normalized_json,digest
            FROM payment_reconciliation_events WHERE provider='paypal' AND state='applied' AND order_id=?
            LIMIT 10001""", (order_id,)).fetchall()
    if len(events) > 10000:
        raise FenceBlocked('Applied report history exceeds safe replay bound')
    for raw, digest in events:
        data = json.loads(raw)
        if not isinstance(data, dict) or not isinstance(data.get('settlement_report_proof', {}), dict):
            raise FenceBlocked('Malformed applied settlement receipt')
        proof = data.get('settlement_report_proof', {})
        if proof.get('case_document_sha256') != document_sha:
            continue
        if (data.get('type') != 'risk' or data.get('status') != 'released'
                or data.get('dispute_document_sha256') != document_sha
                or proof.get('schema') != 'mta-paypal-defended-settlement-1'
                or hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest() != digest
                or data.get('environment') != environment or data.get('merchant_fingerprint') != fingerprint
                or proof.get('capture_id') != data.get('capture_id')
                or proof.get('amount_minor') != data.get('amount_minor')):
            raise FenceBlocked('Applied settlement receipt cannot be verified')
        order = c.execute('SELECT * FROM paypal_orders WHERE id=?', (order_id,)).fetchone()
        capture = c.execute('SELECT order_id,amount_cents FROM paypal_captures WHERE id=?',
                            (data['capture_id'],)).fetchone()
        hold = c.execute('''SELECT order_id,capture_id,amount_cents,status,updated_ms,kind
            FROM paypal_financial_holds WHERE hold_id=?''', (data['hold_id'],)).fetchone()
        if (order is None or (order['environment'], order['client_fingerprint']) != (environment, fingerprint)
                or tuple(capture or ()) != (order_id, proof.get('capture_gross_minor'))
                or tuple(hold or ()) != (order_id, data['capture_id'], data['amount_minor'],
                                        'released', data['updated_ms'], 'dispute')
                or data['hold_id'] not in {'dispute:'+proof['case_id'],
                                           'dispute:'+proof['case_id']+':'+data['capture_id']}):
            raise FenceBlocked('Applied report no longer binds original financial position')
        claim = {'type':'report_settlement_claim','order_id':order_id,'account':proof['account'],
                 'case_id':proof['case_id'],'capture_id':proof['capture_id'],
                 'movement_id':proof['movement_id'],'amount_minor':proof['amount_minor'],
                 'completed_at':proof['completed_at']}
        event = c.execute("""SELECT normalized_json,digest,order_id,state
            FROM payment_reconciliation_events WHERE provider='paypal' AND event_id=?""",
            ('reconcile:report-movement:'+proof['movement_id'],)).fetchone()
        bound = c.execute("""SELECT order_id FROM payment_reconciliation_objects
            WHERE provider='paypal' AND object_id=?""", ('report-movement:'+proof['movement_id'],)).fetchone()
        if tuple(event or ()) != (_encode(claim), _sha(claim), order_id, 'applied') or tuple(bound or ()) != (order_id,):
            raise FenceBlocked('Original settlement movement claim unavailable')
        key = data['capture_id']
        if key in rows and rows[key] != data:
            # A different administrator may have verified the same intrinsic
            # movement; actor/source metadata never changes its allocation.
            previous = rows[key]['settlement_report_proof']
            if any(previous[k] != proof[k] for k in ('case_id','capture_id','account','movement_id','amount_minor','capture_gross_minor')):
                raise FenceBlocked('Conflicting applied report allocation')
        rows[key] = data
    return rows


def replay_allocations(document, cfg, captures):
    if captures is None:
        return None
    with auth.db() as c:
        ids = {row['seller_transaction_id'] for row in document['disputed_transactions']}
        orders = {row[0] for cid in ids for row in c.execute('SELECT order_id FROM paypal_captures WHERE id=?', (cid,))}
        if len(orders) != 1:
            return None
        rows = _verified_replay(c, _sha(document), cfg['environment'],
                               hashlib.sha256(cfg['client_id'].encode()).hexdigest(), next(iter(orders)))
    if not rows:
        return None
    ids = {row['seller_transaction_id'] for row in document['disputed_transactions']}
    if set(rows) != ids or any(rows[cid]['settlement_report_proof']['capture_gross_minor'] != captures[cid]
                               for cid in ids):
        raise FenceBlocked('Original report replay allocation incomplete')
    return {cid: rows[cid]['amount_minor'] for cid in ids}


def verified_replay(c, data):
    capture = c.execute('SELECT order_id FROM paypal_captures WHERE id=?', (data['capture_id'],)).fetchone()
    if capture is None:
        return False
    rows = _verified_replay(c, data['dispute_document_sha256'], data['environment'], data['merchant_fingerprint'], capture[0])
    previous = rows.get(data['capture_id'])
    return (previous is not None and all(previous.get(k) == data.get(k)
            for k in ('hold_id','capture_id','amount_minor','updated_ms','kind')))


def reconcile(actor, order_id, *, username, key_file, known_hosts, acm_name, stl_name, confirm=False):
    return reports.owned_call('paypal-report-recovery',_reconcile,actor,order_id,username=username,
        key_file=key_file,known_hosts=known_hosts,acm_name=acm_name,stl_name=stl_name,confirm=confirm)


def _reconcile(actor, order_id, *, username, key_file, known_hosts, acm_name, stl_name, confirm):
    if confirm is not True:
        raise ValueError('Explicit original settlement recovery confirmation required')
    with auth.db() as c:
        paypal.init(c)
        admin = c.execute('SELECT role,active FROM users WHERE id=?', (actor,)).fetchone()
        row = c.execute('SELECT * FROM paypal_orders WHERE id=?', (order_id,)).fetchone()
        if tuple(admin or ()) != ('admin',1) or row is None:
            raise FenceBlocked('Active administrator and original order required')
        cfg = paypal._keys(c)
        if cfg['environment'] != 'live' or row['environment'] != 'live':
            raise FenceBlocked('Production reporting transport is not sandbox evidence')
        original = {k: row[k] for k in ('id','user_id','kind','period_start','amount_cents',
                                       'environment','client_fingerprint','provider_order')}
        if original['client_fingerprint'] != hashlib.sha256(cfg['client_id'].encode()).hexdigest():
            raise FenceBlocked('Original merchant mismatch')
    from .paypal_reconciliation import _identifier
    canonical = paypal._api(cfg, 'GET', '/v2/checkout/orders/'+_identifier(original['provider_order']))
    units = canonical.get('purchase_units', [])
    account = units[0].get('payee', {}).get('merchant_id') if len(units) == 1 else None
    if not isinstance(account, str) or not account or canonical.get('id') != original['provider_order']:
        raise FenceBlocked('Canonical merchant account required for reporting proof')
    raw, provenance = reports.fetch(username, key_file, known_hosts, acm_name, stl_name)
    allocations = reports.defended(raw[0], raw[1], account)
    context = ReportContext(actor, original, cfg, account, allocations, provenance)
    from .payment_reconcile_service import reconcile_paypal
    return reconcile_paypal(order_id, _settlement_context=context)
