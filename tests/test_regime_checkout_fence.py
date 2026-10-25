"""Real SQLite rollback and idempotency tests for provider checkout admission."""
import json
import sqlite3
import pytest
from app import auth
from app.regime_checkout_fence import enroll, settle_if_enrolled, verify_enrolled_payment
from app.regime_operation_fence import FenceBlocked

@pytest.fixture
def connection(tmp_path,monkeypatch):
    monkeypatch.setattr(auth,'DATA_ROOT',tmp_path)
    (tmp_path/'service-regime.json').write_text(json.dumps({'regime':'COMMERCIAL','revision':0}))
    con=sqlite3.connect(tmp_path/'billing.sqlite')
    yield con
    con.close()

def test_checkout_enrollment_atomic_and_retry(connection):
    connection.execute('BEGIN IMMEDIATE')
    assert enroll(connection,'stripe','abc')['status']=='open'
    assert enroll(connection,'stripe','abc')['status']=='open'
    connection.commit()
    connection.execute('BEGIN IMMEDIATE')
    assert settle_if_enrolled(connection,'stripe','abc')
    assert settle_if_enrolled(connection,'stripe','abc')
    connection.commit()
    assert connection.execute("SELECT COUNT(*) FROM regime_fence_operations").fetchone()[0] == 1

def test_checkout_rollback(connection):
    connection.execute('BEGIN IMMEDIATE')
    enroll(connection,'paypal','a')
    connection.rollback()
    assert connection.execute("SELECT name FROM sqlite_master WHERE name='regime_fence_operations'").fetchone() is None

def test_checkout_refuses_regime_drift(connection):
    connection.execute('BEGIN IMMEDIATE')
    enroll(connection,'stripe','a')
    connection.commit()
    (auth.data_root()/'service-regime.json').write_text(json.dumps({'regime':'NON_COMMERCIAL','revision':1}))
    connection.execute('BEGIN IMMEDIATE')
    with pytest.raises(FenceBlocked):enroll(connection,'stripe','b')
    connection.rollback()


def test_verified_payment_requires_commercial_origin(connection):
    connection.execute('BEGIN IMMEDIATE')
    assert not verify_enrolled_payment(connection, 'stripe', 'legacy')
    enroll(connection, 'stripe', 'new')
    assert verify_enrolled_payment(connection, 'stripe', 'new')
    connection.execute("UPDATE regime_fence_operations SET regime='NON_COMMERCIAL' WHERE operation_id='checkout:stripe:new'")
    with pytest.raises(FenceBlocked):
        verify_enrolled_payment(connection, 'stripe', 'new')
    connection.rollback()


def test_paypal_refund_receipt_rejects_noncommercial_origin(connection):
    connection.execute('BEGIN IMMEDIATE')
    enroll(connection, 'paypal', 'refund-origin')
    assert verify_enrolled_payment(connection, 'paypal', 'refund-origin')
    connection.execute("UPDATE regime_fence_operations SET regime='NON_COMMERCIAL' WHERE operation_id='checkout:paypal:refund-origin'")
    with pytest.raises(FenceBlocked):
        verify_enrolled_payment(connection, 'paypal', 'refund-origin')
    connection.rollback()


@pytest.mark.parametrize('provider', ['stripe', 'paypal'])
def test_checkout_settlement_requires_confirmed_dispatch(connection, provider):
    from app.regime_payment_outbox import enqueue, mark_attempt_uncertain, confirm
    order = 'settle-guard-' + provider
    op = 'checkout:' + provider + ':' + order
    connection.execute('BEGIN IMMEDIATE')
    enroll(connection, provider, order)
    enqueue(connection, provider=provider, order_id=order, request_key='request-'+provider)
    connection.commit()
    connection.execute('BEGIN IMMEDIATE')
    with pytest.raises(FenceBlocked, match='verified provider'):
        settle_if_enrolled(connection, provider, order)
    mark_attempt_uncertain(connection, op)
    with pytest.raises(FenceBlocked, match='verified provider'):
        settle_if_enrolled(connection, provider, order)
    confirm(connection, op, provider_reference='provider-'+provider)
    assert settle_if_enrolled(connection, provider, order)
    connection.commit()
    assert connection.execute('SELECT status FROM regime_fence_operations WHERE operation_id=?', (op,)).fetchone()[0]=='closed'


def test_confirmed_dispatch_cannot_settle_during_transition(connection):
    from app.regime_payment_outbox import enqueue, mark_attempt_uncertain, confirm
    provider, order = 'stripe', 'blocked-during-transition'
    op = f'checkout:{provider}:{order}'
    connection.execute('BEGIN IMMEDIATE')
    enroll(connection, provider, order)
    enqueue(connection, provider=provider, order_id=order, request_key='transition-key')
    mark_attempt_uncertain(connection, op)
    confirm(connection, op, provider_reference='provider-order')
    connection.execute('UPDATE regime_fence_state SET transitioning=1 WHERE singleton=1')
    with pytest.raises(FenceBlocked, match='transition'):
        settle_if_enrolled(connection, provider, order)
    connection.rollback()
