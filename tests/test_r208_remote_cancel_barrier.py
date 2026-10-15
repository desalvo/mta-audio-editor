
import pytest
from fastapi import HTTPException
from app import ai_request_dedup as d
from app import ai_billing_routes as routes


def test_cancel_invalid_key_rejected():
    with pytest.raises(ValueError):
        d.cancel_admitted(1, '../bad')


def test_cancel_no_database_record(monkeypatch):
    class FakeDB:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def execute(self, sql, args=()):
            class Cursor:
                def fetchone(self): return None
            return Cursor()
    monkeypatch.setattr(d, 'db', lambda: FakeDB())
    assert d.cancel_admitted(1, 'a'*20) is None


def test_cancel_requires_authentication(monkeypatch):
    class Req:
        headers = {}
    monkeypatch.setattr(routes.ai_access, 'authenticate', lambda _: None)
    with pytest.raises(HTTPException) as ex:
        routes.remote_request_cancel('a'*20, Req())
    assert ex.value.status_code == 401


def test_cancel_response_does_not_claim_worker_stopped(monkeypatch):
    class Req:
        headers = {'authorization':'Bearer token'}
    monkeypatch.setattr(routes.ai_access, 'authenticate', lambda _: {'user_id': 15})
    monkeypatch.setattr(d, 'cancel_admitted', lambda uid, key: {'state':'cancelled', 'job_id':None})
    assert routes.remote_request_cancel('a'*20, Req()) == {
        'state':'cancelled', 'job_id':None, 'worker_stop_guaranteed':False}

@pytest.mark.parametrize('request_id', ['x', '../unauthorized', '', 'abc?def'*4])
def test_client_cancel_rejects_invalid_request_id(request_id):
    from app.ai_remote_client import cancel_remote_request
    with pytest.raises(ValueError):
        cancel_remote_request('https://example.org', 'token', request_id)


def test_client_cancel_never_calls_network_with_invalid_token():
    from app.ai_remote_client import cancel_remote_request
    with pytest.raises(ValueError):
        cancel_remote_request('https://example.org', 'bad\ntoken', 'a'*20)
