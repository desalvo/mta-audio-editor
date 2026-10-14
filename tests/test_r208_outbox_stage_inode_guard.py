import pytest
from app import ai_publish_outbox as outbox
from app import ai_arranger_runtime as runtime

@pytest.fixture
def isolated(tmp_path, monkeypatch):
    monkeypatch.setattr(runtime, '_ROOT', tmp_path / 'jobs')
    return tmp_path

def test_symlink_staging_rejected(isolated):
    outbox.stage('guard1', 'project', b'audio', {})
    path = outbox._stage_path('guard1')
    target = isolated / 'original'
    path.rename(target)
    path.symlink_to(target)
    with pytest.raises((OSError, ValueError)):
        outbox.recover(lambda *args: None)
    assert outbox.status('guard1')['state'] == 'pending'

def test_replacement_during_callback_fails_closed(isolated):
    outbox.stage('guard2', 'project', b'audio', {})
    path = outbox._stage_path('guard2')
    def replace(*_):
        path.rename(isolated / 'previous-stage')
        path.write_bytes(b'audio')
    with pytest.raises(ValueError, match='replaced'):
        outbox.recover(replace)
    assert outbox.status('guard2')['state'] == 'pending'

def test_symlink_lock_rejected(isolated):
    outbox.stage('guard3', 'project', b'audio', {})
    target = isolated / 'lock-target'
    target.write_bytes(b'untouched')
    (outbox._root() / 'guard3.lock').symlink_to(target)
    with pytest.raises(ValueError, match='lock'):
        outbox.recover(lambda *args: None)
    assert target.read_bytes() == b'untouched'
    assert outbox.status('guard3')['state'] == 'pending'
