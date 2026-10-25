import hashlib
import sqlite3

import pytest

from app.regime_operation_fence import FenceBlocked, admit, apply_provider_event, initialize


@pytest.fixture
def db(tmp_path):
    c = sqlite3.connect(tmp_path / 'fence.sqlite')
    initialize(c, initial_regime='COMMERCIAL')
    c.commit()
    c.execute('CREATE TABLE balances (id INTEGER PRIMARY KEY, cents INTEGER NOT NULL)')
    c.execute('INSERT INTO balances VALUES (1,0)')
    c.commit()
    c.execute('BEGIN IMMEDIATE')
    admit(c, 'checkout:1', 'checkout')
    c.commit()
    yield c
    c.close()


def event(c, event_id='evt1', digest=None, action=None):
    if digest is None:
        digest = hashlib.sha256(b'raw event').hexdigest()
    if action is None:
        def action(conn, receipt):
            conn.execute('UPDATE balances SET cents=cents+100 WHERE id=1')
    return apply_provider_event(c, provider='stripe', event_id=event_id,
                                operation_id='checkout:1', payload_sha256=digest, action=action)


def test_duplicate_event_does_not_credit_twice(db):
    assert event(db)['applied']
    assert event(db)['duplicate']
    assert db.execute('SELECT cents FROM balances').fetchone()[0] == 100


def test_repeated_event_identity_with_changed_payload_rejected(db):
    event(db)
    with pytest.raises(FenceBlocked):
        event(db, digest='0' * 64)
    assert db.execute('SELECT cents FROM balances').fetchone()[0] == 100


def test_failed_action_rollback_and_retry(db):
    def broken(conn, receipt):
        conn.execute('UPDATE balances SET cents=cents+100 WHERE id=1')
        raise RuntimeError('failure')
    with pytest.raises(RuntimeError):
        event(db, action=broken)
    assert db.execute('SELECT cents FROM balances').fetchone()[0] == 0
    assert event(db)['applied']
    assert db.execute('SELECT cents FROM balances').fetchone()[0] == 100


def test_unknown_checkout_fails_closed(db):
    with pytest.raises(FenceBlocked):
        apply_provider_event(db, provider='paypal', event_id='e', operation_id='unknown',
                             payload_sha256='a'*64, action=lambda c,r: None)


def test_persistent_retry_after_restart(tmp_path):
    path = tmp_path / 'persist.sqlite'
    c = sqlite3.connect(path)
    initialize(c, initial_regime='COMMERCIAL'); c.commit()
    c.execute('CREATE TABLE balances (id INTEGER PRIMARY KEY, cents INTEGER NOT NULL)'); c.execute('INSERT INTO balances VALUES (1,0)');c.commit()
    c.execute('BEGIN IMMEDIATE'); admit(c,'checkout:1','checkout');c.commit()
    event(c)
    c.close()
    c = sqlite3.connect(path)
    assert event(c)['duplicate']
    assert c.execute('SELECT cents FROM balances').fetchone()[0] == 100
    c.close()


def test_reject_noncommercial_provider_payment(tmp_path):
    db = sqlite3.connect(tmp_path / 'nc.sqlite')
    initialize(db)
    db.execute('CREATE TABLE balances (id INTEGER PRIMARY KEY, cents INTEGER NOT NULL)')
    db.execute('INSERT INTO balances VALUES(1,0)')
    db.commit()
    db.execute('BEGIN IMMEDIATE')
    admit(db,'checkout:1','checkout')
    db.commit()
    # Default regime is noncommercial. A signed payment must not be sufficient
    # to turn a noncommercial admission into a commercial credit grant.
    with pytest.raises(FenceBlocked, match='noncommercial checkout'):
        event(db)
    assert db.execute('SELECT cents FROM balances').fetchone()[0] == 0


def test_accept_previously_authorized_commercial_checkout(tmp_path):
    c = sqlite3.connect(tmp_path / 'commercial.sqlite')
    initialize(c, initial_regime='COMMERCIAL')
    c.execute('CREATE TABLE balances (id INTEGER PRIMARY KEY, cents INTEGER NOT NULL)')
    c.execute('INSERT INTO balances VALUES(1,0)')
    c.commit()
    c.execute('BEGIN IMMEDIATE')
    admit(c,'checkout:1','checkout', required_regime='COMMERCIAL')
    c.commit()
    assert event(c)['applied']
    assert event(c)['duplicate']
    assert c.execute('SELECT cents FROM balances').fetchone()[0] == 100
    c.close()
