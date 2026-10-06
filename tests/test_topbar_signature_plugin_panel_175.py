from pathlib import Path

from app.models import Project

ROOT = Path(__file__).resolve().parents[1]
INDEX = (ROOT / "app" / "templates" / "index.html").read_text(encoding="utf-8")
APP_JS = (ROOT / "app" / "static" / "app.js").read_text(encoding="utf-8")
APP_CSS = (ROOT / "app" / "static" / "app.css").read_text(encoding="utf-8")


def test_topbar_exposes_editable_time_signature():
    assert 'id="transportTimeSignature"' in INDEX
    assert 'onchange="setProjectTimeSignature(this.value,true)"' in INDEX
    for signature in ("2/4", "3/4", "4/4", "5/4", "6/8", "7/8", "9/8", "12/8"):
        assert f">{signature}<" in INDEX or f">{signature}</option>" in INDEX
    assert "$('#transportTimeSignature').value=current.time_signature||'4/4'" in APP_JS


def test_plugins_inspector_can_close_and_reopen():
    project = Project(id="p", title="Song")
    assert project.inspector_visible is True
    assert "function closeInspectorPanel()" in APP_JS
    assert "current.inspector_visible=false" in APP_JS
    assert "current.inspector_visible=true" in APP_JS
    assert "inspector-close" in APP_CSS
    assert "editor-grid.inspector-hidden" in APP_CSS
