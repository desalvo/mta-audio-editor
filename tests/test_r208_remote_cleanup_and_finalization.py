
import json
import os
import time

import pytest
from app import ai_result_cache as cache, ai_request_dedup as dedup


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    monkeypatch.setenv('MTA_DATA_DIR', str(tmp_path / 'data'))
    monkeypatch.setenv('MTA_AI_RESULT_CACHE_DIR', str(tmp_path / 'cache'))


def test_completed_request_requires_worker_job_and_is_idempotent():
    key = 'remote-finalization-00001'
    dedup.admit(1, key, dedup.fingerprint('whisper', b'{}', b'wav'))
    with pytest.raises(ValueError, match='requires'):
        dedup.finalize(1, key)
    dedup.finalize(1, key, job_id='job-ok')
    dedup.finalize(1, key, job_id='job-ok')
    with pytest.raises(ValueError, match='Conflicting'):
        dedup.finalize(1, key, state='failed')
    with pytest.raises(ValueError, match='Conflicting'):
        dedup.finalize(1, key, job_id='job-different')


def test_missing_or_wrong_owner_cannot_finalize_request():
    key = 'remote-finalization-00002'
    dedup.admit(1, key, dedup.fingerprint('whisper', b'{}', b'wav'))
    with pytest.raises(ValueError, match='Conflicting'):
        dedup.finalize(2, key, job_id='job-ok')
    with pytest.raises(ValueError, match='Conflicting'):
        dedup.finalize(1, 'unknown-remote-request-000', job_id='job-ok')
    assert dedup.request_status(1, key)['state'] == 'admitted'


def test_expired_cache_purge_does_not_follow_symlink(tmp_path):
    key = 'remote-cache-expiration-001'
    cache.save(1, key, b'wav-content', 'audio/wav', 'job1')
    root = cache._root()
    blob, meta = cache._paths(root, 1, key)
    details = json.loads(meta.read_text())
    details['expires_at'] = int(time.time()) - 1
    meta.write_text(json.dumps(details))
    destination = tmp_path / 'protected'
    destination.write_text('protected')
    blob.unlink()
    blob.symlink_to(destination)
    assert cache.purge_expired(dry_run=False)['removed'] == 0
    assert meta.exists() and destination.read_text() == 'protected'


def test_expired_cache_purge_rejects_hardlinked_blob(tmp_path):
    key = 'remote-cache-expiration-002'
    cache.save(1, key, b'wav-content', 'audio/wav', 'job2')
    root = cache._root()
    blob, meta = cache._paths(root, 1, key)
    details = json.loads(meta.read_text())
    details['expires_at'] = int(time.time()) - 1
    meta.write_text(json.dumps(details))
    outside = tmp_path / 'outside'
    os.link(blob, outside)
    assert cache.purge_expired(dry_run=False)['removed'] == 0
    assert outside.read_bytes() == b'wav-content'


def test_expired_cache_purge_removes_owned_pair():
    key = 'remote-cache-expiration-003'
    cache.save(1, key, b'wav-content', 'audio/wav', 'job3')
    root = cache._root()
    blob, meta = cache._paths(root, 1, key)
    details = json.loads(meta.read_text())
    details['expires_at'] = int(time.time()) - 1
    meta.write_text(json.dumps(details))
    assert cache.purge_expired(dry_run=True)['removed'] == 0
    assert cache.purge_expired(dry_run=False)['removed'] == 1
    assert not blob.exists() and not meta.exists()
