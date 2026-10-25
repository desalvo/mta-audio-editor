"""Conservative, read-only provider reversal evidence.

This is *not* an authoritative all-time no-refund/no-dispute certificate:
provider observations can change after a successful request. Never use as a
cutover or entitlement authorization.
"""
from __future__ import annotations

import httpx

from .regime_provider_probe import ProviderProbeError, _get, _reference, _PAYPAL_HOSTS


def inspect_stripe_charge(charge_id: str, secret_key: str, *, client: httpx.Client) -> dict:
    """Fetch a specific Stripe charge and reject refund/dispute/uncertain state."""
    charge_id = _reference(charge_id)
    if not charge_id.startswith('ch_') or not isinstance(secret_key, str) or not secret_key.startswith(('sk_test_', 'sk_live_')):
        raise ProviderProbeError('Invalid Stripe charge or credentials')
    charge = _get(client, 'https://api.stripe.com/v1/charges/' + charge_id,
                  {'Authorization': 'Bearer ' + secret_key})
    if charge.get('id') != charge_id or charge.get('object') != 'charge':
        raise ProviderProbeError('Stripe charge identity mismatch')
    if charge.get('paid') is not True or charge.get('captured') is not True or charge.get('status') != 'succeeded':
        raise ProviderProbeError('Stripe charge not settled')
    if type(charge.get('amount_refunded')) is not int or charge['amount_refunded'] != 0:
        raise ProviderProbeError('Stripe charge refund or uncertain amount')
    if charge.get('refunded') is not False or charge.get('disputed') is not False:
        raise ProviderProbeError('Stripe charge refund/dispute or uncertain flag')
    refunds = charge.get('refunds')
    if not isinstance(refunds, dict) or refunds.get('object') != 'list' or refunds.get('has_more') is not False or refunds.get('data') != []:
        raise ProviderProbeError('Stripe charge refunds not completely absent')
    return {'provider': 'stripe', 'charge_id': charge_id,
            'no_reversal_observed_at_lookup': True, 'authorizes_entitlement': False,
            'authorizes_cutover': False, 'requires_ledger_reconciliation': True}


def inspect_paypal_capture(capture_id: str, access_token: str, *, environment: str,
                           client: httpx.Client) -> dict:
    """Inspect a PayPal capture; do not infer that historical refunds do not exist."""
    capture_id = _reference(capture_id)
    if environment not in _PAYPAL_HOSTS or not isinstance(access_token, str) or not access_token:
        raise ProviderProbeError('Invalid PayPal capture configuration')
    capture = _get(client, _PAYPAL_HOSTS[environment] + '/v2/payments/captures/' + capture_id,
                   {'Authorization': 'Bearer ' + access_token})
    if capture.get('id') != capture_id or capture.get('status') != 'COMPLETED':
        raise ProviderProbeError('PayPal capture uncertain, refunded or incomplete')
    return {'provider': 'paypal', 'capture_id': capture_id,
            'capture_completed_at_lookup': True, 'refunds_and_disputes_verified': False,
            'authorizes_entitlement': False, 'authorizes_cutover': False,
            'requires_ledger_reconciliation': True}
