import pytest
from app.regime_admin_closure import close_negative_checkout
from app.regime_operation_fence import FenceBlocked
from test_regime_cancelled_checkout import setup


@pytest.mark.parametrize('provider', ['stripe', 'paypal'])
def test_administrative_closure_commits_and_retries(provider):
    connection, op = setup(provider)
    result = close_negative_checkout(connection, provider=provider, order_id='x')
    assert result['closed'] and not connection.in_transaction
    assert connection.execute('SELECT status FROM regime_fence_operations WHERE operation_id=?', (op,)).fetchone()[0] == 'closed'
    assert close_negative_checkout(connection, provider=provider, order_id='x')['already_closed']


@pytest.mark.parametrize('provider', ['stripe', 'paypal'])
def test_administrative_closure_fails_closed_when_money_exists(provider):
    connection, op = setup(provider)
    connection.execute("UPDATE credit_purchase_orders SET paid_at=123 WHERE id='x'" if provider=='stripe' else "UPDATE paypal_orders SET paid_at=123 WHERE id='x'")
    connection.commit()
    with pytest.raises(FenceBlocked):
        close_negative_checkout(connection, provider=provider, order_id='x')
    assert not connection.in_transaction
    assert connection.execute('SELECT status FROM regime_fence_operations WHERE operation_id=?', (op,)).fetchone()[0] == 'open'


def test_cannot_join_an_existing_transaction():
    connection, _ = setup()
    connection.execute('BEGIN IMMEDIATE')
    with pytest.raises(FenceBlocked):
        close_negative_checkout(connection, provider='stripe', order_id='x')
    connection.rollback()


def test_uncertain_dispatch_remains_open():
    connection, op = setup()
    connection.execute("UPDATE regime_payment_outbox SET state='uncertain' WHERE operation_id=?", (op,))
    connection.commit()
    with pytest.raises(FenceBlocked):
        close_negative_checkout(connection, provider='stripe', order_id='x')
    assert connection.execute('SELECT status FROM regime_fence_operations WHERE operation_id=?', (op,)).fetchone()[0] == 'open'
