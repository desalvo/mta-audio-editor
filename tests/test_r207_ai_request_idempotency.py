"""Repeat requests must never multiply accounted AI execution."""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
import pytest
from app import ai_request_dedup as d
from app.auth import db

@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    monkeypatch.setenv('MTA_DATA_DIR', str(tmp_path))


def test_same_key_blocked_even_after_completion():
    f = d.fingerprint('whisper', b'{}', b'audio')
    d.admit(1, 'client-request-id-00001', f)
    with pytest.raises(d.DuplicateAIRequest) as exc:
        d.admit(1, 'client-request-id-00001', f)
    assert exc.value.state == 'admitted'
    d.finalize(1, 'client-request-id-00001', job_id='job123')
    with pytest.raises(d.DuplicateAIRequest) as exc:
        d.admit(1, 'client-request-id-00001', f)
    assert (exc.value.state, exc.value.job_id) == ('completed', 'job123')


def test_same_key_changed_audio_rejected():
    d.admit(1, 'client-request-id-00002', d.fingerprint('whisper', b'{}', b'a'))
    with pytest.raises(ValueError, match='different request'):
        d.admit(1, 'client-request-id-00002', d.fingerprint('whisper', b'{}', b'b'))


def test_different_users_are_independent():
    f = d.fingerprint('whisper', b'{}', b'a')
    d.admit(1, 'client-request-id-00003', f)
    d.admit(2, 'client-request-id-00003', f)
    with db() as c:
        assert c.execute('SELECT COUNT(*) FROM ai_request_dedup').fetchone()[0] == 2


def test_simultaneous_admission_one_winner():
    f = d.fingerprint('whisper', b'{}', b'a')
    barrier = Barrier(6)
    def claim(_):
        barrier.wait()
        try:
            d.admit(1, 'client-request-id-00004', f)
            return 'winner'
        except d.DuplicateAIRequest:
            return 'duplicate'
    with ThreadPoolExecutor(max_workers=6) as pool:
        outcomes = list(pool.map(claim, range(6)))
    assert outcomes.count('winner') == 1
    assert outcomes.count('duplicate') == 5


def test_invalid_key_rejected():
    with pytest.raises(ValueError, match='idempotency key'):
        d.admit(1, 'bad', d.fingerprint('whisper', b'{}', b'a'))


def test_status_is_owner_scoped_and_transitions():
    f = d.fingerprint('whisper', b'{}', b'sound')
    assert d.request_status(11, 'client-request-id-00005') is None
    d.admit(11, 'client-request-id-00005', f)
    assert d.request_status(12, 'client-request-id-00005') is None
    assert d.request_status(11, 'client-request-id-00005')['state'] == 'admitted'
    d.finalize(11, 'client-request-id-00005', job_id='tracked')
    result = d.request_status(11, 'client-request-id-00005')
    assert result['state'] == 'completed'
    assert result['job_id'] == 'tracked'
    assert 'fingerprint' not in result and 'token' not in result


def test_status_invalid_key_and_failed_state():
    with pytest.raises(ValueError, match='idempotency key'):
        d.request_status(1, 'bad')
    key = 'client-request-id-00006'
    d.admit(1, key, d.fingerprint('demucs', b'{}', b'a'))
    d.finalize(1, key, state='failed')
    assert d.request_status(1, key)['state'] == 'failed'
