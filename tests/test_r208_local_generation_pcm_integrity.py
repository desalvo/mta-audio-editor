"""Local Arranger/Remix publication must never persist truncated PCM."""
import io
import wave
from unittest.mock import patch
import pytest
from app.main import _append_ai_generated_track
from app.models import Project


def _wav(frames=100):
    buf = io.BytesIO()
    with wave.open(buf, 'wb') as out:
        out.setnchannels(2)
        out.setsampwidth(2)
        out.setframerate(44100)
        out.writeframes(b'\x01\x00\x02\x00' * frames)
    return buf.getvalue()


@pytest.mark.parametrize('mode', ['arranger', 'remix'])
def test_truncated_generated_pcm_fails_before_any_side_effect(tmp_path, mode):
    wav = _wav()[:-48]
    project = Project(id='generated-integrity', title='Safe')
    with patch('app.main.audio_path', side_effect=lambda pid, filename: tmp_path / filename), \
         patch('app.main.save_project') as save:
        with pytest.raises(ValueError, match='truncated'):
            _append_ai_generated_track(project, wav,
                {'frames': 100, 'sample_rate': 44100, 'channels': 2},
                mode=mode, input_source='master', job_id='testjob')
        save.assert_not_called()
    assert not project.tracks
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize('mode', ['arranger', 'remix'])
def test_complete_pcm_is_published_with_original_tracks_intact(tmp_path, mode):
    project = Project(id='generated-integrity', title='Safe')
    audio = _wav()
    with patch('app.main.audio_path', side_effect=lambda pid, filename: tmp_path / filename), \
         patch('app.main._register_track_source_in_library'), \
         patch('app.main.save_project') as save:
        result = _append_ai_generated_track(project, audio,
            {'frames': 100, 'sample_rate': 44100, 'channels': 2},
            mode=mode, input_source='master', job_id='testjob')
    assert result.tracks[0].filename == 'ai-testjob.wav'
    assert (tmp_path / 'ai-testjob.wav').read_bytes() == audio
    save.assert_called_once()
