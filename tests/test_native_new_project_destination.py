from pathlib import Path


def test_native_new_project_requires_save_destination_before_creation():
    root = Path(__file__).resolve().parents[1]
    js = (root / "app/static/app.js").read_text(encoding="utf-8")

    start = js.index("async function createProjectFromDialog()")
    end = js.index("async function openP", start)
    block = js[start:end]

    assert "pendingNewProjectPath" in block
    assert "await chooseNewProjectPath()" in block
    assert "if(!pendingNewProjectPath)return" in block
    assert "bind_project_path(created.id,pendingNewProjectPath)" in block

    choose = block.index("await chooseNewProjectPath()")
    create = block.index("await api('/api/projects?")
    bind = block.index("bind_project_path(created.id,pendingNewProjectPath)")
    assert choose < create < bind


def test_native_new_project_dialog_shows_path_field():
    root = Path(__file__).resolve().parents[1]
    js = (root / "app/static/app.js").read_text(encoding="utf-8")
    css = (root / "app/static/app.css").read_text(encoding="utf-8")

    assert "Percorso di salvataggio" in js
    assert 'id="newProjectPath"' in js
    assert "Scegli…" in js
    assert "function chooseNewProjectPath()" in js
    assert ".native-path-row" in css
