"""Bounded GET-only proof for failed charges on an already canceled intent.

Decline text, card/customer information and client secrets are never retained.
Missing fields or any monetary/authorization evidence require operator review.
"""
from .regime_provider_probe import _get, _reference, ProviderProbeError

FIELDS = ('id', 'payment_intent', 'amount', 'currency', 'status', 'paid',
          'captured', 'amount_captured', 'amount_refunded', 'refunded', 'disputed',
          'balance_transaction', 'failure_balance_transaction', 'livemode')


def validate(proof, intent, amount):
    if (not isinstance(proof, dict) or set(proof) != {'schema', 'charges'}
            or proof['schema'] != 'stripe-failed-charges-1' or not isinstance(proof['charges'], list)
            or not 1 <= len(proof['charges']) <= 100 or not isinstance(intent, str) or not intent.startswith('pi_')
            or type(amount) is not int or amount <= 0):
        raise ProviderProbeError('Invalid failed-charge proof')
    seen = set()
    live = proof['charges'][0].get('livemode') if isinstance(proof['charges'][0], dict) else None
    if type(live) is not bool:
        raise ProviderProbeError('Missing failed-charge environment')
    for charge in proof['charges']:
        normalized = _charge(charge, intent, amount, live)
        if set(charge) != set(FIELDS) or normalized['id'] in seen:
            raise ProviderProbeError('Duplicate or excessive failed-charge evidence')
        seen.add(normalized['id'])
    return seen


def _charge(document, intent, amount, live):
    if not isinstance(document, dict) or any(field not in document for field in FIELDS):
        raise ProviderProbeError('Incomplete failed-charge proof')
    identifier = _reference(document['id'])
    if (not identifier.startswith('ch_') or document['payment_intent'] != intent
            or type(document['amount']) is not int or document['amount'] != amount
            or document['currency'] != 'eur' or document['status'] != 'failed'
            or any(document[key] is not False for key in ('paid', 'captured', 'refunded', 'disputed'))
            or any(type(document[key]) is not int or document[key] != 0 for key in ('amount_captured', 'amount_refunded'))
            or document['balance_transaction'] is not None or document['failure_balance_transaction'] is not None
            or document['livemode'] is not live):
        raise ProviderProbeError('Failed charge has unresolved money or identity')
    return {field: document[field] for field in FIELDS}


def prove(client, key, intent, amount, initial, charges):
    """Called only after the initial canceled/zero-received/capturable checks."""
    from .payment_reconcile_service import _pages
    if not charges:
        if initial['latest_charge'] is not None:
            raise ProviderProbeError('Latest charge missing from provider history')
    live = key.startswith('sk_live_')
    if initial.get('livemode') is not live:
        raise ProviderProbeError('Canceled intent environment mismatch')
    if charges and initial['latest_charge'] not in {item.get('id') for item in charges}:
        raise ProviderProbeError('Latest charge missing from provider history')
    headers = {'Authorization': 'Bearer ' + key}
    verified = []
    for document in charges:
        snapshot = _charge(document, intent, amount, live)
        canonical = _get(client, 'https://api.stripe.com/v1/charges/' + snapshot['id'], headers)
        if _charge(canonical, intent, amount, live) != snapshot:
            raise ProviderProbeError('Failed charge changed during readback')
        verified.append(snapshot)
    final = _pages(client, 'charges', headers, {'payment_intent': intent}, max_items=100)
    normalized = sorted(verified, key=lambda item: item['id'])
    if sorted((_charge(item, intent, amount, live) for item in final), key=lambda item: item['id']) != normalized:
        raise ProviderProbeError('Failed-charge collection changed during readback')
    document = _get(client, 'https://api.stripe.com/v1/payment_intents/' + intent, headers)
    fields = ('id', 'amount', 'currency', 'status', 'amount_received', 'amount_capturable', 'latest_charge', 'livemode')
    if any(field not in document or type(document[field]) is not type(initial[field]) or document[field] != initial[field] for field in fields):
        raise ProviderProbeError('Canceled intent changed during failed-charge proof')
    # Empty history needs the same collection/intent reread. Retain the old
    # receipt shape only after verifying that the empty collection stayed empty.
    return {'schema': 'stripe-failed-charges-1', 'charges': normalized} if normalized else None
