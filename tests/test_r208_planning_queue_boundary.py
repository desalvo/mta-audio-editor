
import pytest
from app.ai_job_queue import AIJobQueue, MAX_JOBS


def test_reject_unsafe_plans_without_queue_mutation():
    q = AIJobQueue()
    invalid = [None, [], {'value': float('nan')}, {'value': float('inf')},
               {'set': {1, 2}}, {1: 'bad'}, {'bad': b'bytes'},
               {'huge': 'x' * (1024 * 1024 + 1)}]
    recursive = {}
    recursive['self'] = recursive
    invalid.append(recursive)
    too_deep = {'root': {}}
    node = too_deep['root']
    for _ in range(35):
        node['child'] = {}
        node = node['child']
    invalid.append(too_deep)
    for plan in invalid:
        with pytest.raises(ValueError):
            q.submit('project', 'owner', 'remix', plan)
    assert not q._jobs


def test_json_detachment_and_unicode_size():
    q = AIJobQueue()
    original = {'message': '🎵', 'nested': [{'n': 4}]}
    result = q.submit('p', 'a', 'remix', original)
    original['nested'][0]['n'] = 99
    result['plan']['nested'][0]['n'] = 88
    assert q.get(result['id'], 'p', 'a')['plan']['nested'][0]['n'] == 4
    with pytest.raises(ValueError):
        q.submit('p', 'a', 'remix', {'message': '🎵' * (1024 * 1024 // 4 + 1)})


def test_authorization_cancel_idempotence_and_fifo_capacity():
    q = AIJobQueue()
    with pytest.raises(ValueError):
        q.submit('', 'owner', 'remix', {})
    with pytest.raises(ValueError):
        q.submit('project', ' ', 'remix', {})
    first = q.submit('p', 'alice', 'remix', {})
    assert q.cancel(first['id'], 'p', 'bob') is None
    cancelled = q.cancel(first['id'], 'p', 'alice')
    assert cancelled['status'] == 'cancelled' and cancelled['cancelled_at']
    assert q.cancel(first['id'], 'p', 'alice')['cancelled_at'] == cancelled['cancelled_at']
    for _ in range(MAX_JOBS):
        q.submit('p', 'alice', 'remix', {})
    assert q.get(first['id'], 'p', 'alice') is None
    with pytest.raises(ValueError):
        q.submit('p', 'alice', 'remix', {})
