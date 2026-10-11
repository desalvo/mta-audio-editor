"""Retained results cannot leak across users, be tampered with or rerun AI."""
import pytest
from app import ai_result_cache as cache

@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    monkeypatch.setenv('MTA_AI_RESULT_CACHE_DIR', str(tmp_path))

KEY = 'client-request-cache-12345'

def test_owner_only_replay():
    assert cache.save(1, KEY, b'RIFFtest', 'audio/wav', 'j1')
    assert cache.load(1, KEY, 'j1') == (b'RIFFtest', 'audio/wav')
    assert cache.load(2, KEY, 'j1') is None
    assert cache.load(1, KEY, 'wrong-job') is None

def test_tampered_payload_rejected(tmp_path):
    cache.save(1, KEY, b'RIFFtest', 'audio/wav', 'j1')
    blob, _ = cache._paths(tmp_path, 1, KEY)
    blob.write_bytes(b'changed')
    assert cache.load(1, KEY, 'j1') is None

def test_invalid_inputs_rejected():
    with pytest.raises(ValueError):
        cache.save(1, KEY, b'data', 'text/html', 'j1')
    with pytest.raises(ValueError):
        cache.save(1, '../unsafe', b'data', 'audio/wav', 'j1')

def test_cache_opt_in(monkeypatch):
    monkeypatch.delenv('MTA_AI_RESULT_CACHE_DIR')
    assert cache.save(1, KEY, b'data', 'audio/wav', 'j1') is False
    assert cache.load(1, KEY, 'j1') is None
