"""Authenticated, read-only financial evidence validation for Stripe and PayPal.

This module does not mutate ledgers, grant credits, retry payments, or authorize
regime changes. A matched observation is not evidence of a completed local
ledger reconciliation; operators must reconcile refunds and legacy liabilities.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
import httpx

from .regime_provider_probe import ProviderProbeError, _reference, _get, _PAYPAL_HOSTS


def _minor_units(value: object) -> int:
    # Provider amount_minor and local accounting must be exact integers, not floats.
    if type(value) is not int or value < 0:
        raise ProviderProbeError('Invalid minor-unit amount')
    return value


def _currency(value: object) -> str:
    if not isinstance(value, str) or len(value) != 3 or not value.isalpha():
        raise ProviderProbeError('Invalid currency')
    return value.upper()


def _paypal_amount(value: object, currency: str) -> int:
    if not isinstance(value, dict) or _currency(value.get('currency_code')) != currency:
        raise ProviderProbeError('PayPal capture currency mismatch')
    raw = value.get('value')
    if not isinstance(raw, str):
        raise ProviderProbeError('Invalid PayPal amount')
    try:
        amount = Decimal(raw)
    except InvalidOperation as exc:
        raise ProviderProbeError('Invalid PayPal amount') from exc
    # Restrict to currencies with two decimal places; others require explicit exponent mapping.
    if currency in {'JPY', 'KRW', 'BHD', 'KWD', 'OMR', 'TND'}:
        raise ProviderProbeError('Currency requires an explicit provider exponent')
    minor = amount * 100
    if not amount.is_finite() or minor != minor.to_integral_value() or minor < 0:
        raise ProviderProbeError('Invalid PayPal amount precision')
    return int(minor)


def verify_stripe_settlement(session_id: str, secret_key: str, expected_minor: int,
                             expected_currency: str, *, client: httpx.Client) -> dict:
    session_id = _reference(session_id)
    amount = _minor_units(expected_minor)
    currency = _currency(expected_currency)
    if not session_id.startswith('cs_') or not isinstance(secret_key, str) or not secret_key.startswith(('sk_test_', 'sk_live_')):
        raise ProviderProbeError('Invalid Stripe reference or credentials')
    headers = {'Authorization': 'Bearer ' + secret_key}
    session = _get(client, 'https://api.stripe.com/v1/checkout/sessions/' + session_id, headers)
    if (session.get('id') != session_id or session.get('status') != 'complete'
            or session.get('payment_status') != 'paid'
            or session.get('amount_total') != amount
            or _currency(session.get('currency')) != currency):
        raise ProviderProbeError('Stripe checkout settlement mismatch')
    intent_id = _reference(session.get('payment_intent'))
    if not intent_id.startswith('pi_'):
        raise ProviderProbeError('Missing Stripe payment intent')
    intent = _get(client, 'https://api.stripe.com/v1/payment_intents/' + intent_id, headers)
    if (intent.get('id') != intent_id or intent.get('status') != 'succeeded'
            or intent.get('amount_received') != amount
            or _currency(intent.get('currency')) != currency):
        raise ProviderProbeError('Stripe payment intent settlement mismatch')
    if intent.get('amount') != amount:
        raise ProviderProbeError('Stripe original amount mismatch')
    # Refunds and disputes may happen after this observation; never authorize fulfillment.
    return {'provider': 'stripe', 'reference': session_id, 'payment_intent': intent_id,
            'amount_minor': amount, 'currency': currency,
            'remote_payment_observed': True, 'refunds_and_disputes_verified': False,
            'local_ledger_reconciled': False, 'authorizes_entitlement': False,
            'authorizes_cutover': False}


def verify_paypal_settlement(order_id: str, client_id: str, client_secret: str,
                             expected_minor: int, expected_currency: str, *, environment: str,
                             client: httpx.Client) -> dict:
    order_id = _reference(order_id)
    amount = _minor_units(expected_minor)
    currency = _currency(expected_currency)
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
    order = _get(client, base + '/v2/checkout/orders/' + order_id,
                 {'Authorization': 'Bearer ' + token})
    if order.get('id') != order_id or order.get('status') != 'COMPLETED':
        raise ProviderProbeError('PayPal order not completed')
    units = order.get('purchase_units')
    if not isinstance(units, list) or not units:
        raise ProviderProbeError('Missing PayPal purchase units')
    captures = []
    for unit in units:
        if not isinstance(unit, dict):
            raise ProviderProbeError('Invalid PayPal purchase unit')
        payments = unit.get('payments')
        entries = payments.get('captures') if isinstance(payments, dict) else None
        if not isinstance(entries, list) or not entries:
            raise ProviderProbeError('Missing PayPal captures')
        captures.extend(entries)
    ids = set()
    total = 0
    for capture in captures:
        if not isinstance(capture, dict) or capture.get('status') != 'COMPLETED':
            raise ProviderProbeError('PayPal capture not completed')
        capture_id = _reference(capture.get('id'))
        if capture_id in ids:
            raise ProviderProbeError('Duplicate PayPal capture')
        ids.add(capture_id)
        total += _paypal_amount(capture.get('amount'), currency)
    if total != amount:
        raise ProviderProbeError('PayPal capture total mismatch')
    return {'provider': 'paypal', 'reference': order_id, 'capture_ids': sorted(ids),
            'amount_minor': amount, 'currency': currency,
            'remote_payment_observed': True, 'refunds_and_disputes_verified': False,
            'local_ledger_reconciled': False, 'authorizes_entitlement': False,
            'authorizes_cutover': False}


def verify_stripe_payment_with_reversals(session_id: str, secret_key: str,
                                         expected_minor: int, expected_currency: str,
                                         *, client: httpx.Client) -> dict:
    """Cross-check settlement and linked charge refund/dispute evidence read-only.

    This snapshot cannot prove future reversal absence or authorize a ledger write.
    """
    from .regime_provider_refund_evidence import inspect_stripe_charge
    settlement = verify_stripe_settlement(session_id, secret_key, expected_minor,
                                           expected_currency, client=client)
    intent = _get(client, 'https://api.stripe.com/v1/payment_intents/' + settlement['payment_intent'],
                  {'Authorization': 'Bearer ' + secret_key})
    if intent.get('id') != settlement['payment_intent']:
        raise ProviderProbeError('Stripe payment intent identity changed')
    charge_id = _reference(intent.get('latest_charge'))
    if not charge_id.startswith('ch_'):
        raise ProviderProbeError('Stripe latest charge unavailable')
    reversal = inspect_stripe_charge(charge_id, secret_key, client=client)
    charge = _get(client, 'https://api.stripe.com/v1/charges/' + charge_id,
                  {'Authorization': 'Bearer ' + secret_key})
    if (charge.get('id') != charge_id or charge.get('payment_intent') != settlement['payment_intent']
            or type(charge.get('amount')) is not int or charge['amount'] != settlement['amount_minor']
            or _currency(charge.get('currency')) != settlement['currency']):
        raise ProviderProbeError('Stripe charge financial identity mismatch')
    return {**settlement, 'charge_id': charge_id,
            'no_reversal_observed_at_lookup': reversal['no_reversal_observed_at_lookup'],
            'local_ledger_reconciled': False, 'authorizes_entitlement': False,
            'authorizes_cutover': False}


def verify_paypal_payment_with_capture_observations(order_id: str, client_id: str,
                                                     client_secret: str, expected_minor: int,
                                                     expected_currency: str, *, environment: str,
                                                     client: httpx.Client) -> dict:
    """Cross-check each capture against a separate authenticated capture lookup.

    Capture status cannot certify historical refunds or disputes; ledger stays gated.
    """
    from .regime_provider_refund_evidence import inspect_paypal_capture
    result = verify_paypal_settlement(order_id, client_id, client_secret, expected_minor,
                                       expected_currency, environment=environment, client=client)
    base = _PAYPAL_HOSTS[environment]
    try:
        auth = client.post(base + '/v1/oauth2/token', auth=(client_id, client_secret),
                           data={'grant_type': 'client_credentials'}, follow_redirects=False, timeout=15)
        if auth.status_code != 200:
            raise ProviderProbeError('PayPal authentication failed')
        token = auth.json()['access_token']
    except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
        raise ProviderProbeError('PayPal capture authentication unavailable') from exc
    if not isinstance(token, str) or not token:
        raise ProviderProbeError('Invalid PayPal capture token')
    for capture_id in result['capture_ids']:
        inspect_paypal_capture(capture_id, token, environment=environment, client=client)
    return {**result, 'captures_individually_observed': True,
            'refunds_and_disputes_verified': False, 'local_ledger_reconciled': False,
            'authorizes_entitlement': False, 'authorizes_cutover': False}
