import pytest
from app.ai_job_queue import AIJobQueue


def test_planning_history_scoped_paginated_and_detached():
    queue = AIJobQueue()
    a = queue.submit('project', 'alice', 'remix', {'secret': 1})
    queue.submit('project', 'bob', 'remix', {'secret': 2})
    b = queue.submit('project', 'alice', 'rearrange', {'secret': 3})
    queue.submit('other', 'alice', 'remix', {'secret': 4})
    queue.cancel(b['id'], 'project', 'alice')
    first = queue.list('project', 'alice', limit=1)
    assert first['total'] == 2 and len(first['items']) == 1
    assert first['items'][0]['id'] == a['id']
    assert first['durable'] is False and first['generation_available'] is False
    first['items'][0]['plan']['secret'] = 'tampered'
    assert queue.get(a['id'], 'project', 'alice')['plan']['secret'] == 1
    assert queue.list('project', 'alice', offset=1)['items'][0]['id'] == b['id']
    assert queue.list('project', 'alice', status='cancelled')['total'] == 1
    assert queue.list('project', 'bob')['total'] == 1
    assert queue.list('other', 'alice')['total'] == 1
    assert queue.list('project', 'mallory')['total'] == 0


@pytest.mark.parametrize('arguments', [
    {'limit': 0}, {'limit': 101}, {'limit': True}, {'offset': -1},
    {'offset': 129}, {'offset': False}, {'status': 'running'},
])
def test_planning_history_rejects_invalid_filters(arguments):
    q = AIJobQueue()
    q.submit('p', 'o', 'remix', {})
    with pytest.raises(ValueError):
        q.list('p', 'o', **arguments)
    assert q.list('p', 'o')['total'] == 1
