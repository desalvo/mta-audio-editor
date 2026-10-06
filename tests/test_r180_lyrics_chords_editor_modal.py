from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_JS = (ROOT / "app/static/app.js").read_text(encoding="utf-8")
APP_CSS = (ROOT / "app/static/app.css").read_text(encoding="utf-8")


def test_editor_has_persistent_save_actions():
    assert 'class="utility-btn primary lc-save-btn" onclick="saveLyricsChordsEditor()">Salva</button>' in APP_JS
    assert APP_JS.count('onclick="saveLyricsChordsEditor()">Salva</button>') >= 2


def test_editor_warns_before_discarding_changes():
    assert "function lyricsChordsEditorHasChanges()" in APP_JS
    assert "function closeLyricsChordsEditor()" in APP_JS
    assert "Modifiche non salvate" in APP_JS
    assert "lyrics-chords-editor-modal')&&lyricsChordsEditorHasChanges()" in APP_JS


def test_editor_body_is_scrollable_and_controls_stay_visible():
    assert 'class="lc-editor-scroll"' in APP_JS
    assert ".lc-editor-scroll" in APP_CSS
    assert "overflow-y:scroll!important" in APP_CSS
    assert ".lc-editor-footer" in APP_CSS
    assert "position:sticky" in APP_CSS


def test_native_webview_button_text_is_forced_visible():
    assert ".lyrics-chords-editor button *" in APP_CSS
    assert "-webkit-text-fill-color:#f4fbff!important" in APP_CSS
    assert ".lyrics-chords-editor .lc-save-btn" in APP_CSS


def test_close_prompt_offers_save_discard_cancel():
    assert "showLyricsChordsClosePrompt" in APP_JS
    assert "Sì, salva" in APP_JS
    assert "No, scarta" in APP_JS
    assert "Annulla" in APP_JS
    assert "discardLyricsChordsEditorChanges" in APP_JS
    assert "cancelLyricsChordsEditorClose" in APP_JS


def test_event_modify_uses_two_column_position_text_table():
    assert 'class="lc-event-edit-table"' in APP_JS
    assert '<th>Posizione</th><th>Testo</th>' in APP_JS
    assert 'Formato posizione:' in APP_JS
    assert 'm:ss.mmm' in APP_JS
    assert 'mm:ss.mmm' in APP_JS
    assert 'parseLyricsChordsEditorPosition' in APP_JS
    assert r"(\d{1,3})" in APP_JS


def test_expanded_editor_removes_expanded_modal_constraint():
    assert "modal?.classList.remove('meta-expanded-modal')" in APP_JS
    assert "modal?.classList.add('lyrics-chords-editor-modal')" in APP_JS


def test_edit_lyrics_add_bottom_button_has_native_contrast_class():
    assert 'timed-add-bottom' in APP_JS
    assert '.timed-editor-modal .timed-add-bottom' in APP_CSS
    assert '-webkit-text-fill-color:#f4fbff!important' in APP_CSS


def test_combined_editor_omits_duplicate_chords_and_markers_sections():
    start = APP_JS.rindex("function lyricsChordsEditorHtml()")
    end = APP_JS.index("function openLyricsChordsEditor()", start)
    block = APP_JS[start:end]
    assert '<h3>Chords</h3>' not in block
    assert '<h3>Markers / sezioni</h3>' not in block
    assert 'solo l\'editor combinato Lyrics + Chords + Markers' in block


def test_combined_editor_has_explicit_vertical_scrollbar():
    assert 'overflow-y:scroll!important' in APP_CSS
    assert '.lc-editor-scroll::-webkit-scrollbar' in APP_CSS
    assert 'scrollbar-gutter:stable both-edges' in APP_CSS
