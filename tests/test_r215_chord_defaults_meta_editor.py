from pathlib import Path

from app import ai_models
from app.music_text import _normalize_chord_options

ROOT = Path(__file__).resolve().parents[1]
JS = (ROOT / "app/static/app.js").read_text(encoding="utf-8")
CSS = (ROOT / "app/static/app.css").read_text(encoding="utf-8")


def test_chord_extraction_default_is_madmom_complete_45_without_quantization():
    assert ai_models.CHORD_DEFAULT_ENGINE == "madmom-deep-chroma"
    preset = next(x for x in ai_models.CHORD_PIPELINE_PRESETS if x["id"] == "balanced")
    assert preset["sensitivity"] == 45
    for key in ("harmonic_refinement", "detect_sevenths", "detect_sus", "detect_dim_aug", "detect_slash_bass", "temporal_smoothing"):
        assert preset[key] is True
    assert preset["beat_sync"] is False
    opts = _normalize_chord_options({"preset": "balanced"})
    assert opts["sensitivity"] == 45 and opts["beat_sync"] is False
    assert all(opts[key] for key in ("harmonic_refinement", "detect_sevenths", "detect_sus", "detect_dim_aug", "detect_slash_bass", "temporal_smoothing"))


def test_chord_extraction_settings_are_persistent_across_projects():
    assert "CHORD_EXTRACTION_SETTINGS_KEY='mta.chordExtractionSettings.v1'" in JS
    assert "localStorage.setItem(CHORD_EXTRACTION_SETTINGS_KEY" in JS
    assert "restoreChordExtractionSettings()" in JS
    assert "saveChordExtractionSettings();query.push(...chordPipelineQuery())" in JS
    assert "engine:'madmom-deep-chroma'" in JS
    assert "sensitivity:45" in JS


def test_meta_lists_support_inline_edit_context_menu_and_playback_follow():
    assert "function beginMetaInlineEdit" in JS
    assert "ondblclick=\"return beginMetaInlineEdit" in JS
    assert "function openMetaContextMenu" in JS
    for label in ("Modifica", "Disabilita", "Cancella", "Riabilita"):
        assert label in JS
    assert "function syncTimedMetaPanel(timeMs)" in JS
    assert "syncTimedMetaPanel(timeMs);" in JS
    assert "current.show_lyrics_playback" in JS
    assert "current.show_chords_playback" in JS
    assert ".meta-line.active-playback" in CSS
    assert ".meta-line.meta-disabled" in CSS
    assert ".meta-line.meta-deleted" in CSS
