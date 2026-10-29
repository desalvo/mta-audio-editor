"""Connect immutable merchant observations to original authenticated ledgers.

Reporting labels cannot create orders, identify users or settle money. Unknown
references and payout/fee entries remain unresolved; no account-wide clearance.
"""
import hashlib
import re
from datetime import datetime

from . import auth, paypal_payments as paypal, paypal_merchant_history as history
from .regime_operation_fence import FenceBlocked


def _snapshot(c, actor, snapshot_id):
    history._admin(c, actor)
    if not isinstance(snapshot_id, str) or not re.fullmatch('[a-f0-9]{64}', snapshot_id):
        raise ValueError('Exact merchant snapshot required')
    row = c.execute('SELECT * FROM paypal_merchant_history WHERE id=?', (snapshot_id,)).fetchone()
    if row is None:
        raise FenceBlocked('Original merchant snapshot missing')
    history.verify_snapshot(row)
    import json
    data = json.loads(row['evidence_json'])
    history.validate_observations(data)
    if history.digest(data) != row['evidence_sha256']:
        raise FenceBlocked('Original merchant observations changed')
    cfg = paypal._keys(c)
    if (not cfg['enabled'] or not cfg['client_id'] or not cfg['client_secret']
            or (cfg['environment'], hashlib.sha256(cfg['client_id'].encode()).hexdigest())
            != (row['environment'], row['merchant_fingerprint'])):
        raise FenceBlocked('Original merchant configuration unavailable')
    return row, data, cfg


def _eligible(item):
    # T0006 is an Express Checkout principal; T1107 is a payment refund.
    # All other codes, including dispute payouts/fees, require separate proof.
    return (item['status'] == 'S' and item['currency'] == 'EUR'
            and ((item['event_code'] == 'T0006' and not item['amount'].startswith('-'))
                 or (item['event_code'] == 'T1107' and item['amount'].startswith('-'))))


def _local(c, item, cfg):
    ids = set()
    if item.get('paypal_reference_id_type') == 'ODR':
        ids.update(r[0] for r in c.execute('SELECT id FROM paypal_orders WHERE provider_order=?',
                                         (item['paypal_reference_id'],)))
    for ref in (item['transaction_id'], item.get('paypal_reference_id')
                if item.get('paypal_reference_id_type') == 'TXN' else None):
        if ref:
            ids.update(r[0] for r in c.execute('SELECT order_id FROM paypal_captures WHERE id=?', (ref,)))
            ids.update(r[0] for r in c.execute('SELECT order_id FROM paypal_refunds WHERE id=?', (ref,)))
    if len(ids) > 1:
        raise FenceBlocked('Merchant observation crosses original orders')
    if not ids:
        return None
    row = c.execute('SELECT * FROM paypal_orders WHERE id=?', (ids.pop(),)).fetchone()
    if (row is None or row['environment'] != cfg['environment']
            or row['client_fingerprint'] != hashlib.sha256(cfg['client_id'].encode()).hexdigest()):
        raise FenceBlocked('Original order merchant mismatch')
    return dict(row)


def review(actor, snapshot_id, *, offset=0, limit=50):
    if type(offset) is not int or offset < 0 or type(limit) is not int or not 1 <= limit <= 100:
        raise ValueError('Invalid merchant review pagination')
    with auth.db() as c:
        c.execute('BEGIN')
        _, data, cfg = _snapshot(c, actor, snapshot_id)
        items = []
        # The display page never limits the review totals.
        counts = {'known_candidates': 0, 'unbound_candidates': 0, 'unsupported': 0}
        for index, item in enumerate(data):
            local = _local(c, item, cfg) if _eligible(item) else None
            state = 'known_candidates' if local else 'unbound_candidates' if _eligible(item) else 'unsupported'
            counts[state] += 1
            if offset <= index < offset + limit:
                items.append({'observation_sha256': history.digest(item), 'transaction_id': item['transaction_id'],
                              'state': state, 'order_id': local['id'] if local else None,
                              'ledger_reconciled': False})
    return {'snapshot_id': snapshot_id, 'items': items, 'total': len(data), 'counts': counts,
            'offset': offset, 'scope': 'immutable_requested_window',
            'complete_account_history': False, 'transition_authorized': False}


def _selected(data, observation_sha256):
    if not isinstance(observation_sha256, str) or not re.fullmatch('[a-f0-9]{64}', observation_sha256):
        raise ValueError('Exact merchant observation required')
    matches = [item for item in data if history.digest(item) == observation_sha256]
    if len(matches) != 1 or not _eligible(matches[0]):
        raise FenceBlocked('Observation needs independent principal settlement evidence')
    return matches[0]


def _matches(snapshot, item, canonical, refunds):
    from .paypal_reconciliation import _payments
    stamp = item.get('transaction_initiation_date')
    if not isinstance(stamp, str):
        raise FenceBlocked('Reporting initiation time missing')
    when = datetime.fromisoformat(stamp.replace('Z', '+00:00'))
    if not history.instant(snapshot['start_date']) <= when <= history.instant(snapshot['end_date']):
        raise FenceBlocked('Reporting principal outside original window')
    payments = _payments(canonical)
    key = 'captures' if item['event_code'] == 'T0006' else 'refunds'
    rows = [r for r in payments.get(key, []) if r.get('id') == item['transaction_id']]
    amount = paypal._cents({'currency_code': item['currency'], 'value': item['amount'].lstrip('-')})
    if len(rows) != 1 or amount <= 0 or paypal._cents(rows[0]['amount']) != amount:
        raise FenceBlocked('Reporting principal does not match canonical payment')
    ref = item.get('paypal_reference_id')
    if item.get('paypal_reference_id_type') == 'ODR' and ref != canonical.get('id'):
        raise FenceBlocked('Reporting order reference changed')
    if item.get('paypal_reference_id_type') == 'TXN':
        expected = ({item['transaction_id']} if item['event_code'] == 'T0006' else
                    {r['capture_id'] for r in refunds if r['refund_id'] == item['transaction_id']})
        if ref not in expected:
            raise FenceBlocked('Reporting capture reference changed')


def before_commit(c, context, order, cfg, canonical, refunds):
    """Recheck the original administrator/snapshot/context in the money transaction."""
    snapshot, data = check_context(c, context, order, cfg)
    item = _selected(data, context['observation_sha256'])
    if canonical.get('status') != 'COMPLETED':
        raise FenceBlocked('Merchant discovery cannot close an unpaid checkout')
    _matches(snapshot, item, canonical, refunds)
    from .payment_reconciliation import record_event
    proof = {'type': 'merchant_discovery_binding', 'snapshot_id': snapshot['id'],
             'observation_sha256': context['observation_sha256'], 'order_id': order['id'],
             'environment': cfg['environment'], 'merchant_fingerprint': snapshot['merchant_fingerprint']}
    event = 'reconcile:merchant:' + history.digest([snapshot['id'], context['observation_sha256']])
    record_event(c, 'paypal', event, history.digest(proof), proof)
    return event


def check_context(c, context, order, cfg):
    snapshot, data, current = _snapshot(c, context['actor'], context['snapshot_id'])
    if (current != cfg or cfg != context['configuration']
            or any(order[k] != value for k, value in context['original_order'].items())):
        raise FenceBlocked('Original merchant reconciliation context changed')
    _selected(data, context['observation_sha256'])
    return snapshot, data


def reconcile(actor, snapshot_id, observation_sha256, *, confirm=False):
    if confirm is not True:
        raise ValueError('Explicit original-ledger reconciliation confirmation required')
    with auth.db() as c:
        c.execute('BEGIN')
        snapshot, data, cfg = _snapshot(c, actor, snapshot_id)
        item = _selected(data, observation_sha256)
        order = _local(c, item, cfg)
    if order is None:
        # Only the fixed principal capture endpoint can discover its canonical
        # order. Never route using payer notes, custom IDs, URLs or account IDs.
        cid = item['transaction_id'] if item['event_code'] == 'T0006' else (
            item.get('paypal_reference_id') if item.get('paypal_reference_id_type') == 'TXN' else None)
        from .paypal_reconciliation import _identifier
        cid = _identifier(cid)
        capture = paypal._api(cfg, 'GET', '/v2/payments/captures/' + cid)
        if capture.get('id') != cid:
            raise FenceBlocked('Canonical discovery capture changed')
        pid = capture.get('supplementary_data', {}).get('related_ids', {}).get('order_id')
        _identifier(pid)
        with auth.db() as c:
            order = _local(c, {'transaction_id': cid, 'paypal_reference_id': pid,
                              'paypal_reference_id_type': 'ODR'}, cfg)
        if order is None:
            raise FenceBlocked('Original local order missing; restore its original evidence')
    # The complete refund/dispute discovery is reused rather than trusting the
    # reporting amount as a credit. Its write lock rechecks this exact context.
    from .payment_reconcile_service import reconcile_paypal
    context = {'actor': actor, 'snapshot_id': snapshot_id, 'observation_sha256': observation_sha256,
               'configuration': cfg, 'original_order': {k: order[k] for k in
               ('id','user_id','kind','period_start','amount_cents','environment','client_fingerprint','provider_order')}}
    result = reconcile_paypal(order['id'], _merchant_context=context)
    return {**result, 'snapshot_id': snapshot['id'], 'observation_sha256': observation_sha256,
            'complete_account_history': False, 'transition_authorized': False}
