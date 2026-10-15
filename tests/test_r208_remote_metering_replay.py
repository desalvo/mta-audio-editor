import json


import pytest

from app import ai_result_cache
from app.ai_remote_metering_attestation import sign_rotating


KEY = b'K' * 32


def setup_cache(monkeypatch, tmp_path):
    monkeypatch.setenv('MTA_AI_RESULT_CACHE_DIR', str(tmp_path))
    monkeypatch.setenv('MTA_AI_REMOTE_METERING_KEYS_JSON', json.dumps({'active': KEY.hex()}))
    monkeypatch.setattr(ai_result_cache, 'cleanup_if_due', lambda: {})


def envelope(*, request='request-12345678', job='job_1'):
    return sign_rotating(KEY, key_id='active', job_id=job,
                         request_id=request, worker_id='worker_1',
                         usage={'cpu_seconds': 2.25})


def test_attested_result_survives_cache_replay(monkeypatch, tmp_path):
    setup_cache(monkeypatch, tmp_path)
    proof = envelope()
    assert ai_result_cache.save(4, 'request-12345678', b'example', 'application/json', 'job_1', metering_envelope=proof)
    assert ai_result_cache.load_with_metering(4, 'request-12345678', 'job_1') == (b'example', 'application/json', proof)


def test_revoked_key_refuses_replay(monkeypatch, tmp_path):
    setup_cache(monkeypatch, tmp_path)
    ai_result_cache.save(4, 'request-12345678', b'example', 'application/json', 'job_1', metering_envelope=envelope())
    monkeypatch.setenv('MTA_AI_REMOTE_METERING_KEYS_JSON', json.dumps({'replacement': (b'R' * 32).hex()}))
    assert ai_result_cache.load_with_metering(4, 'request-12345678', 'job_1') is None


@pytest.mark.parametrize('field,value', [('job_id', 'other'), ('request_id', 'other'), ('worker_id', 'other'), ('signature', '0' * 64), ('key_id', 'unknown')])
def test_mismatched_signed_metadata_rejected(monkeypatch, tmp_path, field, value):
    setup_cache(monkeypatch, tmp_path)
    proof = {**envelope(), field: value}
    with pytest.raises(ValueError):
        ai_result_cache.save(4, 'request-12345678', b'example', 'application/json', 'job_1', metering_envelope=proof)


def test_legacy_cached_payload_remains_available(monkeypatch, tmp_path):
    setup_cache(monkeypatch, tmp_path)
    ai_result_cache.save(4, 'request-12345678', b'example', 'application/json', 'job_1')
    assert ai_result_cache.load_with_metering(4, 'request-12345678', 'job_1') == (b'example', 'application/json', None)


def test_metering_metadata_tampering_rejected(monkeypatch, tmp_path):
    setup_cache(monkeypatch, tmp_path)
    ai_result_cache.save(4, 'request-12345678', b'example', 'application/json', 'job_1', metering_envelope=envelope())
    root = ai_result_cache._root()
    _, path = ai_result_cache._paths(root, 4, 'request-12345678')
    details = json.loads(path.read_text())
    details['metering_envelope']['usage']['cpu_seconds'] = 99
    path.write_text(json.dumps(details))
    assert ai_result_cache.load_with_metering(4, 'request-12345678', 'job_1') is None
