"""Durable shared-store fail-closed regression coverage for r208."""
import json
import os
import multiprocessing

import pytest
from app import storage


def setup(monkeypatch, tmp_path):
    root = tmp_path / 'projects'
    root.mkdir()
    shared = tmp_path / 'shared'
    monkeypatch.setattr(storage, 'ROOT', root)
    monkeypatch.setattr(storage, 'SHARED_MEDIA_ROOT', shared)
    monkeypatch.setattr(storage, 'SHARED_AUDIO_ROOT', shared / 'audio')
    monkeypatch.setattr(storage, 'SHARED_INDEX_PATH', shared / 'index.json')
    return root, shared


def test_malformed_shared_index_does_not_reset(monkeypatch, tmp_path):
    _, shared = setup(monkeypatch, tmp_path)
    shared.mkdir()
    index = shared / 'index.json'
    index.write_text('{broken')
    with pytest.raises(ValueError, match='invalid shared index'):
        storage._load_shared_index()
    assert index.read_text() == '{broken'


def test_unsupported_shared_index_schema_is_preserved(monkeypatch, tmp_path):
    _, shared = setup(monkeypatch, tmp_path)
    shared.mkdir()
    index = shared / 'index.json'
    index.write_text('{"version":2,"assets":{}}')
    with pytest.raises(ValueError, match='schema'):
        storage._load_shared_index()
    assert json.loads(index.read_text())['version'] == 2


def test_index_directory_is_rejected(monkeypatch, tmp_path):
    _, shared = setup(monkeypatch, tmp_path)
    (shared / 'index.json').mkdir(parents=True)
    with pytest.raises(ValueError, match='index'):
        storage._load_shared_index()
    with pytest.raises(ValueError, match='index'):
        storage._write_shared_index({'assets': {}})


def test_shared_root_symlink_rejected(monkeypatch, tmp_path):
    _, shared = setup(monkeypatch, tmp_path)
    other = tmp_path / 'other'
    other.mkdir()
    shared.symlink_to(other, target_is_directory=True)
    with pytest.raises(ValueError, match='root'):
        with storage._shared_process_lock():
            pass
    assert list(other.iterdir()) == []


def test_shared_lock_symlink_rejected(monkeypatch, tmp_path):
    _, shared = setup(monkeypatch, tmp_path)
    shared.mkdir()
    outside = tmp_path / 'outside'
    outside.write_text('do not change')
    (shared / '.shared-media.lock').symlink_to(outside)
    with pytest.raises(ValueError, match='lock'):
        with storage._shared_process_lock():
            pass
    assert outside.read_text() == 'do not change'


def test_blob_shard_symlink_rejected(monkeypatch, tmp_path):
    _, shared = setup(monkeypatch, tmp_path)
    other = tmp_path / 'other'
    other.mkdir()
    (shared / 'audio').mkdir(parents=True)
    (shared / 'audio' / 'ab').symlink_to(other, target_is_directory=True)
    with pytest.raises(ValueError, match='directory'):
        storage._validate_blob_parent(shared / 'audio' / 'ab' / ('ab' * 32 + '.wav'))


def test_shared_lock_released_on_exception(monkeypatch, tmp_path):
    _, shared = setup(monkeypatch, tmp_path)
    with pytest.raises(RuntimeError, match='failure'):
        with storage._shared_process_lock():
            raise RuntimeError('failure')
    with storage._shared_process_lock():
        assert (shared / '.shared-media.lock').is_file()


def _try_lock(path, conn):
    import fcntl
    fd = os.open(path, os.O_RDWR)
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            conn.send(False)
        else:
            conn.send(True)
            fcntl.flock(fd, fcntl.LOCK_UN)
    finally:
        os.close(fd)
        conn.close()


@pytest.mark.skipif(os.name != 'posix', reason='POSIX flock test')
def test_shared_lock_excludes_other_process(monkeypatch, tmp_path):
    _, shared = setup(monkeypatch, tmp_path)
    ctx = multiprocessing.get_context('spawn')
    with storage._shared_process_lock():
        parent, child = ctx.Pipe(duplex=False)
        proc = ctx.Process(target=_try_lock, args=(str(shared / '.shared-media.lock'), child))
        proc.start()
        child.close()
        assert parent.poll(10)
        assert parent.recv() is False
        proc.join(10)
        assert proc.exitcode == 0
