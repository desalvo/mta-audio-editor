"""When a newly-created upload pathname is replaced, rollback cannot delete it."""
import io
import os
from types import SimpleNamespace
import pytest
from app import main, storage


def test_upload_failed_fsync_preserves_replaced_destination(tmp_path, monkeypatch):
    dst = tmp_path / 'upload.wav'
    real_sync = main.os.fsync
    def replace_then_fail(fd):
        if os.fstat(fd).st_mode and dst.exists():
            dst.unlink()
            dst.write_bytes(b'other job')
        raise OSError('fsync interrupted')
    monkeypatch.setattr(main.os, 'fsync', replace_then_fail)
    with pytest.raises(OSError, match='fsync interrupted'):
        main._copy_limited(io.BytesIO(b'new audio'), dst)
    assert dst.read_bytes() == b'other job'


def test_original_failed_copy_preserves_replaced_destination(tmp_path, monkeypatch):
    src = tmp_path / 'src.wav'; src.write_bytes(b'source')
    folder = tmp_path / 'originals'; folder.mkdir()
    target = folder / 'song.wav'
    monkeypatch.setattr(storage, 'find_duplicate_project_file', lambda *a: None)
    monkeypatch.setattr(storage, '_unique_original_name', lambda *a: 'song.wav')
    monkeypatch.setattr(storage, 'original_path', lambda *a: target)
    def replace_then_fail(source, out, length=0):
        out.write(b'partial')
        target.unlink()
        target.write_bytes(b'other job')
        raise OSError('copy interrupted')
    monkeypatch.setattr(storage.shutil, 'copyfileobj', replace_then_fail)
    with pytest.raises(OSError, match='copy interrupted'):
        storage.preserve_original('p', src, 'song.wav')
    assert target.read_bytes() == b'other job'
