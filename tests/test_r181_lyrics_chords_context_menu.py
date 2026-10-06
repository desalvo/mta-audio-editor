from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_JS = (ROOT / 'app/static/app.js').read_text(encoding='utf-8')
APP_CSS = (ROOT / 'app/static/app.css').read_text(encoding='utf-8')


def editor_block():
    start = APP_JS.rindex('function lyricsChordsEditorHtml()')
    end = APP_JS.index('function openLyricsChordsEditor(){', start)
    return APP_JS[start:end]


def test_row_actions_are_contextual_not_inline_buttons():
    block = editor_block()
    assert 'openLyricsChordsContextMenu' in block
    assert 'lc-line-actions' not in block
    assert '>Modifica</button>' not in block
    assert '>Disabilita</button>' not in block
    assert '>Accorpa ↓</button>' not in block
    assert '>Elimina</button>' not in block
    assert '>Ripristina</button>' not in block
    assert 'onclick="addMarkerEditorEvent()">+ Marker</button>' not in block


def test_individual_chords_and_markers_have_context_menus():
    block = editor_block()
    assert "openLyricsChordsContextMenu(event,'chords'" in block
    assert "openLyricsChordsContextMenu(event,'markers'" in block
    assert 'lc-chord-toggle' not in block
    assert 'Click destro: menu chord' in block
    assert 'Click destro: menu marker' in block


def test_context_menu_contains_required_operations():
    assert "['edit','Modifica']" in APP_JS
    assert "['merge','Accorpa con il successivo']" in APP_JS
    assert "['delete','Elimina']" in APP_JS
    assert "['restore','Ripristina']" in APP_JS
    assert "['add-marker','+ Marker']" in APP_JS
    assert "disabled?'Abilita':'Disabilita'" in APP_JS


def test_marker_creation_has_required_start_and_optional_end():
    assert 'id="lcMarkerStart"' in APP_JS
    assert 'id="lcMarkerEnd"' in APP_JS
    assert 'Fine (opzionale)' in APP_JS
    assert 'end_ms:end' in APP_JS
    assert "if(end!=null&&end<start)" in APP_JS


def test_line_time_is_directly_editable_with_same_position_format():
    block = editor_block()
    assert 'editLyricsLineTime' in block
    assert 'lc-time-edit' in block
    assert 'm:ss.mmm' in block
    assert 'mm:ss.mmm' in block
    assert '.lc-time-edit' in APP_CSS
