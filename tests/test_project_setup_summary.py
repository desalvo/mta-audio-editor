from pathlib import Path


def test_project_setup_button_and_summary_include_native_save_path_and_core_fields():
    root = Path(__file__).resolve().parents[1]
    html = (root / "app/templates/index.html").read_text(encoding="utf-8")
    js = (root / "app/static/app.js").read_text(encoding="utf-8")
    native = (root / "native/mta_audio_editor_native.py").read_text(encoding="utf-8")
    assert 'onclick="showProjectSetup()"' in html
    assert "async function showProjectSetup()" in js
    for label in ["Formato", "Tracce", "Path di salvataggio", "Insert Master", "RealTime meters"]:
        assert label in js
    assert "get_project_path" in js
    assert "def get_project_path(self, project_id: str)" in native
