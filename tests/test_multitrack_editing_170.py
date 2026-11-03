from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = (ROOT / "app/static/app.js").read_text()
CSS = (ROOT / "app/static/app.css").read_text()


def test_ctrl_cmd_multiselect_replaces_track_checkboxes():
    assert "event.ctrlKey||event.metaKey" in JS
    assert "selectedTrackIdSet" in JS
    assert 'class="track-check"' not in JS
    assert "selectedTrackIds(){ensureTrackSelection()" in JS


def test_split_tool_prefers_selected_segments_then_selected_tracks():
    assert "function splitSelectedTracksAt(ms)" in JS
    split = JS[JS.index('function splitSelectedTracksAt(ms)'):JS.index('function timelineJoinPair()')]
    assert "const selected=selectedSegmentItems()" in split
    assert "keys.size?new Set(selected.map(x=>x.track.id)):new Set(selectedTrackIds())" in split
    assert "keys.size&&!keys.has(key)" in split
    assert "if(!ids.has(t.id)||t.kind==='midi')continue" in split
    assert "timelineTool==='split'" in JS


def test_range_delete_and_ripple_are_scoped_to_selected_tracks():
    assert "track_ids:ids,ripple:rippleEnabled" in JS
    assert "removeRangeFromTracks(a,b,ids,rippleEnabled)" in JS
    assert "function toggleRippleTool()" in JS
    assert "ripple globale" not in JS


def test_track_selection_is_visually_persistent():
    assert "selectedTrackIdSet.has(t.id)?'selected':''" in JS
    assert ".track-head.primary-selected" in CSS
