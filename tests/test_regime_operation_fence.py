import sqlite3
import threading

import pytest

from app.regime_operation_fence import (
    FenceBlocked, abort_transition, admit, begin_transition, initialize, settle,
)


def connect(path):
    connection = sqlite3.connect(path, timeout=5, isolation_level=None)
    connection.execute('PRAGMA busy_timeout=5000')
    return connection


def test_open_operation_blocks_transition_across_reopen(tmp_path):
    path = tmp_path / 'fence.sqlite'
    with connect(path) as c:
        initialize(c)
        c.execute('BEGIN IMMEDIATE')
        assert admit(c, 'stripe:123', 'checkout', required_regime='NON_COMMERCIAL')['status'] == 'open'
        c.commit()
    with connect(path) as c:
        c.execute('BEGIN IMMEDIATE')
        with pytest.raises(FenceBlocked, match='unsettled'):
            begin_transition(c, expected_revision=0, target='COMMERCIAL')
        settle(c, 'stripe:123')
        plan=begin_transition(c, expected_revision=0,target='COMMERCIAL')
        assert plan['reserved']
        with pytest.raises(FenceBlocked,match='transition in progress'):
            admit(c, 'job:new', 'job')
        abort_transition(c)
        c.commit()


def test_retries_do_not_duplicate_or_change_regime(tmp_path):
    with connect(tmp_path / 'f.sqlite') as c:
        initialize(c, initial_regime='COMMERCIAL')
        c.execute('BEGIN IMMEDIATE')
        original=admit(c,'order1','checkout',required_regime='COMMERCIAL')
        assert admit(c,'order1','checkout')==original
        with pytest.raises(FenceBlocked,match='Conflicting'):
            admit(c,'order1','webhook')
        settle(c,'order1')
        settle(c,'order1')
        c.commit()


def test_requires_write_transaction_and_correct_regime(tmp_path):
    with connect(tmp_path / 'f.sqlite') as c:
        initialize(c)
        with pytest.raises(FenceBlocked,match='BEGIN IMMEDIATE'):
            admit(c,'new','job')
        c.execute('BEGIN IMMEDIATE')
        with pytest.raises(FenceBlocked,match='not permitted'):
            admit(c,'stripe1','checkout',required_regime='COMMERCIAL')
        c.rollback()


def test_concurrent_admission_serializes_on_same_database(tmp_path):
    path=tmp_path/'shared.sqlite'
    with connect(path) as c:
        initialize(c)
    entered=threading.Event()
    allow_commit=threading.Event()
    results=[]
    def first():
        with connect(path) as c:
            c.execute('BEGIN IMMEDIATE')
            admit(c,'job:1','job')
            entered.set()
            allow_commit.wait(3)
            c.commit()
    def second():
        entered.wait(3)
        with connect(path) as c:
            c.execute('BEGIN IMMEDIATE')
            try:
                begin_transition(c,expected_revision=0,target='COMMERCIAL')
                results.append('unsafe')
            except FenceBlocked:
                results.append('blocked')
            c.rollback()
    a=threading.Thread(target=first)
    b=threading.Thread(target=second)
    a.start();b.start()
    allow_commit.set()
    a.join(5);b.join(5)
    assert results==['blocked']


def test_initialize_does_not_commit_callers_transaction(tmp_path):
    import sqlite3
    from app.regime_operation_fence import initialize
    c = sqlite3.connect(tmp_path / 'init-atomic.sqlite')
    c.execute('CREATE TABLE marker(v INTEGER)')
    c.commit()
    c.execute('BEGIN IMMEDIATE')
    c.execute('INSERT INTO marker VALUES (7)')
    initialize(c)
    assert c.in_transaction
    c.rollback()
    assert c.execute('SELECT COUNT(*) FROM marker').fetchone()[0] == 0
    assert c.execute("SELECT COUNT(*) FROM sqlite_master WHERE name='regime_fence_state'").fetchone()[0] == 0
    c.close()

def test_initialize_preserves_existing_admission_transaction(tmp_path):
    import sqlite3
    from app.regime_operation_fence import initialize, admit
    c = sqlite3.connect(tmp_path / 'admit-atomic.sqlite')
    c.execute('BEGIN IMMEDIATE')
    initialize(c)
    receipt = admit(c, 'test-job', 'job')
    assert receipt['regime'] == 'NON_COMMERCIAL'
    c.rollback()
    assert c.execute("SELECT COUNT(*) FROM sqlite_master WHERE name='regime_fence_operations'").fetchone()[0] == 0
    c.close()


def test_retry_cannot_rebind_checkout_to_different_regime(tmp_path):
    with connect(tmp_path / 'epoch.sqlite') as c:
        initialize(c, initial_regime='COMMERCIAL')
        c.execute('BEGIN IMMEDIATE')
        admit(c, 'checkout:1', 'checkout', required_regime='COMMERCIAL')
        with pytest.raises(FenceBlocked, match='not permitted'):
            admit(c, 'checkout:1', 'checkout', required_regime='NON_COMMERCIAL')
        c.rollback()

def test_open_replay_rejects_epoch_conflict_even_with_same_kind(tmp_path):
    with connect(tmp_path / 'epoch2.sqlite') as c:
        initialize(c, initial_regime='COMMERCIAL')
        c.execute('BEGIN IMMEDIATE')
        admit(c, 'job:1', 'job')
        c.execute('UPDATE regime_fence_state SET revision=revision+1 WHERE singleton=1')
        with pytest.raises(FenceBlocked, match='different regime epoch'):
            admit(c, 'job:1', 'job')
        c.rollback()
