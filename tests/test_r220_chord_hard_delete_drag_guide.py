from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = (ROOT / "app/static/app.js").read_text(encoding="utf-8")
CSS = (ROOT / "app/static/app.css").read_text(encoding="utf-8")


def test_chord_delete_is_hard_delete_everywhere():
    assert "for(const i of [...selected].sort((a,b)=>b-a))if(current.chords?.[i])current.chords.splice(i,1)" in JS
    assert "if(action==='delete'&&(kind==='chords'||kind==='markers')){checkpointHistory();current[kind].splice(Number(index),1)" in JS
    assert "if(kind==='chords'||kind==='markers'){arr.splice(i,1);if(kind==='chords')lyricsChordsEditorSelected=-1}" in JS
    assert "if(f.kind==='chords'||f.kind==='markers')arr.splice(f.index,1)" in JS
    assert "if(current?.chords?.some(ch=>ch?.deleted))current.chords=current.chords.filter(ch=>!ch?.deleted)" in JS


def test_timeline_double_click_survives_click_without_drag():
    assert "if(!d.moved)return;const chord=current?.chords?.[d.index]" in JS
    assert 'ondblclick="return beginTimelineChordInlineEdit(event,${index})"' in JS


def test_chord_drag_guide_shows_exact_time():
    assert "createTimelineChordDragGuide(startTime)" in JS
    assert "updateTimelineChordDragGuide(d.guide,d.lastTime)" in JS
    assert "label.textContent=lyricsChordsEditorPosition(timeMs)" in JS
    assert ".timeline-chord-drag-line{" in CSS
    assert ".timeline-chord-drag-time{" in CSS


def test_popular_chord_shortcuts_rank_by_frequency_then_recency():
    assert "function popularProjectChords(limit=8)" in JS
    assert "b.count-a.count||b.last-a.last" in JS
    assert "attachChordShortcutPopover(input,host)" in JS
    assert "chordShortcutHtml('setDraftChordShortcut')" in JS
    assert ".chord-shortcuts button{" in CSS
