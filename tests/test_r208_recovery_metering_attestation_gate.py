"""A cached result cannot settle a request with unauthenticated metering."""
import json

from app import ai_result_cache as cache


def test_unsigned_cache_still_recovers(tmp_path, monkeypatch):
    monkeypatch.setenv('MTA_AI_RESULT_CACHE_DIR', str(tmp_path))
    key = 'recover-unsigned-result-1234'
    cache.save(1, key, b'valid', 'application/json', 'worker-one')
    assert cache.recover_completed_job_id(1, key) == 'worker-one'


def test_tampered_metering_blocks_recovery(tmp_path, monkeypatch):
    monkeypatch.setenv('MTA_AI_RESULT_CACHE_DIR', str(tmp_path))
    key = 'recover-signed-result-12345'
    cache.save(1, key, b'valid', 'application/json', 'worker-one')
    _, metadata = cache._paths(tmp_path, 1, key)
    details = json.loads(metadata.read_text())
    details['metering_envelope'] = {'worker_id': 'forged'}
    metadata.write_text(json.dumps(details))
    assert cache.recover_completed_job_id(1, key) is None


def test_valid_metering_must_be_verified_on_recovery(tmp_path, monkeypatch):
    monkeypatch.setenv('MTA_AI_RESULT_CACHE_DIR', str(tmp_path))
    key = 'recover-attested-result-1234'
    cache.save(1, key, b'valid', 'application/json', 'worker-one')
    _, metadata = cache._paths(tmp_path, 1, key)
    details = json.loads(metadata.read_text())
    details['metering_envelope'] = {'worker_id': 'worker-one'}
    metadata.write_text(json.dumps(details))
    from app import ai_remote_metering_attestation as attestation, ai_remote_keyring
    calls = []
    monkeypatch.setattr(ai_remote_keyring, 'active_keyring', lambda: {'test': b'fake'})
    def verify(keys, envelope, *, job_id, request_id, worker_id):
        calls.append((job_id, request_id, worker_id))
        assert worker_id == 'worker-one'
    monkeypatch.setattr(attestation, 'verify_rotating', verify)
    assert cache.recover_completed_job_id(1, key) == 'worker-one'
    assert calls == [('worker-one', key, 'worker-one')]
