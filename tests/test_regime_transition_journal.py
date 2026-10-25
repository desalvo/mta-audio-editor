import sqlite3
import pytest
from app.regime_operation_fence import FenceBlocked, initialize, admit
from app.regime_transition_journal import reserve, abort, pending


def db(path):
    return sqlite3.connect(path, isolation_level=None)


def good():
    return {'ready': True, 'unresolved': [], 'snapshot': 'verified-test-evidence'}


def test_persistent_reservation_blocks_new_job(tmp_path):
    path = tmp_path / 'db.sqlite'
    with db(path) as c:
        initialize(c)
        c.execute('BEGIN IMMEDIATE')
        assert reserve(c, transition_id='a', target='COMMERCIAL', expected_revision=0, evidence=good())['reserved']
        c.commit()
    with db(path) as c:
        assert len(pending(c)) == 1
        c.execute('BEGIN IMMEDIATE')
        with pytest.raises(FenceBlocked):
            admit(c, 'job:late', 'job')
        abort(c, transition_id='a')
        c.commit()
        assert pending(c) == []


def test_failed_reservation_rolls_back(tmp_path):
    with db(tmp_path / 'db.sqlite') as c:
        initialize(c)
        c.execute('BEGIN IMMEDIATE')
        with pytest.raises(FenceBlocked):
            reserve(c, transition_id='bad', target='COMMERCIAL', expected_revision=0,
                    evidence={'ready': True, 'unresolved': ['unknown-provider']})
        c.rollback()
        assert pending(c) == []


def test_idempotency_and_conflicting_replay(tmp_path):
    with db(tmp_path / 'db.sqlite') as c:
        initialize(c)
        c.execute('BEGIN IMMEDIATE')
        reserve(c, transition_id='a', target='COMMERCIAL', expected_revision=0, evidence=good())
        assert reserve(c, transition_id='a', target='COMMERCIAL', expected_revision=0, evidence=good())['idempotent']
        with pytest.raises(FenceBlocked):
            reserve(c, transition_id='a', target='COMMERCIAL', expected_revision=0,
                    evidence={**good(), 'snapshot': 'different'})
        c.rollback()


def test_open_checkout_blocks_reservation(tmp_path):
    with db(tmp_path / 'db.sqlite') as c:
        initialize(c)
        c.execute('BEGIN IMMEDIATE')
        admit(c, 'checkout:pending', 'checkout')
        with pytest.raises(FenceBlocked):
            reserve(c, transition_id='a', target='COMMERCIAL', expected_revision=0, evidence=good())
        c.rollback()
