"""Authenticated provider observation -> durable local evidence, without entitlement settlement.

Remote requests MUST finish before BEGIN IMMEDIATE; the transaction then revalidates
checkout identity and the journal enforces replay integrity. This is deliberately
not an automatic billing or cutover authority.
"""
from __future__ import annotations

import sqlite3
from typing import Callable

from .regime_financial_evidence import record_observation
from .regime_operation_fence import FenceBlocked
from .regime_provider_settlement import (
    verify_stripe_payment_with_reversals,
    verify_paypal_payment_with_capture_observations,
)


def observe_and_journal(connection: sqlite3.Connection, *, operation_id: str,
                        provider: str, provider_reference: str, amount_minor: int,
                        currency: str, evidence_id: str, credentials: dict,
                        client, verifier: Callable | None = None) -> dict:
    """Fetch independently, then persist only if the original checkout still matches.

    The optional verifier is for isolated test harnesses; production uses the
    authenticated provider-specific verifier. Neither verifier nor journal can
    create financial entitlements.
    """
    if connection.in_transaction:
        raise FenceBlocked('Provider network lookup must run outside an open transaction')
    if provider not in ('stripe', 'paypal') or not isinstance(credentials, dict):
        raise FenceBlocked('Unsupported provider or credentials')
    if not isinstance(operation_id, str) or not operation_id.startswith('checkout:' + provider + ':'):
        raise FenceBlocked('Invalid checkout operation')
    if not isinstance(provider_reference, str) or not provider_reference or len(provider_reference) > 200:
        raise FenceBlocked('Invalid provider reference')
    if type(amount_minor) is not int or amount_minor < 0 or not isinstance(currency, str) or len(currency) != 3 or not currency.isalpha():
        raise FenceBlocked('Invalid expected settlement')
    # Validate identity before any remote I/O; repeat under an IMMEDIATE write lock.
    def matching_checkout():
        row = connection.execute('''SELECT o.provider,o.state,o.provider_reference,f.kind,f.regime
             FROM regime_payment_outbox o JOIN regime_fence_operations f
             ON f.operation_id=o.operation_id WHERE o.operation_id=?''', (operation_id,)).fetchone()
        return row is not None and tuple(row) == (provider, 'confirmed', provider_reference, 'checkout', 'COMMERCIAL')

    if not matching_checkout():
        raise FenceBlocked('Confirmed commercial checkout not found')
    if verifier is not None:
        observation = verifier(provider_reference, amount_minor, currency)
    elif provider == 'stripe':
        observation = verify_stripe_payment_with_reversals(
            provider_reference, credentials['secret_key'], amount_minor, currency, client=client)
    else:
        observation = verify_paypal_payment_with_capture_observations(
            provider_reference, credentials['client_id'], credentials['client_secret'],
            amount_minor, currency, environment=credentials['environment'], client=client)
    if not isinstance(observation, dict) or (
        observation.get('provider') != provider or observation.get('reference') != provider_reference
        or type(observation.get('amount_minor')) is not int
        or observation['amount_minor'] != amount_minor
        or observation.get('currency', '').upper() != currency.upper()
        or observation.get('remote_payment_observed') is not True
        or observation.get('local_ledger_reconciled') is not False
        or observation.get('authorizes_entitlement') is not False
        or observation.get('authorizes_cutover') is not False
    ):
        raise FenceBlocked('Provider observation does not match expected checkout')
    connection.execute('BEGIN IMMEDIATE')
    try:
        if not matching_checkout():
            raise FenceBlocked('Checkout changed during provider lookup')
        outcome = record_observation(connection, operation_id, observation, evidence_id=evidence_id)
        connection.commit()
    except BaseException:
        connection.rollback()
        raise
    return {**outcome, 'settlement_authorized': False, 'transition_authorized': False}
