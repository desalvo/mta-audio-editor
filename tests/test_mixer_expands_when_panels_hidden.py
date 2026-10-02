from pathlib import Path


def test_mixer_expands_when_export_or_metadata_panels_are_hidden():
    root = Path(__file__).resolve().parents[1]
    js = (root / "app/static/app.js").read_text(encoding="utf-8")
    css = (root / "app/static/app.css").read_text(encoding="utf-8")
    assert "dock.classList.toggle('export-hidden',!exp)" in js
    assert "dock.classList.toggle('meta-hidden',!meta)" in js
    assert "dock.classList.toggle('sidepanels-hidden',!exp&&!meta)" in js
    assert ":'minmax(0,1fr)'" in js
    assert ".mixer-dock.sidepanels-hidden" in css
    assert ".mixer-dock .mixer-pane{width:100%" in css
