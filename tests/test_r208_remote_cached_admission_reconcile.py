"""Crash-safe reconciliation of already-published remote job results."""
from app import ai_request_dedup as dedup, ai_result_cache


def test_reconcile_cached_result_after_crash(tmp_path, monkeypatch):
    monkeypatch.setenv('MTA_AI_RESULT_CACHE_DIR', str(tmp_path))
    monkeypatch.setattr(dedup, 'db', _database(tmp_path))
    key = 'remote-completion-12345678'
    digest = dedup.fingerprint('whisper', b'{}', b'wave')
    dedup.admit(1, key, digest)
    assert dedup.reconcile_published(1, key)['state'] == 'admitted'
    assert ai_result_cache.save(1, key, b'valid-result', 'application/json', 'worker-01')
    status = dedup.reconcile_published(1, key)
    assert status['state'] == 'completed' and status['job_id'] == 'worker-01'
    assert dedup.reconcile_published(1, key) == status
    assert dedup.request_status(2, key) is None


def test_corrupted_cache_never_completes(tmp_path, monkeypatch):
    monkeypatch.setenv('MTA_AI_RESULT_CACHE_DIR', str(tmp_path))
    monkeypatch.setattr(dedup, 'db', _database(tmp_path))
    key = 'remote-completion-87654321'
    dedup.admit(1, key, dedup.fingerprint('whisper', b'{}', b'wave'))
    ai_result_cache.save(1, key, b'valid-result', 'application/json', 'worker-02')
    blob, _ = ai_result_cache._paths(tmp_path, 1, key)
    blob.write_bytes(b'other-result')
    assert dedup.reconcile_published(1, key)['state'] == 'admitted'


def _database(tmp_path):
    import sqlite3
    from contextlib import contextmanager
    path = tmp_path / 'dedup.sqlite3'
    @contextmanager
    def connect():
        db = sqlite3.connect(path)
        db.row_factory = sqlite3.Row
        try:
            yield db
            db.commit()
        finally:
            db.close()
    return connect
