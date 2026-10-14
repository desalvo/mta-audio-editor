"""Five independent failure phases must leave no new project upload files."""
import io
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
import pytest
from fastapi import HTTPException
from app import main, storage

@pytest.fixture
def upload_env(monkeypatch,tmp_path):
    audio=tmp_path/'audio'; audio.mkdir(); originals=tmp_path/'originals'; originals.mkdir()
    old=originals/'previous.wav'; old.write_bytes(b'old')
    monkeypatch.setattr(storage, 'pdir', lambda pid: tmp_path)
    monkeypatch.setattr(main,'audio_path',lambda pid,name: audio/name)
    monkeypatch.setattr(main,'originals_dir',lambda pid: originals)
    monkeypatch.setattr(main,'find_duplicate_project_file',lambda *a: None)
    monkeypatch.setattr(main,'preserve_original',lambda pid,dst,name: ((originals/'new.wav').write_bytes(dst.read_bytes()), originals/'new.wav')[1])
    monkeypatch.setattr(main,'load_project',lambda pid: SimpleNamespace(sample_rate=44100))
    monkeypatch.setattr(main,'_normalize_audio_to_project_rate',lambda pid,name,rate: (name,audio/name,44100))
    monkeypatch.setattr(main,'media_duration_ms',lambda path: 123)
    monkeypatch.setattr(main,'ffprobe',lambda path: {'streams':[]})
    return audio,originals

def assert_clean(env):
    audio,originals=env
    assert list(audio.iterdir())==[]
    assert {p.name for p in originals.iterdir()}=={'previous.wav'}
    assert (originals/'previous.wav').read_bytes()==b'old'

def test_stream_read_failure(monkeypatch,upload_env):
    class Broken(io.BytesIO):
        def read(self,*args): raise OSError('stream lost')
    with pytest.raises(OSError,match='stream lost'):
        main._save_upload('p',SimpleNamespace(filename='x.wav',file=Broken()))
    assert_clean(upload_env)

def test_probe_failure(monkeypatch,upload_env):
    monkeypatch.setattr(main,'ffprobe',Mock(side_effect=ValueError('bad audio')))
    with pytest.raises(HTTPException) as error:
        main._save_upload('p',SimpleNamespace(filename='x.wav',file=io.BytesIO(b'audio')))
    assert error.value.status_code==400
    assert_clean(upload_env)

def test_duplicate_failure(monkeypatch,upload_env):
    monkeypatch.setattr(main,'find_duplicate_project_file',lambda *a:{'category':'audio','name':'dup.wav'})
    with pytest.raises(HTTPException) as error:
        main._save_upload('p',SimpleNamespace(filename='x.wav',file=io.BytesIO(b'audio')))
    assert error.value.status_code==409
    assert_clean(upload_env)

def test_preserve_failure(monkeypatch,upload_env):
    def broken(pid,dst,name):
        (upload_env[1]/'new.wav').write_bytes(b'partial')
        (upload_env[1]/'new.wav').unlink()  # preserve_original owns rollback of its incomplete copy
        raise OSError('original copy failed')
    monkeypatch.setattr(main,'preserve_original',broken)
    with pytest.raises(OSError,match='original copy failed'):
        main._save_upload('p',SimpleNamespace(filename='x.wav',file=io.BytesIO(b'audio')))
    assert_clean(upload_env)

def test_metadata_failure_after_conversion(monkeypatch,upload_env):
    def converted(pid,name,rate):
        dest=upload_env[0]/(Path(name).stem+'-sr44100.wav')
        dest.write_bytes(b'converted')
        return dest.name,dest,44100
    monkeypatch.setattr(main,'_normalize_audio_to_project_rate',converted)
    monkeypatch.setattr(main,'media_duration_ms',Mock(side_effect=RuntimeError('metadata failed')))
    with pytest.raises(RuntimeError,match='metadata failed'):
        main._save_upload('p',SimpleNamespace(filename='x.wav',file=io.BytesIO(b'audio')))
    assert_clean(upload_env)
