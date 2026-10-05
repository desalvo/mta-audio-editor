from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_native_recent_projects_are_persisted_outside_webview_local_storage(tmp_path, monkeypatch):
    import native.mta_audio_editor_native as native

    monkeypatch.setattr(native, "_data_root", lambda: tmp_path)
    api = native.NativeApi()
    result = api.set_recent_projects(["p2", "p1", "p2"])
    assert result["recent_projects"] == ["p2", "p1"]

    # A fresh bridge instance must recover them on the next native launch.
    again = native.NativeApi()
    settings = again.get_native_settings()
    assert settings["recent_projects"] == ["p2", "p1"]

    # Saving unrelated settings must preserve the recent-project list.
    again.set_native_settings(1024, True, "stable")
    assert native.NativeApi().get_native_settings()["recent_projects"] == ["p2", "p1"]


def test_native_recent_ui_uses_bridge_persistence():
    js = (ROOT / "app/static/app.js").read_text(encoding="utf-8")
    assert "nativeRecentProjects" in js
    assert "cfg.recent_projects" in js
    assert "bridge.set_recent_projects(nativeRecentProjects)" in js
    assert "if(currentUser?.native_single_user)return [...nativeRecentProjects]" in js


def test_lyrics_and_chords_are_synced_to_bound_native_archive_after_extraction():
    js = (ROOT / "app/static/app.js").read_text(encoding="utf-8")
    start = js.index("async function startTrackTextAnalysis")
    end = js.index("\nfunction openTrackStemWorkflow", start)
    block = js[start:end]
    assert "await flushAutosave()" in block
    assert "current=await api(`/api/projects/${current.id}`)" in block
    assert "await persistCurrentProject(false)" in block
    assert "await syncNativeProjectFile(current.id)" in block


def test_timed_text_round_trips_through_project_json(tmp_path, monkeypatch):
    import app.storage as storage
    from app.models import Chord, LyricLine

    monkeypatch.setattr(storage, "ROOT", (tmp_path / "workspace").resolve())
    storage.ROOT.mkdir(parents=True, exist_ok=True)
    project = storage.create_project("Timed text persistence", "DAW")
    project.lyrics = [LyricLine(time_ms=1000, end_ms=2200, text="hello world")]
    project.chords = [Chord(time_ms=900, chord="C:maj"), Chord(time_ms=2100, chord="G:maj")]
    project.lyrics_engine = "OpenAI Whisper"
    project.lyrics_model = "base"
    project.chords_engine = "madmom-deep-chroma"
    project.chords_model = "madmom-deep-chroma"
    storage.save_project(project)

    loaded = storage.load_project(project.id)
    assert [x.text for x in loaded.lyrics] == ["hello world"]
    assert [x.chord for x in loaded.chords] == ["C:maj", "G:maj"]
    assert loaded.lyrics_model == "base"
    assert loaded.chords_engine == "madmom-deep-chroma"


def test_native_lyrics_pdf_preview_has_persistent_return_control():
    js = (ROOT / "app/static/app.js").read_text(encoding="utf-8")
    css = (ROOT / "app/static/app.css").read_text(encoding="utf-8")
    start = js.index("function previewProjectLyricsPdf")
    end = js.index("async function resetTimedData", start)
    block = js[start:end]
    assert "closeLyricsPdfPreview()" in block
    assert "← Torna all'editor" in block
    assert "pdf-preview-toolbar" in block
    assert "forceNativeViewportTop()" in block
    assert ".pdf-preview-toolbar{position:sticky;top:0" in css
