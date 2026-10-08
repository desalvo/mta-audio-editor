from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = (ROOT / "app/static/app.js").read_text(encoding="utf-8")


def test_timeline_chord_inline_editor_has_save_close_and_direct_enter_commit():
    start = JS.index("function attachChordShortcutPopover")
    end = JS.index("function closeChordShortcutPopover", start)
    popover = JS[start:end]
    assert "chord-shortcuts-close" in popover
    assert "Chiudi e salva modifica" in popover
    assert "onCloseCommit?.()" in popover

    start = JS.index("function beginTimelineChordInlineEdit")
    end = JS.index("function closeTimelineChordContextMenu", start)
    editor = JS[start:end]
    assert "attachChordShortcutPopover(input,host,null,commit)" in editor
    assert "if(e.key==='Enter'){e.preventDefault();void commit()}" in editor
    assert "{once:true}" not in editor


def test_meta_panel_supports_batch_disable_enable_delete_for_all_three_kinds():
    assert "async function setSelectedMetaEventsEnabled(kind,enabled)" in JS
    start = JS.index("function openMetaContextMenu")
    end = JS.index("async function metaContextAction", start)
    menu = JS[start:end]
    assert "disable-selected" in menu
    assert "enable-selected" in menu
    assert "delete-selected" in menu
    assert "setSelectedMetaEventsEnabled(kind,false)" in menu
    assert "setSelectedMetaEventsEnabled(kind,true)" in menu
    assert "deleteSelectedMetaEvents(kind)" in menu
    assert "'lyrics','chords','markers'" in menu


def test_recent_project_frontend_limit_is_15():
    start = JS.index("function rememberRecentProject")
    end = JS.index("function forgetRecentProject", start)
    block = JS[start:end]
    assert ".slice(0,15)" in block


def test_native_recent_projects_dedupe_same_path_and_limit_15(tmp_path, monkeypatch):
    import native.mta_audio_editor_native as native

    monkeypatch.setattr(native, "_data_root", lambda: tmp_path)
    api = native.NativeApi()
    shared = tmp_path / "same.maeprojz"
    shared.write_bytes(b"x")
    api.project_paths["duplicate-a"] = shared
    api.project_paths["duplicate-b"] = shared
    for i in range(20):
        p = tmp_path / f"project-{i}.maeprojz"
        p.write_bytes(b"x")
        api.project_paths[f"p{i}"] = p

    result = api.set_recent_projects(["duplicate-a", "duplicate-b", *[f"p{i}" for i in range(20)]])
    assert result["recent_projects"][:2] == ["duplicate-a", "p0"]
    assert "duplicate-b" not in result["recent_projects"]
    assert len(result["recent_projects"]) == 15

    listed = api.list_recent_projects()["projects"]
    assert len(listed) == 15
    paths = [str(Path(row["path"]).resolve()).casefold() for row in listed]
    assert len(paths) == len(set(paths))
