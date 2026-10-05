from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = (ROOT / "app/static/app.js").read_text(encoding="utf-8")
CSS = (ROOT / "app/static/app.css").read_text(encoding="utf-8")


def test_lyrics_editor_is_structured_and_not_prompt_based():
    assert "function timedEditorConfig(kind)" in JS
    assert "lyrics:{key:'text',label:'Lyrics',end:true,valueLabel:'Testo'}" in JS
    assert "class=\"timed-start\"" in JS
    assert "class=\"timed-end\"" in JS
    assert "class=\"timed-value\"" in JS
    assert "saveTimedEditor(kind)" in JS
    assert "prompt(label,linesToText" not in JS


def test_timed_editor_supports_add_remove_sort_and_time_formats():
    assert "function addTimedEditorRow(kind)" in JS
    assert "function removeTimedEditorRow(button)" in JS
    assert "out.sort((a,b)=>a.time_ms-b.time_ms)" in JS
    assert "function parseTimedEditorTime(value)" in JS
    assert "raw.includes(':')" in JS


def test_edited_lyrics_invalidate_stale_word_timing_only_when_changed():
    assert "item.words=prev.words||[]" in JS
    assert "else if(kind==='lyrics')item.words=[]" in JS


def test_timed_editor_modal_is_large_resizable_and_mobile_safe():
    assert ".utility-modal.timed-editor-modal" in CSS
    assert "resize:both" in CSS
    assert ".timed-editor-table-wrap" in CSS
    assert "overflow:auto" in CSS
    assert "textarea{min-height:54px;resize:vertical" in CSS
    assert "resize:none" in CSS
