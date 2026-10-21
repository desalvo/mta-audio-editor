"""Regression tests for upload validation and failure cleanup."""
import asyncio

from types import SimpleNamespace
from unittest.mock import Mock
import pytest
from fastapi import HTTPException
from app import main
from app import ai_upload_transaction as upload_tx


def test_add_track_invalid_sync_rejected_before_write(monkeypatch):
    monkeypatch.setattr(main, '_project_for_actor', Mock(side_effect=AssertionError('should not read project')))
    with pytest.raises(HTTPException) as exc:
        asyncio.run(main._add_track_under_project_lock('p', object(), SimpleNamespace(filename='x.wav'), sync_mode='invalid'))
    assert exc.value.status_code == 400


def test_add_track_save_failure_removes_uploaded_audio(monkeypatch, tmp_path):
    dest = tmp_path / 'upload.wav'; dest.write_bytes(b'new audio')
    project = SimpleNamespace(target='DAW', sample_rate=44100, tracks=[], archived_tracks=[], clip_library=[])
    monkeypatch.setattr(main, '_project_for_actor', lambda *a, **k: project)
    monkeypatch.setattr(main, '_save_upload', lambda *a, **k: ('upload.wav', dest, 1000))
    monkeypatch.setattr(main, '_register_track_source_in_library', lambda *a, **k: None)
    monkeypatch.setattr(main, 'load_project', lambda pid: SimpleNamespace(target='DAW', tracks=[], archived_tracks=[], clip_library=[]))
    monkeypatch.setattr(main, 'save_project', Mock(side_effect=OSError('disk full')))
    with pytest.raises(OSError, match='disk full'):
        asyncio.run(main._add_track_under_project_lock('p', object(), SimpleNamespace(filename='x.wav')))
    assert not dest.exists()


def test_replace_track_invalid_sync_preserves_old_file(monkeypatch, tmp_path):
    old = tmp_path / 'original.wav'; old.write_bytes(b'original')
    monkeypatch.setattr(main, '_project_for_actor', Mock(side_effect=AssertionError('should not read project')))
    with pytest.raises(HTTPException) as exc:
        asyncio.run(main.replace_track.__wrapped__('p', 't', object(), SimpleNamespace(filename='x.wav'), sync_mode='bad'))
    assert exc.value.status_code == 400
    assert old.read_bytes() == b'original'


def test_replace_track_save_failure_removes_new_file_but_keeps_old(monkeypatch, tmp_path):
    old = tmp_path / 'original.wav'; old.write_bytes(b'original')
    new = tmp_path / 'new.wav'; new.write_bytes(b'new')
    track = SimpleNamespace(id='t', filename='original.wav', duration_ms=1000, clips=[], channels=2, channel_layout='stereo', sample_rate=44100, waveform_peaks=[], waveform_revision='')
    project = SimpleNamespace(target='DAW', sample_rate=44100, tracks=[track], archived_tracks=[], clip_library=[])
    monkeypatch.setattr(main, '_project_for_actor', lambda *a, **k: project)
    monkeypatch.setattr(main, '_save_upload', lambda *a, **k: ('new.wav', new, 2000))
    monkeypatch.setattr(main, 'audio_path', lambda pid, name: tmp_path / name)
    monkeypatch.setattr(main, '_audio_channel_info', lambda path: (2, 'stereo'))
    monkeypatch.setattr(main, '_register_track_source_in_library', lambda *a, **k: None)
    monkeypatch.setattr(main, 'load_project', lambda pid: SimpleNamespace(target='DAW', tracks=[], archived_tracks=[], clip_library=[]))
    monkeypatch.setattr(main, 'save_project', Mock(side_effect=OSError('disk full')))
    with pytest.raises(OSError, match='disk full'):
        asyncio.run(main.replace_track.__wrapped__('p','t',object(),SimpleNamespace(filename='new.wav')))
    assert not new.exists()
    assert old.read_bytes() == b'original'


@pytest.fixture(autouse=True)
def _mock_transaction_for_legacy_rollback_tests(monkeypatch):
    monkeypatch.setattr(upload_tx, "begin", lambda pid: None)
    monkeypatch.setattr(upload_tx, "finish", lambda pid: None)
