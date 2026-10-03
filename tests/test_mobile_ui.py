from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_mobile_header_icons_are_explicit_elements():
    html = (ROOT / "app/templates/index.html").read_text(encoding="utf-8")
    assert 'class="control-icon"' in html
    assert 'aria-label="Account"' in html
    assert 'aria-label="Amministrazione"' in html
    assert 'aria-label="Save"' in html
    assert 'aria-label="Export"' in html
    assert 'aria-label="Esci"' in html


def test_mobile_css_keeps_icon_and_hides_only_text():
    css = (ROOT / "app/static/app.css").read_text(encoding="utf-8")
    assert ".header-actions .control-text{display:none}" in css
    assert ".header-actions .control-icon{display:inline-flex" in css
    assert "::first-letter" not in css


def test_dynamic_controls_receive_hover_titles():
    js = (ROOT / "app/static/app.js").read_text(encoding="utf-8")
    assert "function ensureControlTooltips(" in js
    assert "new MutationObserver" in js
    assert "setAttribute('title',name)" in js
