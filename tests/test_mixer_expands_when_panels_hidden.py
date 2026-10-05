from pathlib import Path


def test_mixer_expands_when_metadata_panel_is_hidden_and_export_is_modal():
    root = Path(__file__).resolve().parents[1]
    js = (root / "app/static/app.js").read_text(encoding="utf-8")
    css = (root / "app/static/app.css").read_text(encoding="utf-8")
    assert "function exportWindowHtml()" in js
    assert "exportPaneHtml" not in js
    assert "dock.classList.toggle('meta-hidden',!meta)" in js
    assert "dock.classList.toggle('sidepanels-hidden',!meta)" in js
    assert ":'minmax(0,1fr)'" in js
    assert ".mixer-dock.sidepanels-hidden" in css
    assert ".mixer-dock .mixer-pane{width:100%" in css
