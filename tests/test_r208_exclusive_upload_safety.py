import io
import pytest
from app import main


def test_existing_destination_cannot_be_deleted(tmp_path):
    dest = tmp_path / 'original.wav'
    dest.write_bytes(b'private-existing-data')
    with pytest.raises(FileExistsError):
        main._copy_limited(io.BytesIO(b'incoming'), dest)
    assert dest.read_bytes() == b'private-existing-data'


def test_interrupted_new_upload_removed(tmp_path):
    class BrokenStream:
        def __init__(self): self.calls = 0
        def read(self, size):
            self.calls += 1
            if self.calls == 1: return b'partial'
            raise OSError('lost connection')
    dest = tmp_path / 'upload.wav'
    with pytest.raises(OSError, match='lost connection'):
        main._copy_limited(BrokenStream(), dest)
    assert not dest.exists()


def test_complete_upload_is_persisted(tmp_path):
    dest = tmp_path / 'upload.wav'
    main._copy_limited(io.BytesIO(b'audio-content'), dest)
    assert dest.read_bytes() == b'audio-content'


def test_sample_conversion_does_not_clobber_existing(tmp_path, monkeypatch):
    source = tmp_path / 'track.wav'; source.write_bytes(b'source')
    converted = tmp_path / 'track-sr48000.wav'; converted.write_bytes(b'preexisting')
    monkeypatch.setattr(main, 'audio_path', lambda pid, filename: tmp_path / filename)
    monkeypatch.setattr(main, '_audio_sample_rate', lambda path: 44100)
    class FakeProc:
        returncode = 0
        stderr = ''
    def fake_run(cmd, **kwargs):
        from pathlib import Path
        Path(cmd[-1]).write_bytes(b'new conversion')
        return FakeProc()
    monkeypatch.setattr(main.subprocess, 'run', fake_run)
    with pytest.raises(FileExistsError):
        main._normalize_audio_to_project_rate('p', 'track.wav', 48000)
    assert source.read_bytes() == b'source'
    assert converted.read_bytes() == b'preexisting'
    assert not list(tmp_path.glob('.*.tmp.wav'))
