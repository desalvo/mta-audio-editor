from pathlib import Path
import shutil
import subprocess
import time

import pytest
from fastapi.testclient import TestClient

WRITE = {"X-MTA-Request": "1"}


def test_projects_panel_collapsed_and_contextual_split_ui():
    root = Path(__file__).resolve().parents[1]
    html = (root / "app/templates/index.html").read_text(encoding="utf-8")
    js = (root / "app/static/app.js").read_text(encoding="utf-8")
    css = (root / "app/static/app.css").read_text(encoding="utf-8")

    assert 'id="projectsPanel"' in html
    assert 'sidebar-projects collapsed' in html
    assert "toggleProjectsPanel" in js
    assert "openTrackContextMenu" in js
    assert "<span>Separa</span>" in js
    assert "<span>Rimuovi</span>" in js
    assert "/stem-jobs" in js
    assert ".track-context-menu" in css
    assert ".sidebar-projects.collapsed .projects-body" in css
    assert "saveProjectLocal()" in html
    assert "openProjectArchive()" in html


def test_native_api_can_save_and_open_project_archive(tmp_path, monkeypatch):
    import app.storage as storage
    from native.mta_audio_editor_native import NativeApi

    monkeypatch.setattr(storage, "ROOT", (tmp_path / "workspace").resolve())
    storage.ROOT.mkdir(parents=True, exist_ok=True)
    project = storage.create_project("Native Save", "MTA16")

    save_path = tmp_path / "exports" / "chosen"
    save_path.parent.mkdir(parents=True)
    archive_path = Path(str(save_path) + ".mta-project.zip")

    class FakeWindow:
        def __init__(self):
            self.calls = 0

        def create_file_dialog(self, *_args, **_kwargs):
            self.calls += 1
            if self.calls == 1:
                return str(save_path)
            return [str(archive_path)]

    import types, sys
    fake_webview = types.SimpleNamespace(FileDialog=types.SimpleNamespace(SAVE="save", OPEN="open"))
    monkeypatch.setitem(sys.modules, "webview", fake_webview)

    api = NativeApi()
    api.window = FakeWindow()
    saved = api.save_project(project.id, project.title)
    assert saved["ok"] is True
    assert archive_path.is_file()

    opened = api.open_project()
    assert opened["ok"] is True
    assert opened["project"]["target"] == "MTA16"
    assert opened["project"]["id"] != project.id


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="FFmpeg required")
def test_duplicate_track_import_is_rejected(tmp_path, monkeypatch):
    import app.main as main
    import app.storage as storage

    monkeypatch.setattr(storage, "ROOT", tmp_path.resolve())
    monkeypatch.setenv("MTA_ALLOW_INSECURE_NO_AUTH", "true")
    source = tmp_path / "same.mp3"
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "sine=frequency=440:duration=0.3",
         "-ar", "44100", "-ac", "2", "-b:a", "192k", str(source)],
        check=True,
    )
    client = TestClient(main.app, headers=WRITE)
    project = client.post("/api/projects?title=Dedupe&target=MTA8").json()
    pid = project["id"]

    def upload():
        with source.open("rb") as handle:
            return client.post(
                f"/api/projects/{pid}/track-import-jobs?name=Same",
                files={"file": ("same.mp3", handle, "audio/mpeg")},
            )

    first = upload()
    assert first.status_code == 200
    job_id = first.json()["id"]
    deadline = time.time() + 5
    while time.time() < deadline:
        status = client.get(f"/api/media-jobs/{job_id}").json()
        if status["status"] in {"completed", "failed"}:
            break
        time.sleep(0.03)
    assert status["status"] == "completed"

    second = upload()
    assert second.status_code == 409
    assert "già presente" in second.text


def test_batch_file_delete(tmp_path, monkeypatch):
    import app.main as main
    import app.storage as storage

    monkeypatch.setattr(storage, "ROOT", tmp_path.resolve())
    monkeypatch.setenv("MTA_ALLOW_INSECURE_NO_AUTH", "true")
    project = storage.create_project("Files")
    one = storage.original_path(project.id, "one.bin")
    two = storage.original_path(project.id, "two.bin")
    one.write_bytes(b"1")
    two.write_bytes(b"2")

    client = TestClient(main.app, headers=WRITE)
    response = client.post(
        f"/api/projects/{project.id}/files/batch-delete",
        json=[
            {"category": "original", "name": "one.bin"},
            {"category": "original", "name": "two.bin"},
        ],
    )
    assert response.status_code == 200
    assert response.json()["ok"] is True
    assert not one.exists()
    assert not two.exists()


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="FFmpeg required")
def test_contextual_track_stem_job_adds_stems_without_duplicate_source(tmp_path, monkeypatch):
    import app.main as main
    import app.storage as storage
    from app.models import Clip, Track

    monkeypatch.setattr(storage, "ROOT", tmp_path.resolve())
    monkeypatch.setenv("MTA_ALLOW_INSECURE_NO_AUTH", "true")

    source = tmp_path / "track.wav"
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "sine=frequency=220:duration=0.3",
         "-ar", "44100", "-ac", "2", str(source)],
        check=True,
    )
    project = storage.create_project("Context split")
    working = storage.audio_path(project.id, "track.wav")
    shutil.copy2(source, working)
    project.tracks = [
        Track(
            id="t1",
            name="Guitar",
            filename="track.wav",
            duration_ms=300,
            clips=[Clip(id="c1", source_start_ms=0, source_end_ms=300, timeline_start_ms=0)],
        )
    ]
    storage.save_project(project)

    class FakeSplitter:
        @classmethod
        def available(cls):
            return True

        @classmethod
        def status(cls):
            return {"available": True, "models": ["htdemucs_6s"], "recommended_model": "htdemucs_6s"}

        @classmethod
        def split(cls, source, output_dir, model="htdemucs_6s", *, progress=None, cancel_event=None):
            output_dir.mkdir(parents=True, exist_ok=True)
            out = output_dir / "vocals.wav"
            shutil.copy2(source, out)
            return [out]

    monkeypatch.setattr(main, "STEM_SPLITTER", FakeSplitter)
    with main.STEM_JOB_LOCK:
        main.STEM_JOBS.clear()

    client = TestClient(main.app, headers=WRITE)
    response = client.post(f"/api/projects/{project.id}/tracks/t1/stem-jobs?model=htdemucs_6s")
    assert response.status_code == 200
    job_id = response.json()["id"]

    deadline = time.time() + 5
    while time.time() < deadline:
        status = client.get(f"/api/stems/jobs/{job_id}").json()
        if status["status"] in {"completed", "failed", "cancelled"}:
            break
        time.sleep(0.03)
    assert status["status"] == "completed"

    final = storage.load_project(project.id)
    assert [track.name for track in final.tracks] == ["Guitar", "Guitar · Vocals"]
    assert final.tracks[0].filename == "track.wav"
