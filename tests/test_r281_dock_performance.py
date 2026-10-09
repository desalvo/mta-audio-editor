from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = (ROOT / "app/static/app.js").read_text()


def test_meta_tabs_update_only_the_dock():
    method = JS.split("function showMetaPanel(kind='lyrics'){", 1)[1].split("\n}", 1)[0]
    assert "updateDockMetadataPanel()" in method
    assert "if(!updateDockMetadataPanel())render()" in method
    assert "current.mixer_meta_tab=kind" in method


def test_dock_swaps_existing_element_and_translates_only_new_content():
    method = JS.split("function updateDockMetadataPanel(){", 1)[1].split("\n}", 1)[0]
    assert "existing.replaceWith(replacement)" in method
    assert "applyInterfaceLanguage(replacement)" in method
    assert "updateMixerDockLayout()" in method
    assert "render()" not in method


def test_inspector_navigation_avoids_full_render_for_existing_dom():
    method = JS.split("function focusInspector(){", 1)[1].split("\n", 1)[0]
    assert "grid?.classList.remove('inspector-hidden')" in method
    assert "if(!$('#inspector'))render()" in method
