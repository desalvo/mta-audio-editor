import wave
from pathlib import Path

from app.main import _limit_metronome_wav
from app.models import Project


def test_metronome_window_mutes_without_shifting(tmp_path: Path):
    path = tmp_path / 'click.wav'
    with wave.open(str(path), 'wb') as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(1000)
        wav.writeframes(b'\x01\x00' * 1000)
    _limit_metronome_wav(path, 200, 600)
    with wave.open(str(path), 'rb') as wav:
        assert wav.getnframes() == 1000
        samples = wav.readframes(1000)
    assert samples[:400] == b'\x00' * 400
    assert samples[400:1200] == b'\x01\x00' * 400
    assert samples[1200:] == b'\x00' * 800


def test_metronome_default_is_noop(tmp_path: Path):
    path = tmp_path / 'fake.wav'
    path.write_bytes(b'fake fixture')
    _limit_metronome_wav(path, 0, None)
    assert path.read_bytes() == b'fake fixture'


def test_metronome_interval_persists_in_project():
    project = Project(id='window', title='Window', metronome_start_ms=250, metronome_stop_ms=1200)
    loaded = Project.model_validate_json(project.model_dump_json())
    assert (loaded.metronome_start_ms, loaded.metronome_stop_ms) == (250, 1200)
    assert Project(id='default',title='Default').metronome_stop_ms is None
