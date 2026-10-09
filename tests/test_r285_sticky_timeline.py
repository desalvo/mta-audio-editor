from pathlib import Path


def test_chord_overlay_sticky():
    css = (Path(__file__).resolve().parents[1] / "app/static/app.css").read_text()
    rules = css.split("/* r285:", 1)[1]
    assert ".timeline-chord-lane:not(.hidden)" in rules
    assert "position:sticky" in rules
    assert "top:30px" in rules


def test_markers_remain_editable():
    root = Path(__file__).resolve().parents[1]
    css = (root / "app/static/app.css").read_text().split("/* r285:", 1)[1]
    js = (root / "app/static/app.js").read_text()
    assert ".project-marker-line .project-marker-caption" in css
    assert ".project-marker-line .project-marker-handle" in css
    assert 'onpointerdown="beginTimelineMarkerDrag(event,' in js
    assert 'ondblclick="return beginTimelineMarkerInlineEdit(event,' in js
    assert 'oncontextmenu="return openTimelineMarkerContextMenu(event,' in js
