from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = (ROOT / "app/static/app.js").read_text()
CSS = (ROOT / "app/static/app.css").read_text()


def test_stop_and_close_clear_timed_overlay():
    assert "function clearTimedPlaybackOverlay()" in JS
    active = JS[JS.rfind("function stopPlayback(){"): JS.index("function pausePlayback(){", JS.rfind("function stopPlayback(){"))]
    assert "clearTimedPlaybackOverlay();" in active
    close = JS[JS.index("function closeCurrentProject(){"): JS.index("function recentProjectIds(){")]
    assert "stopPlayback();" in close
    assert "clearTimedPlaybackOverlay();" in close


def test_lyrics_chords_timestamp_box_is_wider_and_no_wrap():
    assert "grid-template-columns:76px minmax(0,1fr)!important" in CSS
    assert "min-width:72px!important" in CSS
    assert "white-space:nowrap!important" in CSS
