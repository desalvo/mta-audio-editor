"""The legacy worker must publish exactly the bytes it validates."""
import os
import pytest
from app.ai_worker_protocol import _snapshot_preview_wav, verify_preview_wav
from tests.test_r208_worker_pcm_complete import wav_audio


def test_snapshot_returns_verified_bytes(tmp_path):
    payload = wav_audio()
    path = tmp_path / 'preview.wav'
    path.write_bytes(payload)
    data, meta = _snapshot_preview_wav(path)
    assert data == payload
    assert meta['frames'] == 120
    assert meta['bytes'] == len(payload)


def test_snapshot_refuses_symbolic_link(tmp_path):
    actual = tmp_path / 'audio.wav'
    actual.write_bytes(wav_audio())
    (tmp_path / 'preview.wav').symlink_to(actual)
    with pytest.raises(ValueError):
        _snapshot_preview_wav(tmp_path / 'preview.wav')


def test_snapshot_refuses_hardlinked_file(tmp_path):
    actual = tmp_path / 'audio.wav'
    actual.write_bytes(wav_audio())
    os.link(actual, tmp_path / 'preview.wav')
    with pytest.raises(ValueError):
        verify_preview_wav(tmp_path / 'preview.wav')


def test_snapshot_refuses_truncated_pcm(tmp_path):
    path = tmp_path / 'preview.wav'
    path.write_bytes(wav_audio()[:-8])
    with pytest.raises(ValueError, match='truncated'):
        _snapshot_preview_wav(path)
