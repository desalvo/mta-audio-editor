"""Read-only authenticated provider state probes for offline financial triage.

Provider responses are evidence, not entitlement or authorization for regime cutover.
No database mutations, capture, refund or replay are performed here.
"""
from __future__ import annotations

import re
import httpx

_REFERENCE = re.compile(r'^[A-Za-z0-9_-]{5,180}$')
_PAYPAL_HOSTS = {'sandbox': 'https://api-m.sandbox.paypal.com', 'live': 'https://api-m.paypal.com'}
_STRIPE_STATES = frozenset({'open', 'complete', 'expired'})
_PAYPAL_STATES = frozenset({'CREATED', 'SAVED', 'APPROVED', 'VOIDED', 'COMPLETED', 'PAYER_ACTION_REQUIRED'})


class ProviderProbeError(ValueError):
    """The remote provider outcome cannot be verified safely."""


def _reference(value: str) -> str:
    if not isinstance(value, str) or not _REFERENCE.fullmatch(value):
        raise ProviderProbeError('Invalid provider reference')
    return value


def _get(client: httpx.Client, url: str, headers: dict[str, str]) -> dict:
    try:
        response = client.get(url, headers=headers, follow_redirects=False, timeout=15)
        if response.status_code != 200:
            raise ProviderProbeError('Provider status unavailable')
        payload = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise ProviderProbeError('Provider lookup failed') from exc
    if not isinstance(payload, dict):
        raise ProviderProbeError('Malformed provider response')
    return payload


def probe_stripe_checkout(session_id: str, secret_key: str, *, client: httpx.Client) -> dict:
    """Query Stripe checkout session; never infer settlement from session status."""
    session_id = _reference(session_id)
    if not session_id.startswith('cs_') or not isinstance(secret_key, str) or not secret_key.startswith(('sk_test_', 'sk_live_')):
        raise ProviderProbeError('Invalid Stripe reference or credentials')
    payload = _get(client, 'https://api.stripe.com/v1/checkout/sessions/' + session_id,
                   {'Authorization': 'Bearer ' + secret_key})
    if payload.get('id') != session_id or payload.get('status') not in _STRIPE_STATES:
        raise ProviderProbeError('Stripe reference/status mismatch')
    payment = payload.get('payment_status')
    if payment not in ('paid', 'unpaid', 'no_payment_required'):
        raise ProviderProbeError('Unknown Stripe payment status')
    # Explicitly do NOT equate complete checkout with paid financial settlement.
    return {'provider': 'stripe', 'reference': session_id, 'checkout_status': payload['status'],
            'payment_status': payment, 'requires_ledger_reconciliation': True,
            'authorizes_entitlement': False, 'authorizes_cutover': False}


def probe_paypal_order(order_id: str, client_id: str, client_secret: str, *, environment: str,
                       client: httpx.Client) -> dict:
    """Retrieve a PayPal order using OAuth client credentials (no capture)."""
    order_id = _reference(order_id)
    if environment not in _PAYPAL_HOSTS or not client_id or not client_secret:
        raise ProviderProbeError('Invalid PayPal configuration')
    base = _PAYPAL_HOSTS[environment]
    try:
        auth = client.post(base + '/v1/oauth2/token', auth=(client_id, client_secret),
                           data={'grant_type': 'client_credentials'}, follow_redirects=False, timeout=15)
        if auth.status_code != 200:
            raise ProviderProbeError('PayPal authentication failed')
        token = auth.json().get('access_token')
    except (httpx.HTTPError, ValueError, AttributeError) as exc:
        raise ProviderProbeError('PayPal authentication unavailable') from exc
    if not isinstance(token, str) or not token:
        raise ProviderProbeError('Invalid PayPal token')
    payload = _get(client, base + '/v2/checkout/orders/' + order_id, {'Authorization': 'Bearer ' + token})
    if payload.get('id') != order_id or payload.get('status') not in _PAYPAL_STATES:
        raise ProviderProbeError('PayPal reference/status mismatch')
    # Order COMPLETED alone does not establish capture amount/currency and local fulfillment.
    return {'provider': 'paypal', 'reference': order_id, 'order_status': payload['status'],
            'requires_capture_reconciliation': True, 'requires_ledger_reconciliation': True,
            'authorizes_entitlement': False, 'authorizes_cutover': False}
