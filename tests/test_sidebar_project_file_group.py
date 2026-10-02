from pathlib import Path


def test_project_file_sidebar_group_is_collapsible_and_collapsed_by_default():
    root = Path(__file__).resolve().parents[1]
    html = (root / "app/templates/index.html").read_text(encoding="utf-8")
    js = (root / "app/static/app.js").read_text(encoding="utf-8")
    css = (root / "app/static/app.css").read_text(encoding="utf-8")

    assert 'class="sidebar-tools collapsed" id="projectToolsPanel"' in html
    assert "PROJECT / FILE" in html
    for label in ("Export", "Save project locally", "Save project as", "Open project", "Project files", "Delete project"):
        assert label in html
    assert "function toggleProjectToolsPanel()" in js
    assert ".sidebar-tools.collapsed .sidebar-tools-body{display:none}" in css
