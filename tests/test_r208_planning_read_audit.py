import json
import sqlite3
import pytest
from app.ai_planning_sqlite import SQLitePlanningQueue


def test_pagination_detects_corrupt_unreturned_row(tmp_path):
    queue = SQLitePlanningQueue(tmp_path / 'planning.sqlite')
    first = queue.submit('p', 'u', 'remix', {'x': 1})
    second = queue.submit('p', 'u', 'remix', {'x': 2})
    with sqlite3.connect(queue.path) as db:
        db.execute('UPDATE planning_jobs SET payload=? WHERE id=?', ('{bad', second['id']))
    with pytest.raises(ValueError):
        queue.list('p', 'u', limit=1)
    with pytest.raises(ValueError):
        queue.get(first['id'], 'p', 'u')


def test_status_filtered_page_cannot_hide_forged_status(tmp_path):
    queue = SQLitePlanningQueue(tmp_path / 'planning.sqlite')
    first = queue.submit('p', 'u', 'remix', {'x': 1})
    second = queue.submit('p', 'u', 'remix', {'x': 2})
    with sqlite3.connect(queue.path) as db:
        db.execute('UPDATE planning_jobs SET status=? WHERE id=?', ('failed', second['id']))
    with pytest.raises(ValueError):
        queue.list('p', 'u', status='planned', limit=1)


def test_read_audit_owner_scoped(tmp_path):
    queue = SQLitePlanningQueue(tmp_path / 'planning.sqlite')
    first = queue.submit('p', 'alice', 'remix', {'x': 1})
    second = queue.submit('p', 'bob', 'remix', {'x': 2})
    with sqlite3.connect(queue.path) as db:
        db.execute('UPDATE planning_jobs SET payload=? WHERE id=?', ('{bad', second['id']))
    assert queue.get(first['id'], 'p', 'alice')['id'] == first['id']
    assert queue.list('p', 'alice')['total'] == 1
