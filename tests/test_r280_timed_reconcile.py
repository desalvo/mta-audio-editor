from pathlib import Path

from app.models import Chord, Marker


JS = (Path(__file__).resolve().parents[1] / 'app/static/app.js').read_text(encoding='utf-8')


def test_reconcile_start_uses_previous_end():
    assert "edge==='start'?timedRowEnd(neighbor):timedRowStart(neighbor)" in JS
    assert "input.value=timedEditorTime(value)" in JS


def test_reconcile_end_uses_next_start_and_has_boundary_guards():
    assert "edge==='start'?row.previousElementSibling:row.nextElementSibling" in JS
    assert "Nessuna riga precedente" in JS
    assert "Nessuna riga successiva" in JS
    assert 'openTimedTimestampMenu(event,this' in JS


def test_split_keeps_original_end_for_new_row():
    assert "const endInput=row.querySelector('.timed-end')" in JS
    assert 'endInput.value=timedEditorTime(middle)' in JS
    assert 'timedEditorRow(kind,{time_ms:middle,end_ms:end' in JS


def test_optional_end_ms_supported_for_chords_and_markers():
    assert Chord(time_ms=0, chord='C', end_ms=500).end_ms == 500
    assert Marker(time_ms=0, label='A', end_ms=500).end_ms == 500
    assert 'chords:{key:\'chord\',label:\'Chords\',end:true' in JS
    assert 'markers:{key:\'label\',label:\'Markers\',end:true' in JS
