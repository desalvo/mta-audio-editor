"""Capacity pressure must never purge an unverified planning record."""
import json
import sqlite3
import pytest
from app.ai_planning_sqlite import SQLitePlanningQueue
from app.ai_job_queue import MAX_JOBS


def test_corrupt_oldest_terminal_blocks_eviction_and_preserves_rows(tmp_path):
    path = tmp_path / 'planning.sqlite'
    queue = SQLitePlanningQueue(path)
    first = queue.submit('p', 'owner', 'remix', {'n': 0})
    queue.cancel(first['id'], 'p', 'owner')
    for n in range(1, MAX_JOBS):
        queue.submit('p', 'owner', 'remix', {'n': n})
    with sqlite3.connect(path) as db:
        db.execute('UPDATE planning_jobs SET payload=? WHERE id=?', ('{', first['id']))
    with pytest.raises(ValueError, match='corrupt'):
        queue.submit('p', 'owner', 'remix', {'n': 'new'})
    with sqlite3.connect(path) as db:
        assert db.execute('SELECT count(*) FROM planning_jobs').fetchone()[0] == MAX_JOBS
        assert db.execute('SELECT payload FROM planning_jobs WHERE id=?', (first['id'],)).fetchone()[0] == '{'


def test_terminal_owner_mismatch_blocks_eviction(tmp_path):
    path = tmp_path / 'planning.sqlite'
    queue = SQLitePlanningQueue(path)
    first = queue.submit('p', 'owner', 'remix', {})
    queue.cancel(first['id'], 'p', 'owner')
    for _ in range(MAX_JOBS - 1):
        queue.submit('p', 'owner', 'remix', {})
    with sqlite3.connect(path) as db:
        payload = json.loads(db.execute('SELECT payload FROM planning_jobs WHERE id=?', (first['id'],)).fetchone()[0])
        payload['owner_id'] = 'attacker'
        db.execute('UPDATE planning_jobs SET payload=? WHERE id=?', (json.dumps(payload), first['id']))
    with pytest.raises(ValueError, match='identity mismatch'):
        queue.submit('p', 'owner', 'remix', {})
    with sqlite3.connect(path) as db:
        assert db.execute('SELECT count(*) FROM planning_jobs').fetchone()[0] == MAX_JOBS
