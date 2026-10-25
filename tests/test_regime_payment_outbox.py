import sqlite3
import pytest

from app.regime_operation_fence import initialize, admit, FenceBlocked
from app.regime_payment_outbox import enqueue, mark_attempt_uncertain, confirm


def db(tmp_path):
    c=sqlite3.connect(tmp_path/'outbox.sqlite', isolation_level=None)
    c.execute('PRAGMA foreign_keys=ON')
    initialize(c,initial_regime='COMMERCIAL')
    return c


def test_enqueue_atomic_and_idempotent(tmp_path):
    c=db(tmp_path)
    c.execute('BEGIN IMMEDIATE')
    admit(c,'checkout:stripe:123','checkout',required_regime='COMMERCIAL')
    assert enqueue(c,provider='stripe',order_id='123',request_key='stripe-123')['created']
    assert not enqueue(c,provider='stripe',order_id='123',request_key='stripe-123')['created']
    with pytest.raises(FenceBlocked):
        enqueue(c,provider='stripe',order_id='123',request_key='different')
    c.rollback()
    assert c.execute("SELECT name FROM sqlite_master WHERE name='regime_payment_outbox'").fetchone() is None
    c.close()


def test_uncertain_never_resends_without_reconciliation(tmp_path):
    c=db(tmp_path)
    c.execute('BEGIN IMMEDIATE')
    admit(c,'checkout:paypal:12','checkout',required_regime='COMMERCIAL')
    enqueue(c,provider='paypal',order_id='12',request_key='p-12')
    c.commit()
    c.execute('BEGIN IMMEDIATE')
    mark_attempt_uncertain(c,'checkout:paypal:12')
    c.commit()
    c.close()
    c=db(tmp_path)
    c.execute('BEGIN IMMEDIATE')
    with pytest.raises(FenceBlocked,match='reconcile'):
        mark_attempt_uncertain(c,'checkout:paypal:12')
    confirm(c,'checkout:paypal:12',provider_reference='provider-order-1')
    confirm(c,'checkout:paypal:12',provider_reference='provider-order-1')
    with pytest.raises(FenceBlocked):
        confirm(c,'checkout:paypal:12',provider_reference='provider-order-2')
    c.rollback()
    c.close()


def test_unenrolled_checkout_and_noncommercial_rejected(tmp_path):
    c=db(tmp_path)
    c.execute('BEGIN IMMEDIATE')
    with pytest.raises(FenceBlocked):
        enqueue(c,provider='stripe',order_id='x',request_key='x')
    c.rollback(); c.close()


def test_pending_checkout_cannot_be_confirmed_without_dispatch(tmp_path):
    c=db(tmp_path)
    c.execute('BEGIN IMMEDIATE')
    admit(c,'checkout:stripe:pending','checkout',required_regime='COMMERCIAL')
    enqueue(c,provider='stripe',order_id='pending',request_key='stripe-pending')
    with pytest.raises(FenceBlocked,match='dispatched'):
        confirm(c,'checkout:stripe:pending',provider_reference='remote-pending')
    assert c.execute("SELECT state FROM regime_payment_outbox WHERE operation_id='checkout:stripe:pending'").fetchone()[0]=='pending'
    c.rollback();c.close()


def test_confirm_rejects_settled_fence(tmp_path):
    c=db(tmp_path)
    c.execute('BEGIN IMMEDIATE')
    admit(c,'checkout:stripe:settled','checkout',required_regime='COMMERCIAL')
    enqueue(c,provider='stripe',order_id='settled',request_key='stripe-settled')
    mark_attempt_uncertain(c,'checkout:stripe:settled')
    # Simulate a stale/out-of-order confirmation following closure.
    c.execute("UPDATE regime_fence_operations SET status='closed' WHERE operation_id='checkout:stripe:settled'")
    with pytest.raises(FenceBlocked,match='Open commercial'):
        confirm(c,'checkout:stripe:settled',provider_reference='remote-settled')
    c.rollback();c.close()


def test_confirm_rejects_transition_and_epoch_mismatch(tmp_path):
    c=db(tmp_path)
    c.execute('BEGIN IMMEDIATE')
    admit(c,'checkout:stripe:epoch','checkout',required_regime='COMMERCIAL')
    enqueue(c,provider='stripe',order_id='epoch',request_key='stripe-epoch')
    mark_attempt_uncertain(c,'checkout:stripe:epoch')
    c.execute('UPDATE regime_fence_state SET transitioning=1 WHERE singleton=1')
    with pytest.raises(FenceBlocked,match='transition'):
        confirm(c,'checkout:stripe:epoch',provider_reference='remote-epoch')
    c.execute('UPDATE regime_fence_state SET transitioning=0,revision=revision+1 WHERE singleton=1')
    with pytest.raises(FenceBlocked,match='epoch'):
        confirm(c,'checkout:stripe:epoch',provider_reference='remote-epoch')
    assert c.execute("SELECT state FROM regime_payment_outbox WHERE operation_id='checkout:stripe:epoch'").fetchone()[0]=='uncertain'
    c.rollback(); c.close()


def test_dispatch_rejects_transition_or_stale_epoch(tmp_path):
    c=db(tmp_path)
    c.execute('BEGIN IMMEDIATE')
    admit(c,'checkout:paypal:guard','checkout',required_regime='COMMERCIAL')
    enqueue(c,provider='paypal',order_id='guard',request_key='paypal-guard')
    c.execute('UPDATE regime_fence_state SET transitioning=1 WHERE singleton=1')
    with pytest.raises(FenceBlocked,match='transition'):
        mark_attempt_uncertain(c,'checkout:paypal:guard')
    c.execute('UPDATE regime_fence_state SET transitioning=0,revision=revision+1 WHERE singleton=1')
    with pytest.raises(FenceBlocked,match='epoch'):
        mark_attempt_uncertain(c,'checkout:paypal:guard')
    assert c.execute("SELECT attempts FROM regime_payment_outbox WHERE operation_id='checkout:paypal:guard'").fetchone()[0]==0
    c.rollback(); c.close()
