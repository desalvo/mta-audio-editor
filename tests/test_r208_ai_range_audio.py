import wave
from pathlib import Path
import pytest
from app.ai_worker_protocol import _trim_wav_for_ai


def test_ai_range_trims_actual_samples(tmp_path: Path):
    src = tmp_path / 'source.wav'
    with wave.open(str(src), 'wb') as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(1000)
        wav.writeframes(b'\0\0' * 12000)
    _trim_wav_for_ai(src, 2000, 7000)
    with wave.open(str(src), 'rb') as wav:
        assert wav.getnframes() == 5000
        assert wav.getframerate() == 1000


def test_ai_range_rejects_out_of_bounds_without_replacing(tmp_path: Path):
    src = tmp_path / 'source.wav'
    with wave.open(str(src), 'wb') as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(1000)
        wav.writeframes(b'\0\0' * 3000)
    initial = src.read_bytes()
    with pytest.raises(ValueError, match='exceeds'):
        _trim_wav_for_ai(src, 2000, 5000)
    assert src.read_bytes() == initial
