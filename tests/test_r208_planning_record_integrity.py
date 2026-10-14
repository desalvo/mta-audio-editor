"""Fail-closed recovery tests for durable AI planning records."""
import json
import sqlite3
import pytest
from app.ai_planning_sqlite import SQLitePlanningQueue


def test_tampered_owner_payload_refused_on_get_list_cancel(tmp_path):
    path = tmp_path / 'plan.db'
    q = SQLitePlanningQueue(path)
    item = q.submit('project', 'alice', 'remix', {'prompt': 'ok'})
    tampered = {**item, 'owner_id': 'bob'}
    with sqlite3.connect(path) as db:
        db.execute('UPDATE planning_jobs SET payload=? WHERE id=?', (json.dumps(tampered), item['id']))
    with pytest.raises(ValueError, match='identity mismatch'):
        q.get(item['id'], 'project', 'alice')
    with pytest.raises(ValueError, match='identity mismatch'):
        q.list('project', 'alice')
    with pytest.raises(ValueError, match='identity mismatch'):
        q.cancel(item['id'], 'project', 'alice')
    with sqlite3.connect(path) as db:
        assert db.execute('SELECT status FROM planning_jobs WHERE id=?', (item['id'],)).fetchone()[0] == 'planned'


def test_tampered_status_cannot_be_cancelled(tmp_path):
    path = tmp_path / 'plan.db'
    q = SQLitePlanningQueue(path)
    item = q.submit('project', 'alice', 'rearrange', {})
    with sqlite3.connect(path) as db:
        db.execute("UPDATE planning_jobs SET status='cancelled' WHERE id=?", (item['id'],))
    with pytest.raises(ValueError, match='identity mismatch'):
        q.cancel(item['id'], 'project', 'alice')


def test_non_json_record_is_not_interpreted_as_missing(tmp_path):
    path = tmp_path / 'plan.db'
    q = SQLitePlanningQueue(path)
    item = q.submit('p', 'o', 'remix', {})
    with sqlite3.connect(path) as db:
        db.execute('UPDATE planning_jobs SET payload=? WHERE id=?', ('{', item['id']))
    with pytest.raises(ValueError, match='corrupt'):
        q.get(item['id'], 'p', 'o')


def test_schema_mismatch_refused_without_migration(tmp_path):
    path = tmp_path / 'plan.db'
    with sqlite3.connect(path) as db:
        db.execute('CREATE TABLE planning_jobs (seq INTEGER PRIMARY KEY, id TEXT)')
    with pytest.raises((ValueError, sqlite3.OperationalError)):
        SQLitePlanningQueue(path)
    with sqlite3.connect(path) as db:
        assert [r[1] for r in db.execute('PRAGMA table_info(planning_jobs)')] == ['seq', 'id']
