"""Durable owner-scoped recovery discovery for real remote inference requests."""
from contextlib import contextmanager
import sqlite3

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from app import ai_request_dedup as dedup, ai_access
from app.ai_billing_routes import router
from app.auth import db


@pytest.fixture
def isolated(tmp_path, monkeypatch):
    path = tmp_path / 'claims.sqlite'
    @contextmanager
    def connect():
        con = sqlite3.connect(path)
        con.row_factory = sqlite3.Row
        try:
            yield con
            con.commit()
        except BaseException:
            con.rollback()
            raise
        finally:
            con.close()
    monkeypatch.setattr(dedup, 'db', connect)
    return connect


def test_empty_before_first_admission(isolated):
    assert dedup.list_requests(1)['total'] == 0


def test_owner_pagination_and_terminal_states(isolated):
    fingerprint = dedup.fingerprint('ace-step', b'{}', b'')
    for i in range(7):
        dedup.admit(1, f'owner-one-request-{i:04}', fingerprint)
    dedup.admit(2, 'other-owner-request-000', fingerprint)
    dedup.cancel_admitted(1, 'owner-one-request-0000')
    dedup.finalize(1, 'owner-one-request-0001', state='failed')
    dedup.finalize(1, 'owner-one-request-0002', job_id='worker-test')
    a = dedup.list_requests(1, limit=3)
    b = dedup.list_requests(1, limit=3, offset=3)
    assert a['total'] == b['total'] == 7
    assert len(a['items']) == len(b['items']) == 3
    assert not {x['request_key'] for x in a['items']} & {x['request_key'] for x in b['items']}
    assert all(x['request_key'].startswith('owner-one') for x in a['items'] + b['items'])
    assert dedup.list_requests(1, state='completed')['items'][0]['job_id'] == 'worker-test'
    assert dedup.list_requests(1, state='cancelled')['total'] == 1
    assert dedup.list_requests(2)['total'] == 1


def test_invalid_paging_and_corrupt_state_fail_closed(isolated):
    key='history-broken-state-0000'
    dedup.admit(1, key, dedup.fingerprint('ace-step', b'{}', b''))
    for kwargs in ({'limit': 101}, {'offset': -1}, {'state': 'finished'}, {'limit': 0}):
        with pytest.raises(ValueError):
            dedup.list_requests(1, **kwargs)
    with isolated() as con:
        con.execute('UPDATE ai_request_dedup SET state=? WHERE request_key=?', ('unknown', key))
    with pytest.raises(ValueError, match='Corrupt'):
        dedup.list_requests(1)


def test_http_owner_only(tmp_path, monkeypatch):
    monkeypatch.setenv('MTA_DATA_DIR', str(tmp_path / 'server'))
    with db() as con:
        con.execute('CREATE TABLE users(id INTEGER PRIMARY KEY, active INTEGER NOT NULL)')
        con.executemany('INSERT INTO users VALUES(?,1)', [(1,), (2,)])
    one=ai_access.issue(1, 'test')['token']
    two=ai_access.issue(2, 'test')['token']
    key='authenticated-discovery-0001'
    dedup.admit(1, key, dedup.fingerprint('ace-step', b'{}', b''))
    api=FastAPI();api.include_router(router); client=TestClient(api)
    url='/api/ai-jobs/requests'
    assert client.get(url).status_code == 401
    first=client.get(url, headers={'Authorization':f'Bearer {one}'})
    assert first.status_code == 200, first.text
    assert first.json()['items'][0]['request_key'] == key
    second=client.get(url, headers={'Authorization':f'Bearer {two}'})
    assert second.status_code == 200 and second.json()['items'] == []
    assert client.get(url+'?limit=101', headers={'Authorization':f'Bearer {one}'}).status_code == 400


def test_native_discovery_roundtrip_and_fail_closed(monkeypatch):
    import io
    import json
    from app import ai_remote_client as remote
    observed = []
    payload = {'items': [{'request_key': 'native-recovered-key-00001', 'state': 'completed',
                          'job_id': 'worker-01', 'created_at': 1780000000}],
               'total': 1, 'limit': 2, 'offset': 0}
    class Reply:
        def __init__(self, data): self.stream = io.BytesIO(data)
        def __enter__(self): return self
        def __exit__(self, *args): return False
        def read(self, size): return self.stream.read(size)
    def fake_urlopen(request, timeout):
        observed.append(request.full_url)
        return Reply(json.dumps(payload).encode())
    monkeypatch.setattr(remote, 'https_urlopen', fake_urlopen)
    result = remote.list_remote_requests('https://example.org', 'test-token', limit=2)
    assert result == payload and '/api/ai-jobs/requests?limit=2&offset=0' in observed[0]
    payload['items'][0]['job_id'] = None
    with pytest.raises(remote.RemoteAIError):
        remote.list_remote_requests('https://example.org', 'test-token', limit=2)
    with pytest.raises(ValueError):
        remote.list_remote_requests('http://example.org', 'test-token')
