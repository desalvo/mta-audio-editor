from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = (ROOT / 'app/static/app.js').read_text(encoding='utf-8')
CSS = (ROOT / 'app/static/app.css').read_text(encoding='utf-8')
NATIVE = (ROOT / 'native/mta_audio_editor_native.py').read_text(encoding='utf-8')


def test_lyrics_chords_buttons_are_forced_readable():
    assert 'r177: Lyrics + Chords editor buttons are always readable' in CSS
    assert '.lc-toolbar button' in CSS
    assert '-webkit-text-fill-color:#eef8ff!important' in CSS
    assert 'white-space:normal!important' in CSS


def test_timeline_range_is_per_selected_track_and_count_is_visible():
    assert 'id="selectedTrackCount"' in JS
    assert 'data-selection-track="${t.id}"' in JS
    assert "ids.has(s.dataset.selectionTrack)" in JS
    assert "splitSelectedTracksAt(downMs)" in JS
    assert "editTrackIds()" in JS


def test_delete_actions_are_in_compact_toolbar():
    assert 'compact-delete' in JS
    assert 'Delete tracks' in JS
    assert 'Delete selected range' in JS


def test_native_language_auto_and_manual_override_are_persisted():
    assert 'system_language' in NATIVE
    assert 'language must be auto, it or en' in NATIVE
    assert 'id="nativeLanguage"' in JS
    assert 'Auto (system)' in JS
    assert "String(cfg.system_language||'en').toLowerCase().startsWith('it')" in JS
    assert 'applyInterfaceLanguage' in JS
