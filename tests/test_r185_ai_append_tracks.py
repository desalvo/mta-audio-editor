"""AI results must append and must never overwrite a source track."""
import io
import wave
from pathlib import Path
from unittest.mock import patch
from app.models import Project, Track
from app.main import _append_ai_generated_track


def test_append_ai_audio_keeps_original_tracks(tmp_path):
    project = Project(id='aiappendtest', title='Test', tracks=[Track(id='original', name='Original', filename='old.wav')])
    payload = io.BytesIO()
    with wave.open(payload, 'wb') as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(44100)
        w.writeframes(b'\x00\x00' * 441)
    data = payload.getvalue()
    def path(pid, name):
        return tmp_path / name
    with patch('app.main.audio_path', side_effect=path), patch('app.main.save_project') as save, patch('app.main._register_track_source_in_library'):
        result = _append_ai_generated_track(project, data, dict(frames=441, sample_rate=44100, channels=1), mode='remix', input_source='track')
        assert len(result.tracks) == 2
        assert result.tracks[0].filename == 'old.wav'
        assert result.tracks[1].filename != 'old.wav'
        assert result.tracks[1].clips[0].timeline_start_ms == 0
        assert (tmp_path / result.tracks[1].filename).read_bytes() == data
        save.assert_called_once()


def test_append_rejects_mismatch_without_mutation(tmp_path):
    project = Project(id='aiappendtest', title='Test')
    data = io.BytesIO()
    with wave.open(data, 'wb') as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(44100)
        w.writeframes(b'\x00\x00' * 10)
    from pytest import raises
    with raises(ValueError, match='metadata mismatch'):
        _append_ai_generated_track(project, data.getvalue(), dict(frames=100, sample_rate=44100, channels=1), mode='arranger', input_source='master')
    assert not project.tracks
