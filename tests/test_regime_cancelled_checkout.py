import sqlite3

import pytest

from app.regime_cancelled_checkout import close_verified_noncreated_checkout
from app.regime_operation_fence import FenceBlocked, initialize, admit
from app.regime_payment_outbox import enqueue, mark_attempt_uncertain, reconcile_verified_outcome


def setup(provider='stripe'):
    c=sqlite3.connect(':memory:')
    c.execute('BEGIN IMMEDIATE')
    initialize(c,initial_regime='COMMERCIAL')
    c.execute("UPDATE regime_fence_state SET regime='COMMERCIAL'")
    c.execute('CREATE TABLE credit_purchase_orders (id TEXT PRIMARY KEY,status TEXT,paid_at INTEGER,payment_intent TEXT,refunded_cents INTEGER)')
    c.execute('CREATE TABLE paypal_orders (id TEXT PRIMARY KEY,status TEXT,paid_at INTEGER,provider_order TEXT,refund_due_micro INTEGER)')
    c.execute('CREATE TABLE paypal_captures (id TEXT PRIMARY KEY,order_id TEXT)')
    c.execute('CREATE TABLE paypal_refunds (id TEXT PRIMARY KEY,order_id TEXT)')
    c.execute("INSERT INTO credit_purchase_orders VALUES ('x','pending',NULL,NULL,0)")
    c.execute("INSERT INTO paypal_orders VALUES ('x','pending',NULL,NULL,0)")
    op=f'checkout:{provider}:x'
    admit(c,op,'checkout',required_regime='COMMERCIAL')
    enqueue(c,provider=provider,order_id='x',request_key=f'key-{provider}')
    mark_attempt_uncertain(c,op)
    reconcile_verified_outcome(c,op,provider=provider,outcome='not_created')
    c.commit()
    return c,op


@pytest.mark.parametrize('provider', ['stripe','paypal'])
def test_closes_only_provider_verified_noncreation(provider):
    c,op=setup(provider)
    c.execute('BEGIN IMMEDIATE')
    assert close_verified_noncreated_checkout(c,provider=provider,order_id='x')['closed']
    c.commit()
    assert c.execute('SELECT status FROM regime_fence_operations WHERE operation_id=?',(op,)).fetchone()[0]=='closed'
    c.execute('BEGIN IMMEDIATE')
    assert close_verified_noncreated_checkout(c,provider=provider,order_id='x')['already_closed']
    c.rollback()


@pytest.mark.parametrize('provider', ['stripe','paypal'])
def test_blocks_money_and_rolls_back(provider):
    c,op=setup(provider)
    c.execute("UPDATE credit_purchase_orders SET paid_at=123 WHERE id='x'" if provider=='stripe' else "UPDATE paypal_orders SET paid_at=123 WHERE id='x'")
    c.commit()
    c.execute('BEGIN IMMEDIATE')
    with pytest.raises(FenceBlocked):
        close_verified_noncreated_checkout(c,provider=provider,order_id='x')
    c.rollback()
    assert c.execute('SELECT status FROM regime_fence_operations WHERE operation_id=?',(op,)).fetchone()[0]=='open'


def test_requires_caller_transaction():
    c,_=setup()
    with pytest.raises(FenceBlocked):
        close_verified_noncreated_checkout(c,provider='stripe',order_id='x')


def test_no_false_negative_after_confirmed_provider():
    c,_=setup()
    c.execute("UPDATE regime_payment_outbox SET state='confirmed',provider_reference='pi_valid'")
    c.commit()
    c.execute('BEGIN IMMEDIATE')
    with pytest.raises(FenceBlocked):
        close_verified_noncreated_checkout(c,provider='stripe',order_id='x')
    c.rollback()
