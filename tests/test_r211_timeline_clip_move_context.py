from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = (ROOT / "app/static/app.js").read_text(encoding="utf-8")
CSS = (ROOT / "app/static/app.css").read_text(encoding="utf-8")


def test_clip_blocks_are_draggable_in_select_mode():
    assert "function beginTimelineClipDrag(event,trackId,clipId)" in JS
    assert "if(timelineTool!=='select'||event.button!==0)return" in JS
    assert 'onpointerdown="beginTimelineClipDrag(event' in JS
    assert "timeline_start_ms=Math.max(0,item.start+d.delta)" in JS
    assert ".clip-block{pointer-events:auto}" in CSS


def test_shift_drag_moves_selected_track_groups():
    assert "const group=!!event.shiftKey" in JS
    assert "const ids=group?new Set(selectedTrackIds()):new Set([trackId])" in JS
    assert "Segmenti delle tracce selezionate spostati sulla timeline" in JS


def test_timeline_context_menu_exposes_delete_selected_range():
    assert 'closeTrackContextMenu();deleteSelection(true)' in JS
    assert '<span>Delete selected range</span>' in JS


def test_ripple_close_gap_remains_available():
    assert "removeRangeFromTracks(a,b,ids,rippleEnabled)" in JS
    assert "body:JSON.stringify({start_ms:a,end_ms:b,track_ids:ids,ripple:rippleEnabled})" in JS
