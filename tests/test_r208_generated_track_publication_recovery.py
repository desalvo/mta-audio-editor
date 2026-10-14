"""Failure-boundary regressions for local AI generated track publication."""
import io
import wave
from unittest.mock import patch
import pytest
from app.models import Project
from app.main import _append_ai_generated_track


def _wav():
    out = io.BytesIO()
    with wave.open(out, 'wb') as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(44100)
        w.writeframes(b'\0\0' * 100)
    return out.getvalue()


def _append(project, data):
    return _append_ai_generated_track(project, data, {'frames': 100, 'sample_rate': 44100, 'channels': 1}, mode='remix', input_source='master', job_id='localtest')


def test_failed_save_restores_memory_and_removes_owned_output(tmp_path):
    project = Project(id='localtest', title='Demo')
    with patch('app.main.audio_path', side_effect=lambda pid, name: tmp_path / name), \
         patch('app.main.save_project', side_effect=OSError('disk full')), \
         patch('app.main.load_project', side_effect=FileNotFoundError), \
         patch('app.main._register_track_source_in_library'):
        with pytest.raises(OSError, match='disk full'):
            _append(project, _wav())
    assert project.tracks == []
    assert list(tmp_path.iterdir()) == []


def test_postcommit_error_keeps_generated_media(tmp_path):
    project = Project(id='localtest', title='Demo')
    with patch('app.main.audio_path', side_effect=lambda pid, name: tmp_path / name), \
         patch('app.main.save_project', side_effect=OSError('after commit')), \
         patch('app.main.load_project', side_effect=lambda pid: project), \
         patch('app.main._register_track_source_in_library'):
        with pytest.raises(OSError, match='after commit'):
            _append(project, _wav())
    assert (tmp_path / 'ai-localtest.wav').is_file()
    assert not list(tmp_path.glob('*.pending'))


def test_symlink_target_never_overwritten(tmp_path):
    external = tmp_path / 'external'; external.write_bytes(b'untouched')
    (tmp_path / 'ai-localtest.wav').symlink_to(external)
    project = Project(id='localtest', title='Demo')
    with patch('app.main.audio_path', side_effect=lambda pid, name: tmp_path / name):
        with pytest.raises(RuntimeError, match='Unsafe existing'):
            _append(project, _wav())
    assert external.read_bytes() == b'untouched'
