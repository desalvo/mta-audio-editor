"""Planning journal consistency at read/update boundaries (r208 unchanged)."""

import sqlite3
import pytest
from app.ai_planning_sqlite import SQLitePlanningQueue


def test_get_uses_explicit_read_snapshot(tmp_path, monkeypatch):
    queue = SQLitePlanningQueue(tmp_path / 'plans.db')
    item = queue.submit('p', 'o', 'remix', {'x': 1})
    original = queue._audit_owner_records
    def audit(connection, pid, owner):
        assert connection.in_transaction
        return original(connection, pid, owner)
    monkeypatch.setattr(queue, '_audit_owner_records', audit)
    assert queue.get(item['id'], 'p', 'o')['id'] == item['id']


def test_cancel_rejects_corruption_in_other_owner_scoped_record(tmp_path):
    queue = SQLitePlanningQueue(tmp_path / 'plans.db')
    first = queue.submit('p', 'o', 'remix', {'x': 1})
    second = queue.submit('p', 'o', 'rearrange', {'x': 2})
    with sqlite3.connect(queue.path) as db:
        db.execute('UPDATE planning_jobs SET payload=? WHERE id=?', ('{broken', second['id']))
    with pytest.raises(ValueError):
        queue.cancel(first['id'], 'p', 'o')
    with sqlite3.connect(queue.path) as db:
        assert db.execute('SELECT status FROM planning_jobs WHERE id=?', (first['id'],)).fetchone()[0] == 'planned'


def test_cancel_keeps_owner_isolation_with_other_owner_corruption(tmp_path):
    queue = SQLitePlanningQueue(tmp_path / 'plans.db')
    first = queue.submit('p', 'o', 'remix', {'x': 1})
    second = queue.submit('p', 'different', 'remix', {'x': 2})
    with sqlite3.connect(queue.path) as db:
        db.execute('UPDATE planning_jobs SET payload=? WHERE id=?', ('{broken', second['id']))
    assert queue.cancel(first['id'], 'p', 'o')['status'] == 'cancelled'


def test_list_decodes_inside_read_transaction(tmp_path, monkeypatch):
    queue = SQLitePlanningQueue(tmp_path / 'plans.db')
    queue.submit('p', 'o', 'remix', {'x': 1})
    original = queue._decode
    def checked(row, **kwargs):
        # Under a valid read transaction an independent writer cannot alter
        # the page between the audit and the decode.
        assert snapshot_connection[0].in_transaction
        return original(row, **kwargs)
    original_connect = queue._connect
    snapshot_connection = []
    def connect():
        connection = original_connect()
        snapshot_connection[:] = [connection]
        return connection
    monkeypatch.setattr(queue, '_connect', connect)
    monkeypatch.setattr(queue, '_decode', checked)
    assert queue.list('p', 'o')['total'] == 1
