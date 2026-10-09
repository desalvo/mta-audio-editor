from pathlib import Path


def test_chord_lane_does_not_obscure_first_track():
    css = (Path(__file__).resolve().parents[1] / "app/static/app.css").read_text()
    sticky = css.split("/* r285:", 1)[1].split(".project-marker-line", 1)[0]
    assert ".timeline-chord-lane:not(.hidden)" in sticky
    assert "position:sticky" in sticky
    assert "background:transparent" in sticky
    assert "linear-gradient" not in sticky
    assert "pointer-events:none" in css.split(".timeline-chord-lane{", 1)[1].split("}", 1)[0]
    assert "pointer-events:auto" in css.split(".timeline-chord-marker{", 1)[1].split("}", 1)[0]
