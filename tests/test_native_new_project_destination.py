from pathlib import Path


def test_native_new_project_requires_save_destination_before_creation():
    root = Path(__file__).resolve().parents[1]
    js = (root / "app/static/app.js").read_text(encoding="utf-8")

    start = js.index("async function createProjectFromDialog()")
    end = js.index("async function openP", start)
    block = js[start:end]

    assert "pendingNewProjectPath" in block
    assert "await bridge.choose_project_save_path(title)" in block
    assert "if(chosen?.cancelled===true)" in block
    assert "if(!chosen?.ok)throw Error" in block
    assert "bind_project_path(created.id,pendingNewProjectPath)" in block

    choose = block.index("await bridge.choose_project_save_path(title)")
    create = block.index("await api('/api/projects?")
    bind = block.index("bind_project_path(created.id,pendingNewProjectPath)")
    assert choose < create < bind


def test_native_new_project_dialog_asks_for_destination_on_create():
    root = Path(__file__).resolve().parents[1]
    js = (root / "app/static/app.js").read_text(encoding="utf-8")
    start=js.index('async function newProject()');end=js.index('async function createProjectFromDialog()',start)
    assert 'id="newProjectPath"' not in js[start:end]
    assert 'chooseNewProjectPath()' not in js[start:end]
    assert 'id="createProjectButton"' in js[start:end]
