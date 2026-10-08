from pathlib import Path

from app import main
from app.models import Chord, LyricLine

ROOT = Path(__file__).resolve().parents[1]
JS = (ROOT / "app/static/app.js").read_text(encoding="utf-8")
MAIN = (ROOT / "app/main.py").read_text(encoding="utf-8")
CSS = (ROOT / "app/static/app.css").read_text(encoding="utf-8")


def test_timed_event_range_replacement_preserves_outside_events():
    old = [
        LyricLine(time_ms=1000, text="before"),
        LyricLine(time_ms=5000, text="old inside"),
        LyricLine(time_ms=9000, text="after"),
    ]
    new = [LyricLine(time_ms=6000, text="new inside")]
    merged = main._replace_timed_range(old, new, 4000, 8000)
    assert [(x.time_ms, x.text) for x in merged] == [
        (1000, "before"), (6000, "new inside"), (9000, "after")
    ]


def test_shift_timed_events_moves_lyrics_words_and_chords():
    line = LyricLine(time_ms=100, end_ms=500, text="ciao", words=[{"text":"ciao","start_ms":120,"end_ms":450}])
    chord = Chord(time_ms=250, chord="C")
    shifted_line = main._shift_timed_events([line], 4000)[0]
    shifted_chord = main._shift_timed_events([chord], 4000)[0]
    assert shifted_line.time_ms == 4100 and shifted_line.end_ms == 4500
    assert shifted_line.words[0].start_ms == 4120 and shifted_line.words[0].end_ms == 4450
    assert shifted_chord.time_ms == 4250


def test_partial_extraction_api_and_ui_are_wired():
    assert "range_start_ms: int | None = None" in MAIN
    assert "range_end_ms: int | None = None" in MAIN
    assert "_replace_timed_range(latest.lyrics" in MAIN
    assert "_replace_timed_range(latest.chords" in MAIN
    assert "function currentExtractionRange()" in JS
    assert 'id="textAnalysisSelectedRange"' not in JS
    assert "if(range){query.push(`range_start_ms=${range.start_ms}`,`range_end_ms=${range.end_ms}`)}" in JS
    assert "range_start_ms=${range.start_ms}" in JS
    assert "range_end_ms=${range.end_ms}" in JS
    assert "Solo intervallo selezionato" in JS


def test_ctrl_cmd_multi_select_and_batch_delete_for_lyrics_chords():
    assert "const metaMultiSelection={lyrics:new Set(),chords:new Set()}" in JS
    assert "event?.metaKey||event?.ctrlKey" in JS
    assert "async function deleteSelectedMetaEvents(kind)" in JS
    assert "Cancella ${multiCount} selezionati" in JS
    assert "current[kind].splice(index,1)" in JS
    assert "eliminazione batch chords" in JS
    assert ".meta-line.meta-multi-selected" in CSS
