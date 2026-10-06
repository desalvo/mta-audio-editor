from pathlib import Path

JS = Path('app/static/app.js').read_text(encoding='utf-8')


def test_selected_chord_click_toggles_selection_off():
    block = JS[JS.rfind('function selectLyricsChord(index)'):]
    block = block[:block.find('\nfunction ', 10)] if '\nfunction ' in block[10:] else block
    assert 'lyricsChordsEditorSelected===next' in block
    assert 'lyricsChordsEditorSelected=-1' in block
    assert 'lyricsChordsEditorFocus=null' in block


def test_latest_chord_chip_uses_toggle_helper_and_keeps_double_click_edit():
    tail = JS[JS.rfind('function lyricsChordsEditorHtml()'):]
    assert 'onclick="event.stopPropagation();selectLyricsChord(${ci})"' in tail
    assert "ondblclick=\"event.stopPropagation();lcRememberScroll();editDraftEvent('chords',${ci})\"" in tail
