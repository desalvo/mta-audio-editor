from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = (ROOT / "app/static/app.js").read_text(encoding="utf-8")
CSS = (ROOT / "app/static/app.css").read_text(encoding="utf-8")
NATIVE = (ROOT / "native/mta_audio_editor_native.py").read_text(encoding="utf-8")


def test_lyrics_chords_editor_buttons_are_readable():
    assert ".lyrics-chords-editor button" in CSS
    assert "white-space:normal!important" in CSS
    assert "-webkit-text-fill-color:#eef8ff!important" in CSS


def test_selection_overlay_and_count_are_track_scoped():
    assert 'id="selectedTrackCount"' in JS
    assert 'data-selection-track="${t.id}"' in JS
    assert "ids.has(s.dataset.selectionTrack)" in JS
    assert "selectedTrackIds()" in JS


def test_native_language_auto_override_is_persisted():
    assert 'language = "auto"' in NATIVE
    assert 'language not in {"auto", "it", "en"}' in NATIVE
    assert "system_language" in NATIVE
    assert "nativeLanguage" in JS
    assert "applyInterfaceLanguage()" in JS


def test_about_shows_revision_for_early_and_stable_label_otherwise():
    assert "const revisionLabel=channel==='early'?`r${info.revision||''}`:'stable'" in JS
    assert "<dt>Revisione</dt><dd>${esc(revisionLabel)}</dd>" in JS
    assert "<dt>Release</dt><dd>${esc(releaseLabel)}</dd>" in JS
    assert "info.release_channel||'stable'" in JS
