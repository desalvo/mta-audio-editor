from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = (ROOT / "app/static/app.js").read_text(encoding="utf-8")
CSS = (ROOT / "app/static/app.css").read_text(encoding="utf-8")


def test_lyrics_rows_can_be_inserted_above_below_or_split():
    assert "function insertTimedEditorRow(button,kind,where='below')" in JS
    assert "＋ sopra" in JS
    assert "＋ sotto" in JS
    assert "function splitTimedEditorRow(button,kind)" in JS
    assert "title=\"Dividi riga\"" in JS
    assert "const middle=Math.round((start+end)/2)" in JS


def test_lyrics_rows_can_be_deleted_with_save_only_semantics():
    assert "function removeTimedEditorRow(button)" in JS
    assert "Eliminare questa riga?" in JS
    assert "La modifica sarà applicata solo premendo Salva." in JS
    assert "row.remove();renumberTimedEditorRows()" in JS


def test_inserted_rows_get_suggested_editable_timestamps():
    assert "function suggestedTimedRow(kind,row,where)" in JS
    assert "item.end_ms=" in JS
    assert "timedEditorTime(middle)" in JS


def test_original_word_timing_tracks_original_row_after_insert_delete():
    assert "data-original-index" in JS
    assert "const originalIndex=Number(row.dataset.originalIndex)" in JS
    assert "old[originalIndex]" in JS


def test_action_column_is_wide_and_wraps():
    assert ".timed-row-actions{display:flex" in CSS
    assert "width:190px" in CSS
    assert "flex-wrap:wrap" in CSS


def test_chord_rows_have_same_insert_split_delete_workflow():
    assert "kind==='lyrics'||kind==='chords'" in JS
    assert "timedEditorRow('chords',{time_ms:middle,chord:''}" in JS
    assert "Dividi crea un nuovo punto accordo" in JS
    assert "removeTimedEditorRow(this)" in JS
