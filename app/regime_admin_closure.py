"""Administrative settlement of provider-verified *non-created* checkouts.

Never accepts provider evidence from the request body. This only consumes the
previously recorded durable outcome, and rechecks the financial state inside
one SQLite write transaction.
"""
from __future__ import annotations

import sqlite3

from .regime_cancelled_checkout import close_verified_noncreated_checkout
from .regime_operation_fence import FenceBlocked


def close_negative_checkout(connection: sqlite3.Connection, *, provider: str, order_id: str) -> dict:
    """Transaction-owning, idempotent administrative financial closure."""
    if connection.in_transaction:
        raise FenceBlocked('Closure must own the SQLite transaction')
    connection.execute('BEGIN IMMEDIATE')
    try:
        result = close_verified_noncreated_checkout(connection, provider=provider, order_id=order_id)
        connection.commit()
        return result
    except BaseException:
        if connection.in_transaction:
            connection.rollback()
        raise
