"""Enroll commercial checkout orders in the durable regime fence.

The caller must already own a BEGIN IMMEDIATE transaction. Never hold that
transaction while making calls to payment providers. Existing pre-fence orders
remain readable and require conservative transition reconciliation.
"""
from __future__ import annotations

from . import auth
from .regime_operation_fence import FenceBlocked, admit, initialize, settle
from .service_regime import read_regime


def enroll(connection, provider: str, order_id: str) -> dict:
    if provider not in {'stripe', 'paypal'}:
        raise ValueError('Unsupported provider')
    if not connection.in_transaction:
        raise FenceBlocked('Checkout enrollment requires a transaction')
    configured = read_regime(auth.data_root() / 'service-regime.json')
    # A process cannot create new commercial orders against a stale fence.
    initialize(connection, initial_regime=configured.regime.value)
    state = connection.execute('SELECT regime,revision FROM regime_fence_state WHERE singleton=1').fetchone()
    if tuple(state) != (configured.regime.value, configured.revision):
        raise FenceBlocked('Checkout regime and persisted configuration differ')
    return admit(connection, f'checkout:{provider}:{order_id}', 'checkout', required_regime='COMMERCIAL')


def settle_if_enrolled(connection, provider: str, order_id: str) -> bool:
    """Close an admitted checkout in the caller's existing payment transaction.

    For pre-fence orders, preserve legacy fulfillment and require a separate
    reconciliation before transition. Do not invent a historical admission.
    """
    if provider not in {'stripe', 'paypal'}:
        raise ValueError('Unsupported provider')
    if not connection.in_transaction:
        raise FenceBlocked('Checkout settlement requires a transaction')
    op_id = f'checkout:{provider}:{order_id}'
    exists = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='regime_fence_operations'"
    ).fetchone()
    if not exists:
        return False
    if connection.execute('SELECT 1 FROM regime_fence_operations WHERE operation_id=?', (op_id,)).fetchone() is None:
        return False
    # A checkout that was dispatched using the durable outbox must never be
    # closed while its provider creation outcome is still unknown.  This is
    # checked under the caller's payment transaction, together with settlement.
    has_outbox = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='regime_payment_outbox'"
    ).fetchone()
    if has_outbox:
        dispatch = connection.execute(
            'SELECT state FROM regime_payment_outbox WHERE operation_id=?', (op_id,)
        ).fetchone()
        if dispatch is not None:
            from .regime_outcome_receipt import require_open_commercial_checkout
            require_open_commercial_checkout(connection, op_id)
            if dispatch[0] != 'confirmed':
                raise FenceBlocked('Cannot close checkout before verified provider dispatch confirmation')
    settle(connection, op_id)
    return True


def verify_enrolled_payment(connection, provider: str, order_id: str) -> bool:
    """Validate a signed provider receipt against its original checkout epoch.

    Legacy orders are deliberately not rewritten into synthetic fence entries;
    reconciliation must account for them before switching regimes.
    """
    if provider not in {'stripe', 'paypal'}:
        raise ValueError('Unsupported provider')
    if not connection.in_transaction:
        raise FenceBlocked('Payment verification requires caller transaction')
    existing = connection.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='regime_fence_operations'"
    ).fetchone()
    if not existing:
        return False
    receipt = connection.execute(
        'SELECT kind,regime,revision,status FROM regime_fence_operations WHERE operation_id=?',
        (f'checkout:{provider}:{order_id}',)
    ).fetchone()
    if receipt is None:
        return False
    if receipt[0] != 'checkout' or receipt[1] != 'COMMERCIAL':
        raise FenceBlocked('Payment receipt has invalid originating regime')
    return True
