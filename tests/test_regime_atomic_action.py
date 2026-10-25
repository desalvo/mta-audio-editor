"""Transactional database-local operation integration; no external payment I/O."""
import sqlite3

import pytest

from app.regime_operation_fence import FenceBlocked, execute_atomic, initialize


def prepared(tmp_path):
    db = tmp_path / 'fence.sqlite'
    connection = sqlite3.connect(db)
    initialize(connection)
    connection.execute('CREATE TABLE events (id TEXT PRIMARY KEY, amount INTEGER NOT NULL)')
    connection.commit()
    return connection


def test_atomic_action_and_idempotency(tmp_path):
    connection = prepared(tmp_path)
    def action(db, receipt):
        db.execute('INSERT INTO events VALUES (?, ?)', (receipt['operation_id'], 9))
        return 'ok'
    first = execute_atomic(connection, 'event:123', 'webhook', action)
    again = execute_atomic(connection, 'event:123', 'webhook', action)
    assert first['applied'] is True and first['result'] == 'ok'
    assert again['applied'] is False
    assert connection.execute('SELECT COUNT(*) FROM events').fetchone()[0] == 1


def test_rollback_removes_admission_and_mutation(tmp_path):
    connection = prepared(tmp_path)
    def action(db, receipt):
        db.execute('INSERT INTO events VALUES (?, 2)', (receipt['operation_id'],))
        raise RuntimeError('fail after insert')
    with pytest.raises(RuntimeError):
        execute_atomic(connection, 'event:fail', 'webhook', action)
    assert connection.execute('SELECT COUNT(*) FROM events').fetchone()[0] == 0
    assert connection.execute('SELECT COUNT(*) FROM regime_fence_operations').fetchone()[0] == 0


def test_no_callback_when_regime_wrong(tmp_path):
    connection = prepared(tmp_path)
    with pytest.raises(FenceBlocked):
        execute_atomic(connection, 'checkout:1', 'checkout', lambda *_: 1, required_regime='COMMERCIAL')
    assert connection.execute('SELECT COUNT(*) FROM regime_fence_operations').fetchone()[0] == 0


def test_retries_survive_restart(tmp_path):
    connection = prepared(tmp_path)
    execute_atomic(connection, 'job:17', 'job', lambda db, r: db.execute('INSERT INTO events VALUES (?,1)', (r['operation_id'],)))
    connection.close()
    second = sqlite3.connect(tmp_path / 'fence.sqlite')
    assert execute_atomic(second, 'job:17', 'job', lambda *_: 1)['applied'] is False
    assert second.execute('SELECT COUNT(*) FROM events').fetchone()[0] == 1


def test_no_nested_transaction(tmp_path):
    connection = prepared(tmp_path)
    connection.execute('BEGIN IMMEDIATE')
    with pytest.raises(FenceBlocked):
        execute_atomic(connection, 'job:1', 'job', lambda *_: None)
    connection.rollback()
