"""Ensure external worker outputs have actual PCM, not only plausible RIFF headers."""
import io
import wave

import pytest
from app.ai_worker_artifacts import _verify_wav_bytes, package_artifacts
from app.ai_worker_protocol import verify_preview_wav


def wav_audio(frames=120):
    stream = io.BytesIO()
    with wave.open(stream, 'wb') as output:
        output.setnchannels(2)
        output.setsampwidth(2)
        output.setframerate(44100)
        output.writeframes(b'\x00\x01\x02\x03' * frames)
    return stream.getvalue()


@pytest.mark.parametrize('removed', [1, 8, 40])
def test_legacy_preview_rejects_truncated_samples(tmp_path, removed):
    truncated = wav_audio()[:-removed]
    with pytest.raises(ValueError, match='truncated'):
        _verify_wav_bytes(truncated)
    path = tmp_path / 'preview.wav'
    path.write_bytes(truncated)
    with pytest.raises(ValueError, match='truncated'):
        verify_preview_wav(path)
    with pytest.raises(ValueError, match='truncated'):
        package_artifacts(tmp_path)


def test_legacy_worker_accepts_complete_pcm(tmp_path):
    complete = wav_audio()
    path = tmp_path / 'preview.wav'
    path.write_bytes(complete)
    _verify_wav_bytes(complete)
    assert verify_preview_wav(path)['frames'] == 120
    assert package_artifacts(tmp_path) == (complete, 'audio/wav')
