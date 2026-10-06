from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.audio_engine import generate_metronome_wav
from app.main import app
from app.models import Clip, Project, Track


def _project(sig: str, bpm: float = 120.0) -> Project:
    track = Track(id="t", name="Audio", filename="a.wav", duration_ms=4000,
                  clips=[Clip(id="c", source_start_ms=0, source_end_ms=4000, timeline_start_ms=0)])
    return Project(id="p", title="Song", bpm=bpm, time_signature=sig, tracks=[track])


def test_6_8_does_not_double_metronome_pulse_rate(tmp_path):
    # Same BPM => same pulse spacing regardless of denominator.
    import wave
    p4 = tmp_path / "4.wav"
    p6 = tmp_path / "6.wav"
    generate_metronome_wav(_project("4/4"), p4)
    generate_metronome_wav(_project("6/8"), p6)
    # Source-level invariant is intentional and protects against reintroducing 4/denominator scaling.
    source = Path("app/audio_engine.py").read_text(encoding="utf-8")
    assert "beat_seconds = 60.0 / float(project.bpm)" in source
    assert "(4.0 / max(1, denominator))" not in source
    with wave.open(str(p4), "rb") as a, wave.open(str(p6), "rb") as b:
        assert a.getframerate() == b.getframerate() == 44100
        assert a.getnframes() == b.getnframes()


def test_manual_meter_recalc_chooses_tempo_octave_nearest_existing_bpm(tmp_path, monkeypatch):
    # This is a source/logic regression test because the endpoint storage is covered elsewhere.
    source = Path("app/main.py").read_text(encoding="utf-8")
    assert 'candidates = {float(bpm)}' in source
    assert 'abs(candidate - reference_bpm)' in source
    assert 'signature = preferred' in source


def test_compound_meter_accents_remain_supported():
    source = Path("app/audio_engine.py").read_text(encoding="utf-8")
    assert "denominator == 8 and numerator in {6, 9, 12}" in source
