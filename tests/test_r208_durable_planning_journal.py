
import pytest
from app.ai_planning_sqlite import SQLitePlanningQueue
from app.ai_job_queue import MAX_JOBS


def test_restart_and_owner_isolation(tmp_path):
    db = tmp_path / 'planning.sqlite'
    a = SQLitePlanningQueue(db)
    job = a.submit('p', 'alice', 'remix', {'text': 'hello'})
    b = SQLitePlanningQueue(db)
    assert b.get(job['id'], 'p', 'alice')['plan']['text'] == 'hello'
    assert b.get(job['id'], 'p', 'bob') is None
    assert b.cancel(job['id'], 'p', 'bob') is None
    result = b.cancel(job['id'], 'p', 'alice')
    assert result['status'] == 'cancelled'
    assert SQLitePlanningQueue(db).cancel(job['id'], 'p', 'alice')['cancelled_at'] == result['cancelled_at']
    assert a.list('p', 'alice')['durable'] is True


def test_atomic_capacity_across_instances(tmp_path):
    db = tmp_path / 'planning.sqlite'
    a, b = SQLitePlanningQueue(db), SQLitePlanningQueue(db)
    for i in range(MAX_JOBS):
        (a if i % 2 else b).submit('p', 'alice', 'remix', {'n': i})
    with pytest.raises(ValueError, match='capacity'):
        b.submit('p', 'alice', 'remix', {})
    old = a.list('p', 'alice')['items'][0]
    b.cancel(old['id'], 'p', 'alice')
    a.submit('p', 'alice', 'rearrange', {})
    assert b.get(old['id'], 'p', 'alice') is None
    assert a.list('p', 'alice')['total'] == MAX_JOBS


def test_invalid_payload_does_not_evict_terminal(tmp_path):
    q = SQLitePlanningQueue(tmp_path / 'planning.sqlite')
    job = q.submit('p', 'o', 'remix', {})
    q.cancel(job['id'], 'p', 'o')
    cyclic = {}
    cyclic['cycle'] = cyclic
    with pytest.raises(ValueError):
        q.submit('p', 'o', 'remix', cyclic)
    assert q.get(job['id'], 'p', 'o') is not None


def test_invalid_database_paths(tmp_path):
    relative = 'planning.sqlite'
    with pytest.raises(ValueError):
        SQLitePlanningQueue(relative)
    target = tmp_path / 'target'
    target.write_text('')
    link = tmp_path / 'symlink'
    link.symlink_to(target)
    with pytest.raises(ValueError):
        SQLitePlanningQueue(link)


def test_persisted_history_pagination(tmp_path):
    q = SQLitePlanningQueue(tmp_path / 'planning.sqlite')
    a = q.submit('p', 'one', 'remix', {})
    q.submit('p', 'two', 'remix', {})
    b = q.submit('p', 'one', 'rearrange', {})
    q.cancel(b['id'], 'p', 'one')
    assert q.list('p', 'one', limit=1)['items'][0]['id'] == a['id']
    assert q.list('p', 'one', offset=1)['items'][0]['id'] == b['id']
    assert q.list('p', 'one', status='cancelled')['total'] == 1
    assert q.list('p', 'two')['total'] == 1


def test_concurrent_submissions_never_exceed_capacity(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    path = tmp_path / 'planning.sqlite'
    queues = [SQLitePlanningQueue(path) for _ in range(4)]
    def submit(n):
        try:
            return queues[n % 4].submit('p', 'o', 'remix', {'n': n})['id']
        except ValueError as exc:
            assert 'capacity' in str(exc)
            return None
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(submit, range(MAX_JOBS + 24)))
    assert len(set(r for r in results if r)) == MAX_JOBS
    assert SQLitePlanningQueue(path).list('p', 'o', limit=100)['total'] == MAX_JOBS


def test_invalid_filters_match_volatile_queue(tmp_path):
    q = SQLitePlanningQueue(tmp_path / 'planning.sqlite')
    for kwargs in ({'limit': True}, {'offset': False}, {'offset': MAX_JOBS + 1},
                   {'status': 'running'}, {'limit': 101}):
        with pytest.raises(ValueError):
            q.list('p', 'o', **kwargs)
