from pathlib import Path

JS = Path('app/static/app.js').read_text()
CSS = Path('app/static/app.css').read_text()

def test_double_click_opens_structured_editors():
    assert "ondblclick=\"event.stopPropagation();lcRememberScroll();editDraftEvent('chords'" in JS
    assert "ondblclick=\"event.stopPropagation();lcRememberScroll();editDraftEvent('markers'" in JS
    assert "editDraftEvent('lyrics'" in JS

def test_inline_lyrics_editing_does_not_touch_timestamp_directly():
    assert 'contenteditable=\"true\"' in JS
    assert 'commitLyricsInlineUnit(' in JS
    block = JS[JS.index('function commitLyricsInlineUnit'):JS.index('function openLyricsChordsContextMenu', JS.index('function commitLyricsInlineUnit'))]
    assert 'line.time_ms=' not in block
    assert 'line.text=' in block
    assert 'line.words=' in block
    assert '.lc-lyrics-inline' in CSS

def test_deleted_token_reanchors_chords_previous_then_next():
    block = JS[JS.index('function lcReanchorDeletedUnit'):JS.index('function commitLyricsInlineUnit')]
    assert 'wi>0' in block
    assert 'remainingWords.length' in block
    assert 'anchor_word_index=wi-1' in block
    assert 'anchor_word_index=0' in block
    assert "ch.anchor_kind='start'" in block

def test_revision_184_metadata():
    assert Path('REVISION').read_text().strip() == '184'
    assert 'versionCode = 20184' in Path('mobile/android/app/build.gradle.kts').read_text()
    assert '<string>20184</string>' in Path('mobile/ios/MTAEditorMobile/Info.plist').read_text()
