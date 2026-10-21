"""Commercial-safe chord profiles and retention of complex chord qualities."""
from app import music_text
from app.models import Chord


def test_advanced_chord_labels_survive_postprocessing():
    labels = ["C7b9", "D7#9", "Em7b5", "Fmaj9", "Gsus4/B", "Aadd9", "C9", "BmMaj7"]
    events = [Chord(time_ms=i * 2000, chord=label) for i, label in enumerate(labels)]
    result = music_text._postprocess_chord_events(events, {"preset": "detailed", "min_chord_ms": 0, "max_changes_per_minute": 0, "temporal_smoothing": False})
    assert [e.chord for e in result] == labels


def test_stable_profile_still_simplifies_for_songbook():
    assert music_text._limit_chord_vocabulary("C7b9", {"preset": "stable", "detect_sevenths": True, "detect_slash_bass": True}) == "C7"


def test_profile_cannot_include_disabled_legacy_madmom(monkeypatch):
    monkeypatch.setattr("app.ai_models.chord_engine_available", lambda engine: True)
    for profile in ("stable", "fast", "accurate", "maximum"):
        engines = music_text._profile_engine_candidates(profile)
        assert "madmom-deep-chroma" not in engines
        assert "madmom-cnn-crf" not in engines
        assert "chordformer" not in engines
        assert "mta-chromagram" in engines


def test_extended_templates_cover_12_roots():
    labels = {name for name, _ in music_text._chord_templates()}
    for quality in ("sus2", "sus4", "7sus4", "m7b5", "dim7", "mMaj7", "add9", "9", "maj9", "m9", "7b5", "7#5", "7b9", "7#9"):
        assert "C" + quality in labels
        assert "F#" + quality in labels
