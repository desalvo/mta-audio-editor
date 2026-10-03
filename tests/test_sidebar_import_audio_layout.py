from pathlib import Path


def test_import_audio_button_text_is_contained_in_sidebar_button():
    root = Path(__file__).resolve().parents[1]
    html = (root / "app/templates/index.html").read_text(encoding="utf-8")
    css = (root / "app/static/app.css").read_text(encoding="utf-8")
    assert 'class="nav-item import-action import-audio-action"' in html
    assert 'class="nav-label">Import Audio</span>' in html
    assert ".sidebar .nav-item.import-audio-action" in css
    assert "grid-template-columns:18px minmax(0,1fr)" in css
    assert "overflow:hidden" in css
    assert ".nav-label" in css
    assert "min-width:0" in css
