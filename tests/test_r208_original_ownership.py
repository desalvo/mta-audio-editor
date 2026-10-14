"""Original cleanup is scoped to files owned by the failing upload."""
import io
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
import pytest
from app import main, storage


def test_unrelated_original_created_mid_upload_is_preserved(tmp_path, monkeypatch):
    audio = tmp_path / 'audio'; audio.mkdir()
    originals = tmp_path / 'originals'; originals.mkdir()
    monkeypatch.setattr(storage, 'pdir', lambda pid: tmp_path)
    monkeypatch.setattr(main, 'audio_path', lambda pid, name: audio / name)
    monkeypatch.setattr(main, 'originals_dir', lambda pid: originals)
    monkeypatch.setattr(main, 'ffprobe', lambda path: {'streams': []})
    monkeypatch.setattr(main, 'find_duplicate_project_file', lambda *args: None)
    monkeypatch.setattr(main, 'load_project', lambda pid: SimpleNamespace(sample_rate=44100))
    monkeypatch.setattr(main, '_normalize_audio_to_project_rate', lambda pid, name, rate: (name, audio / name, rate))
    def preserve(pid, source, name):
        owned = originals / 'owned.wav'; owned.write_bytes(b'owned')
        (originals / 'other-job.wav').write_bytes(b'other')
        return owned
    monkeypatch.setattr(main, 'preserve_original', preserve)
    monkeypatch.setattr(main, 'media_duration_ms', Mock(side_effect=RuntimeError('metadata unavailable')))
    with pytest.raises(RuntimeError, match='metadata unavailable'):
        main._save_upload('p', SimpleNamespace(filename='incoming.wav', file=io.BytesIO(b'audio')))
    assert (originals / 'other-job.wav').read_bytes() == b'other'
    assert not (originals / 'owned.wav').exists()
    assert not list(audio.iterdir())


def test_exclusive_original_copy_preserves_collision(tmp_path, monkeypatch):
    original_folder = tmp_path / 'originals'; original_folder.mkdir()
    source = tmp_path / 'source.wav'; source.write_bytes(b'new bytes')
    destination = original_folder / 'song.wav'; destination.write_bytes(b'untouchable')
    monkeypatch.setattr(storage, 'originals_dir', lambda pid: original_folder)
    monkeypatch.setattr(storage, 'original_path', lambda pid, name: original_folder / name)
    monkeypatch.setattr(storage, 'find_duplicate_project_file', lambda *args: None)
    monkeypatch.setattr(storage, '_unique_original_name', lambda pid, name: 'song.wav')
    with pytest.raises(FileExistsError):
        storage.preserve_original('p', source, 'song.wav')
    assert destination.read_bytes() == b'untouchable'


def test_failed_original_copy_removes_only_its_partial_file(tmp_path, monkeypatch):
    originals = tmp_path / 'originals'; originals.mkdir()
    source = tmp_path / 'source.wav'; source.write_bytes(b'audio')
    unrelated = originals / 'other.wav'; unrelated.write_bytes(b'keep')
    monkeypatch.setattr(storage, 'originals_dir', lambda pid: originals)
    monkeypatch.setattr(storage, 'original_path', lambda pid, name: originals / name)
    monkeypatch.setattr(storage, 'find_duplicate_project_file', lambda *args: None)
    monkeypatch.setattr(storage, '_unique_original_name', lambda pid, name: 'new.wav')
    original_copy = storage.shutil.copyfileobj
    def broken(src, dst, length=0):
        dst.write(b'partial')
        raise OSError('disk error')
    monkeypatch.setattr(storage.shutil, 'copyfileobj', broken)
    with pytest.raises(OSError, match='disk error'):
        storage.preserve_original('p', source, 'new.wav')
    assert not (originals / 'new.wav').exists()
    assert unrelated.read_bytes() == b'keep'
