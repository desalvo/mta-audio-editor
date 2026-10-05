import shutil
import subprocess
import time

import pytest
from fastapi.testclient import TestClient

WRITE = {"X-MTA-Request": "1"}


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="FFmpeg required")
def test_async_stem_workflow_persists_project_and_progress(tmp_path, monkeypatch):
    import app.main as main
    import app.storage as storage

    monkeypatch.setattr(storage, "ROOT", tmp_path.resolve())
    monkeypatch.setenv("MTA_ALLOW_INSECURE_NO_AUTH", "true")

    source = tmp_path / "song.mp3"
    subprocess.run(
        [
            "ffmpeg", "-y", "-v", "error", "-f", "lavfi",
            "-i", "sine=frequency=440:duration=0.4",
            "-ar", "44100", "-ac", "2", "-b:a", "192k", str(source),
        ],
        check=True,
    )

    class FakeSplitter:
        @classmethod
        def available(cls):
            return True

        @classmethod
        def status(cls):
            return {
                "available": True,
                "models": ["htdemucs_6s"],
                "recommended_model": "htdemucs_6s",
            }

        @classmethod
        def split(cls, source, output_dir, model="htdemucs_6s", *, stem_count=0, progress=None, cancel_event=None):
            output_dir.mkdir(parents=True, exist_ok=True)
            if progress:
                progress(35, "analysing")
                progress(75, "separating")
            paths = []
            for name in ("vocals", "drums", "bass", "other"):
                out = output_dir / f"{name}.wav"
                subprocess.run(
                    [
                        "ffmpeg", "-y", "-v", "error", "-i", str(source),
                        "-ar", "44100", "-ac", "2", str(out),
                    ],
                    check=True,
                )
                paths.append(out)
            return paths

    monkeypatch.setattr(main, "STEM_SPLITTER", FakeSplitter)
    with main.STEM_JOB_LOCK:
        main.STEM_JOBS.clear()

    client = TestClient(main.app, headers=WRITE)
    with source.open("rb") as fh:
        response = client.post(
            "/api/stems/jobs?project_title=Persisted%20Song&target=MTA8&model=htdemucs_6s&keep_original_track=true",
            files={"file": ("song.mp3", fh, "audio/mpeg")},
        )
    assert response.status_code == 200
    payload = response.json()
    pid = payload["project"]["id"]
    job_id = payload["job"]["id"]

    # The project and original mix are committed before background work completes.
    persisted = storage.load_project(pid)
    assert persisted.title == "Persisted Song"
    assert any(track.name == "Original Mix" for track in persisted.tracks)
    assert any(item["name"].startswith("song") for item in storage.project_files(pid) if item["category"] == "original")

    deadline = time.time() + 10
    status = None
    while time.time() < deadline:
        r = client.get(f"/api/stems/jobs/{job_id}")
        assert r.status_code == 200
        status = r.json()
        if status["status"] in {"completed", "failed", "cancelled"}:
            break
        time.sleep(0.05)

    assert status is not None
    assert status["status"] == "completed"
    assert status["progress"] == 100

    final = storage.load_project(pid)
    names = {track.name for track in final.tracks}
    assert {"Original Mix", "Vocals", "Drums", "Bass", "Other"} <= names


def test_mobile_ui_exposes_persistent_project_and_stem_workflow():
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    html = (root / "app/templates/index.html").read_text(encoding="utf-8")
    js = (root / "app/static/app.js").read_text(encoding="utf-8")
    css = (root / "app/static/app.css").read_text(encoding="utf-8")

    assert "Import &amp; Separate" in html
    assert "Save project locally" in html
    assert "Delete project" in html
    assert "function openStemWorkflow()" in js
    assert "function pollStemJob(" in js
    assert "function cancelStemJob(" in js
    assert "function markDirty(" in js
    assert "flushAutosave" in js
    assert "stem-progress-fill" in css
    assert "project-row" in css


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="FFmpeg required")
def test_async_stem_workflow_can_be_cancelled(tmp_path, monkeypatch):
    import app.main as main
    import app.storage as storage

    monkeypatch.setattr(storage, "ROOT", tmp_path.resolve())
    monkeypatch.setenv("MTA_ALLOW_INSECURE_NO_AUTH", "true")

    source = tmp_path / "song.mp3"
    subprocess.run(
        [
            "ffmpeg", "-y", "-v", "error", "-f", "lavfi",
            "-i", "sine=frequency=330:duration=0.4",
            "-ar", "44100", "-ac", "2", "-b:a", "192k", str(source),
        ],
        check=True,
    )

    class SlowSplitter:
        @classmethod
        def available(cls):
            return True

        @classmethod
        def status(cls):
            return {"available": True, "models": ["htdemucs_6s"], "recommended_model": "htdemucs_6s"}

        @classmethod
        def split(cls, source, output_dir, model="htdemucs_6s", *, stem_count=0, progress=None, cancel_event=None):
            for i in range(100):
                if cancel_event is not None and cancel_event.is_set():
                    raise RuntimeError("stem separation cancelled")
                if progress:
                    progress(20 + min(60, i), "working")
                time.sleep(0.01)
            raise RuntimeError("test should have cancelled")

    monkeypatch.setattr(main, "STEM_SPLITTER", SlowSplitter)
    with main.STEM_JOB_LOCK:
        main.STEM_JOBS.clear()

    client = TestClient(main.app, headers=WRITE)
    with source.open("rb") as fh:
        response = client.post(
            "/api/stems/jobs?project_title=Cancelled%20Song&model=htdemucs_6s",
            files={"file": ("song.mp3", fh, "audio/mpeg")},
        )
    assert response.status_code == 200
    payload = response.json()
    pid = payload["project"]["id"]
    job_id = payload["job"]["id"]

    cancel = client.post(f"/api/stems/jobs/{job_id}/cancel")
    assert cancel.status_code == 200

    deadline = time.time() + 5
    status = None
    while time.time() < deadline:
        status = client.get(f"/api/stems/jobs/{job_id}").json()
        if status["status"] == "cancelled":
            break
        time.sleep(0.03)

    assert status["status"] == "cancelled"
    project = storage.load_project(pid)
    assert [track.name for track in project.tracks] == ["Original Mix"]
