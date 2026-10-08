from pathlib import Path

from app.ai_models import CHORD_PIPELINE_PRESETS
from app.music_text import _normalize_chord_options

ROOT = Path(__file__).resolve().parents[1]
JS = (ROOT / "app/static/app.js").read_text(encoding="utf-8")
CSS = (ROOT / "app/static/app.css").read_text(encoding="utf-8")


def test_balanced_is_only_default_complete_replacement():
    ids = {p["id"] for p in CHORD_PIPELINE_PRESETS}
    assert "default-complete" not in ids
    assert "balanced" in ids
    balanced = next(p for p in CHORD_PIPELINE_PRESETS if p["id"] == "balanced")
    assert balanced["sensitivity"] == 45
    for key in (
        "harmonic_refinement",
        "detect_sevenths",
        "detect_sus",
        "detect_dim_aug",
        "detect_slash_bass",
        "temporal_smoothing",
    ):
        assert balanced[key] is True
    assert balanced["beat_sync"] is False


def test_legacy_default_complete_normalizes_to_balanced():
    opts = _normalize_chord_options({"preset": "default-complete"})
    assert opts["preset"] == "balanced"
    assert opts["sensitivity"] == 45
    assert opts["detect_dim_aug"] is True
    assert opts["detect_slash_bass"] is True
    assert opts["beat_sync"] is False


def test_selected_range_is_automatic_not_optional():
    assert "id=\"textAnalysisSelectedRange\"" not in JS
    assert "if(range){query.push(`range_start_ms=${range.start_ms}`,`range_end_ms=${range.end_ms}`)}" in JS
    assert "È presente una Range attiva: l’analisi è vincolata" in JS


def test_modal_geometry_is_reset_between_dialogs():
    assert "UTILITY_MODAL_TRANSIENT_CLASSES" in JS
    assert "function resetUtilityModalGeometry()" in JS
    assert "resetUtilityModalGeometry();\n  $('#utilityTitle')" in JS
    assert "'chords-refresh-progress-modal'" in JS
    assert ".utility-modal{min-width:min(420px,94vw);min-height:180px}" in CSS


def test_timeline_chords_support_multiselect_batch_and_backspace():
    assert "timelineChordSelectedIndices=new Set()" in JS
    assert "event.ctrlKey||event.metaKey" in JS
    assert "Disabilita selezionati" in JS
    assert "Riabilita selezionati" in JS
    assert "deleteSelectedTimelineChords" in JS
    assert "e.key==='Backspace'||e.key==='Delete'" in JS
    assert "context-shortcut\">${key}</kbd>" in JS
    assert "context-shortcut\">C</kbd>" in JS
    assert ".timeline-chord-marker.multi-selected" in CSS
