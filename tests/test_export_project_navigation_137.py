from pathlib import Path


def test_export_is_modal_and_not_a_mixer_side_panel():
    root = Path(__file__).resolve().parents[1]
    html = (root / "app/templates/index.html").read_text(encoding="utf-8")
    js = (root / "app/static/app.js").read_text(encoding="utf-8")
    assert 'onclick="openExportPanel()"' in html
    assert "function exportWindowHtml()" in js
    assert "showUtilityModal('Export',exportWindowHtml())" in js
    assert "exportPaneHtml" not in js
    mixer = js[js.index("function mixerHtml()") : js.index("function metaPaneHtml()")]
    assert "export_panel_visible" not in mixer
    assert "exportPane" not in mixer


def test_projects_sidebar_is_removed_and_web_native_open_flows_are_explicit():
    root = Path(__file__).resolve().parents[1]
    html = (root / "app/templates/index.html").read_text(encoding="utf-8")
    js = (root / "app/static/app.js").read_text(encoding="utf-8")
    assert 'id="projectsPanel"' not in html
    assert '>PROJECTS<' not in html
    assert 'id="openRecentProjectBtn"' in html
    assert 'id="openLocalProjectBtn"' in html
    assert "function openProjectSelector()" in js
    assert "if(currentUser?.native_single_user)return openProjectArchive()" in js
    assert "showUtilityModal('Open project'" in js
    assert "function openLocalProject()" in js
    assert "function openRecentProjects()" in js
    assert "mtaRecentProjects" in js
