"""Bounded canonical ancestry of one paid Stripe intent; never global authority.

Called twice independently before the caller's accounting transaction. Only
fixed financial fields enter the snapshot; no card, customer or decline data.
"""
from .regime_provider_probe import _get, _reference, ProviderProbeError
from .stripe_failed_charge_proof import _charge as failed_charge
from time import monotonic


class ReadbackBudget:
    """Bound the complete attempt, including both passes and terminal lookups."""
    MAX_READS = 256
    MAX_SECONDS = 60

    def __init__(self, client):
        self.client = client
        self.remaining = self.MAX_READS
        self.deadline = monotonic()+self.MAX_SECONDS

    def get(self, *args, **kwargs):
        seconds = self.deadline-monotonic()
        if self.remaining <= 0 or seconds <= 0:
            raise ProviderProbeError('Stripe readback budget exhausted; operator review required')
        self.remaining -= 1
        kwargs['timeout'] = min(kwargs.get('timeout',15), seconds)
        response = self.client.get(*args, **kwargs)
        if monotonic() >= self.deadline:
            raise ProviderProbeError('Stripe readback deadline exceeded; refresh required')
        return response


def collect(client, key, order):
    from .payment_reconcile_service import _pages
    headers = {'Authorization': 'Bearer '+key}
    live = key.startswith('sk_live_')

    def read(path):
        return _get(client, 'https://api.stripe.com/v1/'+path, headers)

    def project(doc, fields):
        if any(field not in doc for field in fields):
            raise ProviderProbeError('Incomplete Stripe financial snapshot')
        return {field: doc[field] for field in fields}

    def environment(doc):
        if doc.get('livemode') is not live:
            raise ProviderProbeError('Stripe financial environment mismatch')

    session = read('checkout/sessions/'+_reference(order['session_id']))
    environment(session)
    metadata = session.get('metadata')
    if (session.get('id') != order['session_id'] or session.get('mode') != 'payment' or session.get('status') != 'complete'
            or session.get('payment_status') != 'paid' or type(session.get('amount_total')) is not int
            or session['amount_total'] != order['amount_cents'] or session.get('currency') != 'eur'
            or session.get('client_reference_id') != order['id'] or not isinstance(metadata, dict)
            or metadata.get('mta_order') != order['id']):
        raise ProviderProbeError('Canonical checkout identity mismatch')
    iid = _reference(session.get('payment_intent'))
    if not iid.startswith('pi_'):
        raise ProviderProbeError('Stripe payment intent reference required')
    intent = read('payment_intents/'+iid)
    environment(intent)
    if (intent.get('id') != iid or intent.get('status') != 'succeeded' or intent.get('currency') != 'eur'
            or any(type(intent.get(field)) is not int or intent[field] != order['amount_cents']
                   for field in ('amount', 'amount_received'))
            or type(intent.get('amount_capturable')) is not int or intent['amount_capturable'] != 0):
        raise ProviderProbeError('Canonical intent settlement mismatch')
    cid = _reference(intent.get('latest_charge'))
    if not cid.startswith('ch_'):
        raise ProviderProbeError('Stripe successful charge reference required')
    fields = ('id','payment_intent','amount','amount_captured','currency','status','paid',
              'captured','amount_refunded','refunded','disputed','balance_transaction',
              'failure_balance_transaction','livemode')
    attempts = _pages(client, 'charges', headers, {'payment_intent': iid}, max_items=100)
    if cid not in {item.get('id') for item in attempts}:
        raise ProviderProbeError('Successful charge missing from original intent history')
    prior = []
    charge = None
    for summary in attempts:
        aid = _reference(summary.get('id'))
        if not aid.startswith('ch_'):
            raise ProviderProbeError('Invalid Stripe charge identity')
        canonical = read('charges/'+aid)
        if aid != cid:
            item = failed_charge(canonical, iid, order['amount_cents'], live)
            if failed_charge(summary, iid, order['amount_cents'], live) != item:
                raise ProviderProbeError('Prior Stripe charge changed during readback')
            prior.append(item)
            continue
        charge = project(canonical, fields)
        if project(summary, fields) != charge:
            raise ProviderProbeError('Stripe charge changed during readback')
        environment(charge)
        if (charge['id'] != cid or charge['payment_intent'] != iid or charge['currency'] != 'eur'
                or charge['status'] != 'succeeded' or charge['paid'] is not True or charge['captured'] is not True
                or any(type(charge[field]) is not int or charge[field] != order['amount_cents']
                       for field in ('amount', 'amount_captured'))
                or type(charge['amount_refunded']) is not int
                or not 0 <= charge['amount_refunded'] <= order['amount_cents']
                or type(charge['refunded']) is not bool
                or charge['refunded'] != (charge['amount_refunded'] == order['amount_cents'])
                or type(charge['disputed']) is not bool or charge['failure_balance_transaction'] is not None
                or not _reference(charge['balance_transaction']).startswith('txn_')):
            raise ProviderProbeError('Canonical charge identity or money mismatch')
    collections = {}
    for kind, prefix in (('refunds','re_'), ('disputes','dp_')):
        verified = []
        for item in _pages(client, kind, headers, {'charge': cid}, max_items=1000):
            identifier = _reference(item.get('id'))
            if not identifier.startswith(prefix):
                raise ProviderProbeError('Invalid Stripe financial object identity')
            fields = ('id','charge','payment_intent','amount','currency','status')
            normalized = project(item, fields)
            if project(read(kind+'/'+identifier), fields) != normalized:
                raise ProviderProbeError('Stripe financial object changed during readback')
            statuses = (('succeeded','failed','canceled') if kind=='refunds' else
                        ('warning_needs_response','warning_under_review','warning_closed','needs_response','under_review','won','lost'))
            if (normalized['charge'] != cid or normalized['payment_intent'] != iid
                    or type(normalized['amount']) is not int or not 0 < normalized['amount'] <= order['amount_cents']
                    or normalized['currency'] != 'eur' or normalized['status'] not in statuses):
                raise ProviderProbeError('Unresolved or mismatched Stripe financial object')
            verified.append(normalized)
        collections[kind] = sorted(verified,key=lambda x:x['id'])
    if sum(item['amount'] for item in collections['refunds'] if item['status']=='succeeded') != charge['amount_refunded']:
        raise ProviderProbeError('Refund history changed or incomplete')
    if charge['disputed'] != bool(collections['disputes']):
        raise ProviderProbeError('Stripe dispute collection contradicts charge evidence')
    return {'schema':'stripe-paid-history-1',
            'session':{**project(session, ('id','mode','status','payment_status','amount_total','currency','client_reference_id','payment_intent','livemode')),
                       'metadata':{'mta_order':metadata['mta_order']}},
            'intent':project(intent, ('id','status','amount','amount_received','amount_capturable','currency','latest_charge','livemode')),
            'charge':charge,'failed_attempts':sorted(prior,key=lambda x:x['id']), **collections}
