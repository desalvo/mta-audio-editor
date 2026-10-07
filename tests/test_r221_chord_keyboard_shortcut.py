from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = (ROOT / "app/static/app.js").read_text(encoding="utf-8")


def test_c_shortcut_adds_chord_only_when_chords_are_shown():
    assert "e.key.toLowerCase()==='c'&&current?.show_chords_playback" in JS
    assert "!e.ctrlKey&&!e.metaKey&&!e.altKey&&!e.shiftKey" in JS
    assert "openAddTimelineChordDialog()" in JS


def test_add_chord_dialog_uses_project_popular_shortcuts_and_current_time():
    assert "showUtilityModal('Aggiungi chord'" in JS
    assert "chordShortcutHtml('setAddTimelineChordShortcut')" in JS
    assert "Posizione corrente:" in JS
    assert "confirmAddTimelineChord(timeMs)" in JS


def test_add_chord_does_not_soft_delete_or_add_deleted_flag():
    block = JS[JS.index("async function confirmAddTimelineChord"):JS.index("function addTimelineChordAtPlayhead")]
    assert "deleted:" not in block
