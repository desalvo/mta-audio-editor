from pathlib import Path

from app.models import AdaptiveTempoPoint, Project

ROOT = Path(__file__).resolve().parents[1]
JS = (ROOT / "app/static/app.js").read_text(encoding="utf-8")
MAIN = (ROOT / "app/main.py").read_text(encoding="utf-8")
INDEX = (ROOT / "app/templates/index.html").read_text(encoding="utf-8")


def test_project_persists_metronome_source_shift_and_transport_mode():
    project = Project(id="p", title="x")
    project.metronome_reference_track_id = "drums"
    project.metronome_reference_track_name = "Drums"
    project.metronome_grid_origin_ms = 125
    project.metronome_shift_ms = -40
    project.transport_time_mode = "musical"
    project.adaptive_tempo_map = [AdaptiveTempoPoint(time_ms=100, bpm=120, beat_index=0)]
    payload = project.model_dump()
    assert payload["metronome_reference_track_id"] == "drums"
    assert payload["metronome_grid_origin_ms"] == 125
    assert payload["metronome_shift_ms"] == -40
    assert payload["transport_time_mode"] == "musical"


def test_track_context_menu_has_fixed_and_adaptive_reference_actions():
    assert "Metronomo da questa traccia" in JS
    assert "Metronomo adattivo da questa traccia" in JS
    assert "createMetronomeTrack('fixed','${id}')" in JS
    assert "createMetronomeTrack('adaptive','${id}')" in JS


def test_adaptive_shift_reuses_saved_tempo_map_without_analysis():
    start = MAIN.index('@app.post("/api/projects/{pid}/metronome-shift")')
    end = MAIN.index('@app.post("/api/projects/{pid}/transport-time-mode")', start)
    body = MAIN[start:end]
    assert "project.adaptive_tempo_map" in body
    assert "generate_adaptive_metronome_wav" in body
    assert "estimate_adaptive_tempo_map" not in body
    assert 'unit in {"beat", "beats"}' in body


def test_transport_supports_time_and_musical_views():
    assert 'id="transportDisplayMode"' in INDEX
    assert '<option value="musical">Misure:Beat</option>' in INDEX
    assert "function transportMusicalPosition" in JS
    assert "function parseMusicalPosition" in JS
    assert "current?.metronome_mode==='adaptive'" in JS
    assert "shiftedAdaptiveBeatTimes" in JS


def test_mixer_remains_vertical_channel_strip():
    css = (ROOT / "app/static/app.css").read_text(encoding="utf-8")
    assert ".v-fader" in css
    assert "transform:rotate(-90deg)" in css
    assert ".channels{display:flex" in css


def test_mixer_default_height_shows_complete_controls():
    root = Path(__file__).resolve().parents[1]
    js = (root / "app/static/app.js").read_text(encoding="utf-8")
    css = (root / "app/static/app.css").read_text(encoding="utf-8")
    project = Project(id="mixer-fit", title="Mixer fit")
    assert project.mixer_height_px == 320
    assert "var(--mixer-height,320px)" in css
    assert "current.mixer_height_px||320" in js
    assert ".mixer-dock .channels{flex:1 0 230px" in css
    assert "overflow-y:auto!important" in css
