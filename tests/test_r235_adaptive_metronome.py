from pathlib import Path
import wave

import numpy as np

from app import main as main_module
from app.audio_engine import estimate_adaptive_tempo_map, generate_adaptive_metronome_wav
from app.models import AdaptiveTempoPoint, Clip, Project, Track

ROOT = Path(__file__).resolve().parents[1]
JS = (ROOT / "app/static/app.js").read_text(encoding="utf-8")
MODELS = (ROOT / "app/models.py").read_text(encoding="utf-8")
MAIN = (ROOT / "app/main.py").read_text(encoding="utf-8")


def _project() -> Project:
    return Project(
        id="p1",
        title="Adaptive",
        bpm=120,
        sample_rate=44100,
        tracks=[
            Track(
                id="music",
                name="Music",
                type="other",
                filename="music.wav",
                duration_ms=8000,
                channels=1,
                sample_rate=44100,
                clips=[Clip(id="c1", source_start_ms=0, source_end_ms=8000, timeline_start_ms=0)],
            )
        ],
    )


def test_project_persists_adaptive_tempo_map_and_frontend_exposes_mode():
    project = _project()
    project.metronome_mode = "adaptive"
    project.adaptive_tempo_map = [AdaptiveTempoPoint(time_ms=0, bpm=120, beat_index=0)]
    restored = Project.model_validate_json(project.model_dump_json())
    assert restored.metronome_mode == "adaptive"
    assert restored.adaptive_tempo_map[0].bpm == 120
    assert "createMetronomeTrack('adaptive')" in JS
    assert "tutti i beat e tutte le variazioni vengono ricalcolati" in JS
    assert "project.adaptive_tempo_map = tempo_points" in MAIN


def test_adaptive_endpoint_recalculates_map_every_request(monkeypatch, tmp_path):
    project = _project()
    calls = {"analysis": 0, "render": 0}
    monkeypatch.setattr(main_module, "_project_for_actor", lambda request, pid: project)
    monkeypatch.setattr(main_module, "audio_path", lambda pid, name: tmp_path / name)
    monkeypatch.setattr(main_module, "save_project", lambda p: None)
    monkeypatch.setattr(main_module, "waveform_peaks", lambda p: [0.0, 0.1])

    def fake_render_mix(p, resolver, out, **kwargs):
        calls["render"] += 1
        Path(out).write_bytes(b"analysis")
        return out

    def fake_estimate(path):
        calls["analysis"] += 1
        base = calls["analysis"]
        return [0, 500, 980, 1440], [
            AdaptiveTempoPoint(time_ms=0, bpm=120 + base, beat_index=0),
            AdaptiveTempoPoint(time_ms=500, bpm=125 + base, beat_index=1),
        ]

    def fake_generate(p, out, beats):
        Path(out).write_bytes(b"wav")
        return 8000

    monkeypatch.setattr(main_module, "render_mix", fake_render_mix)
    monkeypatch.setattr(main_module, "estimate_adaptive_tempo_map", fake_estimate)
    monkeypatch.setattr(main_module, "generate_adaptive_metronome_wav", fake_generate)
    monkeypatch.setattr(main_module, "_track_waveform_revision", lambda track, out: "rev")

    first = main_module._create_metronome_track_locked("p1", object(), mode="adaptive")
    second = main_module._create_metronome_track_locked("p1", object(), mode="adaptive")

    assert calls == {"analysis": 2, "render": 2}
    assert first["mode"] == second["mode"] == "adaptive"
    assert second["tempo_map"][0].bpm == 122
    assert project.adaptive_tempo_map[0].bpm == 122
    assert len([t for t in project.tracks if t.type == "click"]) == 1
    assert project.tracks[-1].name == "Metronomo adattivo"


def test_generate_adaptive_metronome_places_clicks_at_variable_intervals(tmp_path):
    project = _project()
    out = tmp_path / "adaptive.wav"
    beats = [0, 500, 1000, 1500, 1900, 2300, 2700, 3100]
    assert generate_adaptive_metronome_wav(project, out, beats) == 8000
    with wave.open(str(out), "rb") as handle:
        assert handle.getframerate() == 44100
        samples = np.frombuffer(handle.readframes(handle.getnframes()), dtype=np.int16)
    for ms in beats:
        index = int(ms * 44.1)
        window = samples[index:index + 1000]
        assert window.size and int(np.max(np.abs(window))) > 1000


def test_adaptive_estimator_detects_non_constant_tempo(tmp_path):
    sr = 4000
    duration = 14.0
    data = np.zeros(int(sr * duration), dtype=np.int16)
    times = []
    t = 0.5
    while t < 6.0:
        times.append(t)
        t += 0.5  # 120 BPM
    while t < 13.0:
        times.append(t)
        t += 0.4  # 150 BPM
    for t in times:
        i = int(t * sr)
        n = min(100, len(data) - i)
        if n > 0:
            pulse = np.sin(2 * np.pi * 600 * np.arange(n) / sr) * np.linspace(1, 0, n)
            data[i:i+n] = np.asarray(pulse * 28000, dtype=np.int16)
    src = tmp_path / "tempo-change.wav"
    with wave.open(str(src), "wb") as h:
        h.setnchannels(1); h.setsampwidth(2); h.setframerate(sr); h.writeframes(data.tobytes())
    beats, points = estimate_adaptive_tempo_map(src)
    assert len(beats) >= 12
    values = [p.bpm for p in points]
    assert max(values) - min(values) >= 12
