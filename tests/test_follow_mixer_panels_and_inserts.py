from pathlib import Path

from app.models import Project
from app.plugins import plugin_catalog, plugin_manifest


def test_project_persists_follow_and_mixer_panel_visibility():
    project = Project(
        id="p",
        title="UI",
        follow_playback_enabled=True,
        export_panel_visible=False,
        metadata_panel_visible=False,
    )
    restored = Project.model_validate_json(project.model_dump_json())
    assert restored.follow_playback_enabled is True
    assert restored.export_panel_visible is False
    assert restored.metadata_panel_visible is False


def test_single_band_eq_is_not_exposed_but_graphic_eq_is():
    catalog = plugin_catalog()
    manifest = plugin_manifest()
    assert "eq" not in catalog
    assert "eq" not in manifest["schemas"]
    assert "eq" not in manifest["custom"]
    assert "graphic_eq_32" in catalog
    assert "graphic_eq_32" in manifest["schemas"]
    assert len(manifest["schemas"]["graphic_eq_32"]) == 32


def test_ui_has_follow_collapsible_mixer_panels_master_divider_and_mixer_insert_management():
    root = Path(__file__).resolve().parents[1]
    html = (root / "app/templates/index.html").read_text(encoding="utf-8")
    js = (root / "app/static/app.js").read_text(encoding="utf-8")
    css = (root / "app/static/app.css").read_text(encoding="utf-8")

    assert 'id="followBtn"' in html
    assert "toggleFollowPlayback()" in html
    assert "function followPlayhead(" in js
    assert "pane.scrollLeft=Math.max" in js
    assert "followPlayhead(playheadX)" in js

    assert 'onclick="openExportPanel()"' in html
    assert "showMetaPanel('lyrics')" in html and "id=\"viewToolsPanel\"" in html
    assert "function exportWindowHtml()" in js
    assert "exportPaneHtml" not in js
    assert "metadata_panel_visible" in js
    assert "gridTemplateColumns" in js

    assert "master-divider" in js
    assert ".master-divider" in css
    assert ".channel.master" in css

    assert "openMixerInsertManager(" in js
    assert "removeInsert(" in js
    assert "insert-remove" in js
    assert "MASTER inserts" in js
    assert "Gestisci insert Master" in js


def test_graphic_eq_32_editor_uses_sliders_not_numeric_boxes():
    root = Path(__file__).resolve().parents[1]
    js = (root / "app/static/app.js").read_text(encoding="utf-8")
    css = (root / "app/static/app.css").read_text(encoding="utf-8")

    start = js.index("function graphicEqEditorFields")
    end = js.index("function openInsertEditor", start)
    block = js[start:end]
    assert 'type="range"' in block
    assert 'type="number"' not in block
    assert "geq-bands" in block
    assert ".geq-bands" in css
    assert ".geq-slider" in css
