from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_piano_popup_fallback_draggable():
    js = (ROOT / "app/static/app.js").read_text()
    css = (ROOT / "app/static/app.css").read_text()
    assert "if(!popup){pianoOpenFloating();return}" in js
    assert "function pianoOpenFloating()" in js
    assert "head.addEventListener('pointerdown'" in js
    assert "resize:both" in css
    assert "pianoFloatingLab.remove()" in js


def test_toggles_have_full_size_svg_and_tooltips():
    html = (ROOT / "app/templates/index.html").read_text()
    css = (ROOT / "app/static/app.css").read_text()
    for element_id in ("showLyricsBtn", "showChordsBtn", "showMarkersBtn"):
        content = html.split(f'id="{element_id}"', 1)[1].split("</button>", 1)[0]
        assert "<svg" in content
        assert "title=" in content
    assert ".transport-btn.timed-display-mode svg{display:block;width:100%;height:100%" in css
