from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = (ROOT / 'app/static/app.js').read_text(encoding='utf-8')
CSS = (ROOT / 'app/static/app.css').read_text(encoding='utf-8')
MODELS = (ROOT / 'app/models.py').read_text(encoding='utf-8')
MUSIC = (ROOT / 'app/music_text.py').read_text(encoding='utf-8')


def test_pdf_preview_uses_html_not_pdf_iframe():
    tail = JS[JS.rfind('async function previewProjectLyricsPdf'):]
    assert 'lyricsPdfHtmlPreview()' in tail
    assert '<iframe' not in tail.split('function closeLyricsPdfPreview', 1)[0]


def test_editor_has_granular_anchors_and_chord_sequences():
    assert 'anchor_kind: Literal["start", "word", "end"]' in MODELS
    assert 'anchor_syllable_index' in MODELS
    assert 'anchor_order' in MODELS
    assert 'dropLyricsChordOnChord' in JS
    assert "'start'" in JS and "'end'" in JS
    assert 'editorWordUnits' in JS


def test_editor_preserves_scroll_and_supports_history_clipboard():
    for token in ['lyricsChordsEditorScrollTop', 'undoLyricsChordsEditor', 'redoLyricsChordsEditor',
                  'cutLyricsChordsItem', 'copyLyricsChordsItem', 'pasteLyricsChordsItem']:
        assert token in JS
    assert 'lcRestoreScroll()' in JS


def test_split_here_is_context_menu_not_per_word_button():
    tail = JS[JS.rfind('function lyricsChordsEditorHtml'):]
    assert 'openLyricsWordContextMenu' in JS
    assert 'Dividi qui' in JS
    assert 'lc-split-word' not in tail.split('function refreshLyricsChordsEditor', 1)[0]


def test_editor_is_compact_and_timestamp_stays_one_line():
    assert 'white-space:nowrap!important' in CSS
    assert '.lc-line{grid-template-columns:66px' in CSS
    assert '.lc-syllable{font-size:13px' in CSS


def test_saving_overlay_warns_and_blocks_close():
    assert 'Salvataggio in corso…' in JS
    assert 'lyricsChordsSaving' in JS
    assert 'Attendere: Lyrics, Chords e Markers vengono persistiti nel progetto.' in JS


def test_pdf_page_break_reapplies_chord_style_after_ensure():
    fragment = MUSIC[MUSIC.index('if line_chords:'):MUSIC.index('lyric_font,lyric_size', MUSIC.index('if line_chords:'))]
    assert fragment.index('ensure(chord_size+16)') < fragment.index('c.setFont(chord_font, chord_size)')
    assert 'anchor_syllable_index' in MUSIC
