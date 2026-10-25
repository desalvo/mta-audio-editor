"""Transactional Stripe webhook inbox for previously fenced checkouts.

Invoked only after Stripe signature verification and inside the caller-owned
BEGIN IMMEDIATE transaction. Legacy events continue to use the pre-existing
credit_payment_events journal pending separate reconciliation.
"""
from __future__ import annotations

import re

from .regime_operation_fence import FenceBlocked


def prepare(connection, *, event_id: str, order_id: str, payload_sha256: str) -> bool:
    """Validate an enrolled checkout, and detect conflicting event identities.

    Returns False for legacy un-fenced orders. Caller must record the event
    via ``mark_applied`` in its very same transaction as the credit mutation.
    """
    if not connection.in_transaction:
        raise FenceBlocked('Stripe inbox requires a caller-owned transaction')
    if not isinstance(event_id, str) or not 1 <= len(event_id) <= 200:
        raise ValueError('Invalid Stripe event ID')
    if not isinstance(order_id, str) or not order_id:
        raise ValueError('Invalid Stripe order ID')
    if not isinstance(payload_sha256, str) or not re.fullmatch('[a-f0-9]{64}', payload_sha256):
        raise ValueError('Invalid Stripe event digest')
    receipt = connection.execute(
        "SELECT kind,regime FROM regime_fence_operations WHERE operation_id=?",
        (f'checkout:stripe:{order_id}',)
    ).fetchone() if connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='regime_fence_operations'"
    ).fetchone() else None
    if receipt is None:
        return False
    if receipt[0] != 'checkout' or receipt[1] != 'COMMERCIAL':
        raise FenceBlocked('Stripe event refers to an incompatible checkout epoch')
    connection.execute('''CREATE TABLE IF NOT EXISTS regime_provider_inbox (
        provider TEXT NOT NULL, event_id TEXT NOT NULL, operation_id TEXT NOT NULL,
        payload_sha256 TEXT NOT NULL, state TEXT NOT NULL CHECK(state IN ('received','applied')),
        PRIMARY KEY(provider,event_id))''')
    prior = connection.execute(
        'SELECT operation_id,payload_sha256,state FROM regime_provider_inbox WHERE provider=? AND event_id=?',
        ('stripe', event_id)
    ).fetchone()
    if prior is not None:
        if prior[0] != f'checkout:stripe:{order_id}' or prior[1] != payload_sha256:
            raise FenceBlocked('Stripe event identity reused with conflicting payload')
        if prior[2] == 'applied':
            return True
        raise FenceBlocked('Stripe event has incomplete prior receipt')
    return True


def mark_applied(connection, *, event_id: str, order_id: str, payload_sha256: str) -> None:
    """Append the event atomically after the caller's financial mutation."""
    if not connection.in_transaction:
        raise FenceBlocked('Stripe inbox requires a caller-owned transaction')
    connection.execute(
        "INSERT INTO regime_provider_inbox(provider,event_id,operation_id,payload_sha256,state) VALUES('stripe',?,?,?,'applied')",
        (event_id, f'checkout:stripe:{order_id}', payload_sha256)
    )
