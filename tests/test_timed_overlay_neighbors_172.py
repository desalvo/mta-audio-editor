from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_JS = (ROOT / "app" / "static" / "app.js").read_text(encoding="utf-8")
APP_CSS = (ROOT / "app" / "static" / "app.css").read_text(encoding="utf-8")


def test_settings_expose_independent_previous_next_options():
    assert "Show previous and next chords" in APP_JS
    assert "Show previous and next lyrics" in APP_JS
    assert "showPreviousNextChords" in APP_JS
    assert "showPreviousNextLyrics" in APP_JS


def test_timed_overlay_uses_previous_current_next_triplet():
    assert "function timedItemTriplet" in APP_JS
    assert "timedOverlayTripletHtml" in APP_JS
    assert "current" in APP_JS
    assert "timed-overlay-item ${role}" in APP_JS


def test_timed_overlay_styles_current_and_neighbors_differently():
    assert ".timed-overlay-item.previous,.timed-overlay-item.next" in APP_CSS
    assert ".timed-overlay-item.current" in APP_CSS
    assert "opacity:.38" in APP_CSS
