"""GET result may reconcile the durable blob without a preliminary status request."""
from contextlib import contextmanager
import sqlite3
import pytest
from fastapi import HTTPException
from starlette.requests import Request
from app import ai_request_dedup as dedup, ai_result_cache, ai_billing_routes, ai_access


def _request():
    return Request({'type': 'http', 'method': 'GET', 'path': '/', 'headers': [(b'authorization', b'Bearer test')]})


def _configure(tmp_path, monkeypatch):
    monkeypatch.setenv('MTA_AI_RESULT_CACHE_DIR', str(tmp_path / 'cache'))
    path = tmp_path / 'dedup.db'
    @contextmanager
    def db():
        c = sqlite3.connect(path)
        c.row_factory = sqlite3.Row
        try:
            yield c
            c.commit()
        finally:
            c.close()
    monkeypatch.setattr(dedup, 'db', db)
    monkeypatch.setattr(ai_access, 'authenticate', lambda token: {'user_id': 1, 'id': 2} if token == 'test' else None)
    return 'recovery-direct-123456789'


def test_get_result_recovers_published_cache_without_status_call(tmp_path, monkeypatch):
    key = _configure(tmp_path, monkeypatch)
    dedup.admit(1, key, dedup.fingerprint('whisper', b'{}', b'wav'))
    ai_result_cache.save(1, key, b'AI WAV bytes', 'audio/wav', 'worker-123')
    response = ai_billing_routes.remote_request_result(key, _request())
    assert response.body == b'AI WAV bytes'
    assert response.headers['x-mta-ai-job-id'] == 'worker-123'
    assert dedup.request_status(1, key)['state'] == 'completed'
    response2 = ai_billing_routes.remote_request_result(key, _request())
    assert response2.body == response.body


def test_get_result_does_not_finalize_corrupt_cache(tmp_path, monkeypatch):
    key = _configure(tmp_path, monkeypatch)
    dedup.admit(1, key, dedup.fingerprint('whisper', b'{}', b'wav'))
    ai_result_cache.save(1, key, b'AI WAV bytes', 'audio/wav', 'worker-123')
    blob, _ = ai_result_cache._paths(tmp_path / 'cache', 1, key)
    blob.write_bytes(b'corrupted')
    with pytest.raises(HTTPException) as e:
        ai_billing_routes.remote_request_result(key, _request())
    assert e.value.status_code == 409
    assert dedup.request_status(1, key)['state'] == 'admitted'


def test_get_result_does_not_revive_cancelled_request(tmp_path, monkeypatch):
    key = _configure(tmp_path, monkeypatch)
    dedup.admit(1, key, dedup.fingerprint('whisper', b'{}', b'wav'))
    ai_result_cache.save(1, key, b'AI WAV bytes', 'audio/wav', 'worker-123')
    dedup.cancel_admitted(1, key)
    with pytest.raises(HTTPException) as e:
        ai_billing_routes.remote_request_result(key, _request())
    assert e.value.status_code == 409
    assert dedup.request_status(1, key)['state'] == 'cancelled'


def test_get_result_never_accesses_other_owner(tmp_path, monkeypatch):
    key = _configure(tmp_path, monkeypatch)
    dedup.admit(2, key, dedup.fingerprint('whisper', b'{}', b'wav'))
    ai_result_cache.save(2, key, b'private bytes', 'audio/wav', 'worker-123')
    with pytest.raises(HTTPException) as e:
        ai_billing_routes.remote_request_result(key, _request())
    assert e.value.status_code == 404
    assert dedup.request_status(2, key)['state'] == 'admitted'
