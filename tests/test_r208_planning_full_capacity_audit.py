"""Planning journals refuse regular-file substitution and forged hidden rows."""
import json
import sqlite3
import pytest
from app.ai_planning_sqlite import SQLitePlanningQueue
from app.ai_job_queue import MAX_JOBS


def test_regular_database_replacement_rejected(tmp_path):
    path = tmp_path / 'plans.db'
    q = SQLitePlanningQueue(path)
    q.submit('p', 'o', 'remix', {})
    path.unlink()
    SQLitePlanningQueue(path)  # an otherwise valid replacement journal
    with pytest.raises(ValueError, match='replaced'):
        q.submit('p', 'o', 'remix', {})


def test_full_capacity_audits_even_unrelated_planned_row(tmp_path):
    path = tmp_path / 'plans.db'
    q = SQLitePlanningQueue(path)
    first = q.submit('p', 'o', 'remix', {})
    q.cancel(first['id'], 'p', 'o')
    for _ in range(MAX_JOBS - 1):
        q.submit('p', 'o', 'remix', {})
    with sqlite3.connect(path) as db:
        row = db.execute('SELECT id,payload FROM planning_jobs WHERE status=? LIMIT 1', ('planned',)).fetchone()
        payload = json.loads(row[1])
        payload['owner_id'] = 'forged'
        db.execute('UPDATE planning_jobs SET payload=? WHERE id=?', (json.dumps(payload), row[0]))
    with pytest.raises(ValueError, match='identity mismatch'):
        q.submit('p', 'o', 'remix', {})
    with sqlite3.connect(path) as db:
        assert db.execute('SELECT count(*) FROM planning_jobs').fetchone()[0] == MAX_JOBS
        assert db.execute('SELECT id FROM planning_jobs WHERE id=?', (first['id'],)).fetchone()
