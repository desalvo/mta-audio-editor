from pathlib import Path


def _assets():
    root = Path(__file__).resolve().parents[1]
    return (root / "app/static/app.js").read_text(encoding="utf-8"), (root / "app/static/app.css").read_text(encoding="utf-8")


def test_touch_long_press_opens_existing_track_context_menu():
    js, _ = _assets()
    assert "TRACK_CONTEXT_LONG_PRESS_MS=600" in js
    assert "TRACK_CONTEXT_MOVE_PX=12" in js
    assert "data-track-context-id" in js
    assert "trackContextPointerDown" in js
    assert "trackContextPointerMove" in js
    assert "openTrackContextMenuAt(state.id,state.x,state.y)" in js
    assert "event.pointerType!=='touch'&&event.pointerType!=='pen'" in js


def test_long_press_cancels_on_move_and_pointer_end():
    js, _ = _assets()
    assert "Math.hypot(event.clientX-state.x,event.clientY-state.y)>TRACK_CONTEXT_MOVE_PX" in js
    assert "document.addEventListener('pointerup',trackContextPointerEnd" in js
    assert "document.addEventListener('pointercancel',trackContextPointerEnd" in js


def test_mobile_ellipsis_fallback_and_desktop_contextmenu_remain():
    js, css = _assets()
    assert "track-more-menu" in js
    assert "Menu traccia" in js
    assert "oncontextmenu=\"openTrackContextMenu(event,'${t.id}')\"" in js
    assert "@media (hover:hover) and (pointer:fine){.track-more-menu{display:none}}" in css
    assert "@media (hover:none), (pointer:coarse)" in css
    assert "-webkit-touch-callout:none" in css
    assert "min-height:44px" in css
