"""A failed exclusive conversion must never remove somebody else's audio."""
import io
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
import pytest
from app import main, storage


def test_conversion_collision_survives_upload_rollback(tmp_path, monkeypatch):
    audio = tmp_path / 'audio'; audio.mkdir()
    originals = tmp_path / 'originals'; originals.mkdir()
    monkeypatch.setattr(storage, 'pdir', lambda pid: tmp_path)
    monkeypatch.setattr(main, 'audio_path', lambda pid, name: audio / name)
    monkeypatch.setattr(main, 'originals_dir', lambda pid: originals)
    monkeypatch.setattr(main, 'find_duplicate_project_file', lambda *args: None)
    monkeypatch.setattr(main, 'ffprobe', lambda path: {'streams': [{'codec_type':'audio','sample_rate':'44100'}]})
    monkeypatch.setattr(main, 'preserve_original', lambda *args: None)
    monkeypatch.setattr(main, 'load_project', lambda *args: SimpleNamespace(sample_rate=48000))
    monkeypatch.setattr(main.uuid, 'uuid4', lambda: SimpleNamespace(hex='abcde12345ffffffffff'))
    existing = audio / 'abcde12345-sr48000.wav'; existing.write_bytes(b'important-existing-audio')
    def convert(args, **kwargs):
        Path(args[-1]).write_bytes(b'converted')
        return SimpleNamespace(returncode=0, stderr='')
    monkeypatch.setattr(main.subprocess, 'run', convert)
    with pytest.raises(FileExistsError):
        main._save_upload('proj', SimpleNamespace(filename='new.wav', file=io.BytesIO(b'incoming')))
    assert existing.read_bytes() == b'important-existing-audio'
    assert not (audio / 'abcde12345.wav').exists()
    assert not list(audio.glob('.*.tmp.wav'))


def test_conversion_exception_keeps_preexisting_destination(tmp_path, monkeypatch):
    source = tmp_path / 'new.wav'; source.write_bytes(b'new')
    existing = tmp_path / 'new-sr48000.wav'; existing.write_bytes(b'important')
    monkeypatch.setattr(main, 'audio_path', lambda pid, name: tmp_path / name)
    monkeypatch.setattr(main, '_audio_sample_rate', lambda path: 44100)
    def failed_process(cmd, **kwargs):
        Path(cmd[-1]).write_bytes(b'partial')
        raise OSError('encoder died')
    monkeypatch.setattr(main.subprocess, 'run', failed_process)
    with pytest.raises(OSError, match='encoder died'):
        main._normalize_audio_to_project_rate('p', 'new.wav', 48000)
    assert existing.read_bytes() == b'important'
    assert source.read_bytes() == b'new'
    assert not list(tmp_path.glob('.*.tmp.wav'))
