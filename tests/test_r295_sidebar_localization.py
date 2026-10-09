from pathlib import Path


def test_attribute_translation_is_idempotent():
    js = (Path(__file__).resolve().parents[1] / "app/static/app.js").read_text()
    assert "if(translated!==original)el.setAttribute(a,translated)" in js
    assert "if(translated!==original)element.setAttribute(attribute,translated)" in js
    assert "else if(change.type==='attributes'&&change.target?.nodeType===Node.ELEMENT_NODE)localizationPending.add(change.target)" not in js


def test_sidebar_still_allows_no_project_navigation():
    html = (Path(__file__).resolve().parents[1] / "app/templates/index.html").read_text()
    assert 'onclick="showSettings()"' in html
    assert 'onclick="showAbout()"' in html
    assert 'onclick="toggleViewToolsPanel()"' in html
