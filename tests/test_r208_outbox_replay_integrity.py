import pytest
from app import ai_publish_outbox as outbox
from app import ai_arranger_runtime as runtime

@pytest.fixture
def isolated(tmp_path, monkeypatch):
    monkeypatch.setattr(runtime, '_ROOT', tmp_path / 'jobs')
    return tmp_path

def test_pending_replay_rejects_missing_wav(isolated):
    outbox.stage('replaymissing', 'proj', b'audio', {})
    outbox._stage_path('replaymissing').unlink()
    with pytest.raises(FileNotFoundError):
        outbox.stage('replaymissing', 'proj', b'audio', {})
    assert outbox.status('replaymissing')['state'] == 'pending'

def test_pending_replay_rejects_tampering(isolated):
    outbox.stage('replaytampered', 'proj', b'audio', {})
    outbox._stage_path('replaytampered').write_bytes(b'tampered')
    with pytest.raises(ValueError, match='checksum'):
        outbox.stage('replaytampered', 'proj', b'audio', {})
    assert outbox.status('replaytampered')['state'] == 'pending'

def test_pending_replay_rejects_symlink(isolated):
    outbox.stage('replaysymlink', 'proj', b'audio', {})
    path = outbox._stage_path('replaysymlink')
    target = isolated / 'outside'
    path.rename(target)
    path.symlink_to(target)
    with pytest.raises((OSError, ValueError)):
        outbox.stage('replaysymlink', 'proj', b'audio', {})
    assert target.read_bytes() == b'audio'

def test_published_replay_does_not_require_deleted_stage(isolated):
    outbox.stage('replaypublished', 'proj', b'audio', {})
    assert outbox.recover(lambda *args: None) == 1
    assert not outbox._stage_path('replaypublished').exists()
    assert outbox.stage('replaypublished', 'proj', b'audio', {})['state'] == 'published'
