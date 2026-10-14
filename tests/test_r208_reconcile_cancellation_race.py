"""Concurrent cancellation must win over stale cache reconciliation."""
import pytest
from app import ai_request_dedup as dedup
from test_r208_remote_cached_admission_reconcile import _database


def test_cancellation_wins_after_cache_probe(tmp_path, monkeypatch):
    monkeypatch.setattr(dedup, 'db', _database(tmp_path))
    key = 'race-reconcile-cancel-1234'
    dedup.admit(1, key, dedup.fingerprint('whisper', b'{}', b'input'))
    from app import ai_result_cache
    def cancelled_during_load(uid, rid):
        assert (uid, rid) == (1, key)
        assert dedup.cancel_admitted(uid, rid)['state'] == 'cancelled'
        return 'worker-already-published'
    monkeypatch.setattr(ai_result_cache, 'recover_completed_job_id', cancelled_during_load)
    assert dedup.reconcile_published(1, key)['state'] == 'cancelled'
    assert dedup.request_status(1, key)['state'] == 'cancelled'


def test_failed_state_wins_after_cache_probe(tmp_path, monkeypatch):
    monkeypatch.setattr(dedup, 'db', _database(tmp_path))
    key = 'race-reconcile-failed-1234'
    dedup.admit(1, key, dedup.fingerprint('whisper', b'{}', b'input'))
    from app import ai_result_cache
    def failed_during_load(uid, rid):
        dedup.finalize(uid, rid, state='failed')
        return 'worker-already-published'
    monkeypatch.setattr(ai_result_cache, 'recover_completed_job_id', failed_during_load)
    assert dedup.reconcile_published(1, key)['state'] == 'failed'


@pytest.mark.parametrize('key', [None, 1234, [], {}, True])
def test_request_status_handles_malformed_keys(key):
    with pytest.raises(ValueError, match='idempotency key'):
        dedup.request_status(1, key)
