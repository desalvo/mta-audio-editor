"""End-to-end local financial identity enforcement, including legacy duplicated rows."""
import sqlite3
import pytest
from app.regime_operation_fence import initialize, admit, FenceBlocked
from app.regime_payment_outbox import enqueue, mark_attempt_uncertain, confirm, reconcile_verified_outcome
from app.regime_outbox_review import audit_checkout_integrity


def _two_orders(tmp_path, provider):
    c = sqlite3.connect(tmp_path / 'identities.db', isolation_level=None)
    c.execute('PRAGMA foreign_keys=ON')
    initialize(c, initial_regime='COMMERCIAL')
    ops = []
    for i in (1, 2):
        op = f'checkout:{provider}:order-{i}'
        c.execute('BEGIN IMMEDIATE')
        admit(c, op, 'checkout', required_regime='COMMERCIAL')
        enqueue(c, provider=provider, order_id=f'order-{i}', request_key=f'{provider}-key-{i}')
        c.commit()
        c.execute('BEGIN IMMEDIATE')
        mark_attempt_uncertain(c, op)
        c.commit()
        ops.append(op)
    return c, ops


@pytest.mark.parametrize('provider', ['stripe', 'paypal'])
@pytest.mark.parametrize('method', ['confirm', 'reconcile'])
def test_duplicate_remote_reference_rejected_without_mutation(tmp_path, provider, method):
    c, (first, second) = _two_orders(tmp_path, provider)
    def apply(op, ref):
        if method == 'confirm':
            confirm(c, op, provider_reference=ref)
        else:
            reconcile_verified_outcome(c, op, provider=provider,
                                       outcome='confirmed', provider_reference=ref)
    c.execute('BEGIN IMMEDIATE')
    apply(first, 'remote-checkout-1')
    c.commit()
    c.execute('BEGIN IMMEDIATE')
    with pytest.raises(FenceBlocked, match='already assigned'):
        apply(second, 'remote-checkout-1')
    assert c.execute('SELECT state, provider_reference FROM regime_payment_outbox WHERE operation_id=?',
                     (second,)).fetchone() == ('uncertain', None)
    c.rollback()
    c.execute('BEGIN IMMEDIATE')
    apply(second, 'remote-checkout-2')
    c.commit()
    assert audit_checkout_integrity(c)['verified']
    c.close()


@pytest.mark.parametrize('provider', ['stripe', 'paypal'])
def test_existing_duplicate_legacy_data_blocks_integrity_audit(tmp_path, provider):
    c, (first, second) = _two_orders(tmp_path, provider)
    c.execute("UPDATE regime_payment_outbox SET state='confirmed',provider_reference='legacy-dup'")
    audit = audit_checkout_integrity(c)
    assert audit['verified'] is False
    assert audit['inconsistencies']['reused_provider_reference'] == 1
    c.close()
