from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = (ROOT / "app/static/app.js").read_text(encoding="utf-8")
CSS = (ROOT / "app/static/app.css").read_text(encoding="utf-8")


def test_timeline_chord_lane_is_rendered_when_show_chords_is_enabled():
    assert 'id="timelineChordLane"' in JS
    assert 'timelineChordLaneHtml(W)' in JS
    assert "current.show_chords_playback?'':'hidden'" in JS

def test_timeline_chords_support_drag_inline_edit_and_context_menu():
    assert 'beginTimelineChordDrag(event,${index})' in JS
    assert 'beginTimelineChordInlineEdit(event,${index})' in JS
    assert 'openTimelineChordContextMenu(event,${index})' in JS
    assert 'chord.time_ms=d.lastTime' in JS
    assert "item.excluded=true" in JS
    assert "item.deleted=true" in JS
    assert "item.excluded=false" in JS

def test_timeline_can_add_chord_at_playhead():
    assert 'addTimelineChordAtPlayhead()' in JS
    assert 'const timeMs=Math.max(0,Math.round(playCursorMs||0));' in JS
    assert 'current.chords.push({time_ms:Math.max(0,Math.round(Number(timeMs)||0))' in JS
    assert '+ Chord alla posizione corrente' in JS

def test_chord_lane_does_not_change_track_geometry():
    assert '.timeline-chord-lane{position:absolute' in CSS
    assert 'z-index:13' in CSS
    assert 'pointer-events:none' in CSS
