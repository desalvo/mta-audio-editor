import sqlite3
import pytest
from app.regime_operation_fence import initialize, admit, FenceBlocked
from app.regime_payment_outbox import enqueue, mark_attempt_uncertain, reconcile_verified_outcome


def setup(tmp_path, provider='stripe'):
    c=sqlite3.connect(tmp_path/'reconcile.sqlite', isolation_level=None)
    c.execute('PRAGMA foreign_keys=ON')
    initialize(c, initial_regime='COMMERCIAL')
    c.execute('BEGIN IMMEDIATE')
    op=f'checkout:{provider}:order-1'
    admit(c,op,'checkout',required_regime='COMMERCIAL')
    enqueue(c,provider=provider,order_id='order-1',request_key=f'{provider}-key')
    c.commit()
    c.execute('BEGIN IMMEDIATE')
    mark_attempt_uncertain(c,op)
    c.commit()
    return c,op

@pytest.mark.parametrize('provider', ['stripe','paypal'])
def test_confirm_reconcile_is_idempotent(tmp_path,provider):
    c,op=setup(tmp_path,provider)
    c.execute('BEGIN IMMEDIATE')
    assert reconcile_verified_outcome(c,op,provider=provider,outcome='confirmed',provider_reference='remote-1')['changed']
    assert not reconcile_verified_outcome(c,op,provider=provider,outcome='confirmed',provider_reference='remote-1')['changed']
    with pytest.raises(FenceBlocked):
        reconcile_verified_outcome(c,op,provider=provider,outcome='confirmed',provider_reference='remote-2')
    c.commit(); c.close()

@pytest.mark.parametrize('provider',['stripe','paypal'])
def test_negative_requires_verified_outcome_and_never_closes_fence(tmp_path,provider):
    c,op=setup(tmp_path,provider)
    c.execute('BEGIN IMMEDIATE')
    assert reconcile_verified_outcome(c,op,provider=provider,outcome='not_created')['state']=='cancelled'
    assert reconcile_verified_outcome(c,op,provider=provider,outcome='not_created')['changed'] is False
    assert c.execute('SELECT status FROM regime_fence_operations WHERE operation_id=?',(op,)).fetchone()[0]=='open'
    c.commit(); c.close()

def test_rollback_and_provider_conflict(tmp_path):
    c,op=setup(tmp_path)
    c.execute('BEGIN IMMEDIATE')
    with pytest.raises(FenceBlocked):
        reconcile_verified_outcome(c,op,provider='paypal',outcome='confirmed',provider_reference='x')
    reconcile_verified_outcome(c,op,provider='stripe',outcome='confirmed',provider_reference='x')
    c.rollback()
    assert c.execute('SELECT state FROM regime_payment_outbox WHERE operation_id=?',(op,)).fetchone()[0]=='uncertain'
    c.close()

@pytest.mark.parametrize('provider', ['stripe', 'paypal'])
def test_reconciliation_blocks_closed_receipt(tmp_path, provider):
    c, op = setup(tmp_path, provider)
    c.execute('BEGIN IMMEDIATE')
    c.execute("UPDATE regime_fence_operations SET status='closed' WHERE operation_id=?", (op,))
    with pytest.raises(FenceBlocked, match='Open commercial'):
        reconcile_verified_outcome(c, op, provider=provider, outcome='confirmed', provider_reference='remote')
    c.rollback()
    assert c.execute('SELECT state FROM regime_payment_outbox WHERE operation_id=?', (op,)).fetchone()[0] == 'uncertain'
    c.close()

@pytest.mark.parametrize('provider', ['stripe', 'paypal'])
def test_reconciliation_blocks_transition_and_stale_revision(tmp_path, provider):
    c, op = setup(tmp_path, provider)
    c.execute('BEGIN IMMEDIATE')
    c.execute('UPDATE regime_fence_state SET transitioning=1 WHERE singleton=1')
    with pytest.raises(FenceBlocked, match='transition'):
        reconcile_verified_outcome(c, op, provider=provider, outcome='not_created')
    c.execute('UPDATE regime_fence_state SET transitioning=0, revision=revision+1 WHERE singleton=1')
    with pytest.raises(FenceBlocked, match='epoch'):
        reconcile_verified_outcome(c, op, provider=provider, outcome='not_created')
    c.rollback(); c.close()
