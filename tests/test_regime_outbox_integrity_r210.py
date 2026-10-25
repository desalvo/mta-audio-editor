import sqlite3

import pytest

from app.regime_operation_fence import initialize, admit, settle, FenceBlocked
from app.regime_payment_outbox import enqueue, mark_attempt_uncertain, confirm
from app.regime_outbox_review import audit_checkout_integrity


def test_missing_schema_fails_closed():
    with pytest.raises(FenceBlocked):
        audit_checkout_integrity(sqlite3.connect(':memory:'))


def make_db():
    con = sqlite3.connect(':memory:', isolation_level=None)
    initialize(con, initial_regime='COMMERCIAL')
    con.execute('BEGIN IMMEDIATE')
    admit(con, 'checkout:stripe:x', 'checkout', required_regime='COMMERCIAL')
    enqueue(con, provider='stripe', order_id='x', request_key='x')
    con.commit()
    return con


def test_pending_and_confirmed_state_read_only():
    con = make_db()
    before = con.total_changes
    check = audit_checkout_integrity(con)
    assert check['verified'] and check['outstanding_dispatches'] == 1
    assert not check['transition_safe'] and con.total_changes == before
    con.execute('BEGIN IMMEDIATE'); mark_attempt_uncertain(con,'checkout:stripe:x'); con.commit()
    con.execute('BEGIN IMMEDIATE'); confirm(con,'checkout:stripe:x',provider_reference='cs_1'); con.commit()
    assert audit_checkout_integrity(con)['verified']
    con.execute('BEGIN IMMEDIATE'); settle(con,'checkout:stripe:x'); con.commit()
    check = audit_checkout_integrity(con)
    assert check['outstanding_dispatches'] == 0 and not check['transition_safe']


@pytest.mark.parametrize('sql,reason', [
    ("UPDATE regime_payment_outbox SET attempts=2 WHERE operation_id='checkout:stripe:x'", 'pending_with_attempts'),
    ("UPDATE regime_payment_outbox SET state='confirmed', attempts=1 WHERE operation_id='checkout:stripe:x'", 'missing_provider_reference'),
    ("UPDATE regime_payment_outbox SET provider_reference='cs_1' WHERE operation_id='checkout:stripe:x'", 'unexpected_provider_reference'),
    ("UPDATE regime_fence_operations SET status='closed' WHERE operation_id='checkout:stripe:x'", 'unresolved_checkout_closed'),
    ("DELETE FROM regime_fence_operations WHERE operation_id='checkout:stripe:x'", 'missing_receipt'),
])
def test_integrity_detects_inconsistencies(sql, reason):
    con = make_db()
    con.execute('PRAGMA foreign_keys=OFF')
    con.execute(sql)
    check = audit_checkout_integrity(con)
    assert not check['verified'] and check['inconsistencies'][reason] == 1
