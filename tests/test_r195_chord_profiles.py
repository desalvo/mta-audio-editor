from pathlib import Path

from app import ai_models, music_text
from app.models import Chord


def test_chord_catalog_exposes_profiles_and_new_models(monkeypatch):
    monkeypatch.setattr(ai_models, "chord_engine_available", lambda engine: True)
    catalog = ai_models.chords_catalog(native=False)
    ids = [item["id"] for item in catalog["engines"]]
    assert ids[:4] == ["profile-stable", "profile-fast", "profile-accurate", "profile-maximum"]
    assert {m["id"] for m in catalog["models"]} >= {"btc-hcqt", "chordformer"}
    assert catalog["default_engine"] == "profile-stable"
    assert {p["id"] for p in catalog["presets"]} == {"stable", "balanced", "detailed", "raw"}


def test_accurate_profile_prefers_chordformer(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(music_text, "_profile_engine_candidates", lambda profile: ["chordformer", "btc-hcqt", "mta-chromagram"])
    calls = []
    def fake_extract(path, *, engine=None, **kwargs):
        calls.append(engine)
        return [Chord(time_ms=0, chord="Cmaj7")]
    monkeypatch.setattr(music_text, "extract_chords", fake_extract)
    events, used = music_text._extract_profile_base(tmp_path / "x.wav", "accurate")
    assert used == "chordformer"
    assert calls == ["chordformer"]
    assert events[0].chord == "Cmaj7"


def test_maximum_profile_uses_weighted_ensemble(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(music_text, "_profile_engine_candidates", lambda profile: ["chordformer", "btc-hcqt", "chordino"])
    results = {
        "chordformer": [Chord(time_ms=0, chord="Cmaj7"), Chord(time_ms=1000, chord="F")],
        "btc-hcqt": [Chord(time_ms=0, chord="Cmaj7"), Chord(time_ms=1000, chord="F")],
        "chordino": [Chord(time_ms=0, chord="C"), Chord(time_ms=1000, chord="F")],
    }
    monkeypatch.setattr(music_text, "extract_chords", lambda path, *, engine=None, **kwargs: results[engine])
    events, used = music_text._extract_profile_base(tmp_path / "x.wav", "maximum")
    assert used.startswith("ensemble:")
    assert [e.chord for e in events] == ["Cmaj7", "F"]


def test_fast_profile_falls_back_to_internal(monkeypatch):
    monkeypatch.setattr(ai_models, "chord_engine_available", lambda engine: engine == "mta-chromagram")
    assert music_text._profile_engine_candidates("fast") == ["mta-chromagram"]
