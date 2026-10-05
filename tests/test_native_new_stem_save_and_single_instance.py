from pathlib import Path
import sys
import types


def test_native_stem_new_project_asks_for_save_path_before_starting_job():
    root = Path(__file__).resolve().parents[1]
    js = (root / "app/static/app.js").read_text(encoding="utf-8")

    start = js.index("async function startStemWorkflow")
    end = js.index("function showStemProgress", start)
    block = js[start:end]

    choose = block.index("choose_project_save_path")
    request = block.index("/api/stems/jobs?")
    bind = block.index("bind_project_path")
    assert choose < request < bind
    assert "if(!chosen?.ok)return" in block
    assert "mode==='new'" in block


def test_native_external_project_file_is_resynced_after_autosave_and_stem_completion():
    root = Path(__file__).resolve().parents[1]
    js = (root / "app/static/app.js").read_text(encoding="utf-8")

    assert "async function syncNativeProjectFile(projectId)" in js
    assert "await syncNativeProjectFile(saved.id)" in js
    assert "await syncNativeProjectFile(current.id)" in js
    assert "await syncNativeProjectFile(job.project_id)" in js


def test_frozen_launcher_calls_multiprocessing_freeze_support_before_main():
    root = Path(__file__).resolve().parents[1]
    launcher = (root / "native/mta_audio_editor_native.py").read_text(encoding="utf-8")

    guard = launcher.index('if __name__ == "__main__":')
    freeze = launcher.index("multiprocessing.freeze_support()", guard)
    main = launcher.index("raise SystemExit(main())", guard)
    assert freeze < main


def test_native_api_choose_bind_and_sync_project(tmp_path, monkeypatch):
    import app.storage as storage
    from native.mta_audio_editor_native import NativeApi

    monkeypatch.setattr(storage, "ROOT", (tmp_path / "workspace").resolve())
    storage.ROOT.mkdir(parents=True, exist_ok=True)
    project = storage.create_project("Stem destination", "MTA16")

    target = tmp_path / "exports" / "stem-project"
    target.parent.mkdir(parents=True)

    fake_webview = types.SimpleNamespace(FileDialog=types.SimpleNamespace(SAVE="save", OPEN="open"))
    monkeypatch.setitem(sys.modules, "webview", fake_webview)

    class FakeWindow:
        def create_file_dialog(self, *_args, **_kwargs):
            return str(target)

    api = NativeApi()
    api.window = FakeWindow()

    chosen = api.choose_project_save_path(project.title)
    assert chosen["ok"] is True
    assert chosen["path"].endswith(".maeproj")

    bound = api.bind_project_path(project.id, chosen["path"])
    assert bound["ok"] is True
    archive = Path(bound["path"])
    assert archive.is_file()

    before = archive.stat().st_mtime_ns
    loaded = storage.load_project(project.id)
    loaded.title = "Updated title"
    storage.save_project(loaded)

    synced = api.sync_project(project.id)
    assert synced["ok"] is True
    assert synced["bound"] is True
    assert archive.stat().st_mtime_ns >= before
