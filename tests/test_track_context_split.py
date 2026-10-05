import shutil
import subprocess
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

WRITE = {"X-MTA-Request": "1"}


def test_track_context_menu_exposes_separate_action():
    root = Path(__file__).resolve().parents[1]
    js = (root / "app/static/app.js").read_text(encoding="utf-8")
    css = (root / "app/static/app.css").read_text(encoding="utf-8")

    assert "openTrackContextMenu(event" in js
    assert "openTrackStemWorkflow(" in js
    assert "startTrackStemSplit(" in js
    assert "new URLSearchParams({model,stem_count:String(stemCount)" in js
    assert "Avvia separazione" in js
    assert "<span>Separa</span>" in js
    assert ".track-context-menu" in css


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="FFmpeg required")
def test_existing_track_can_start_stem_job_and_original_track_is_kept(tmp_path, monkeypatch):
    import app.main as main
    import app.storage as storage
    from app.models import Clip, Track

    monkeypatch.setattr(storage, "ROOT", tmp_path.resolve())
    monkeypatch.setenv("MTA_ALLOW_INSECURE_NO_AUTH", "true")

    project = storage.create_project("Context split")
    source = storage.audio_path(project.id, "track.wav")
    subprocess.run(
        [
            "ffmpeg", "-y", "-v", "error", "-f", "lavfi",
            "-i", "sine=frequency=440:duration=0.4",
            "-ar", "44100", "-ac", "2", str(source),
        ],
        check=True,
    )
    project.tracks = [
        Track(
            id="track1",
            name="Piano Guide",
            filename="track.wav",
            duration_ms=400,
            channels=2,
            channel_layout="stereo",
            clips=[Clip(id="clip1", source_start_ms=0, source_end_ms=400, timeline_start_ms=0)],
        )
    ]
    storage.save_project(project)

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
            result = []
            for name in ("vocals", "other"):
                out = output_dir / f"{name}.wav"
                subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(source), str(out)], check=True)
                result.append(out)
            return result

    monkeypatch.setattr(main, "STEM_SPLITTER", FakeSplitter)
    with main.STEM_JOB_LOCK:
        main.STEM_JOBS.clear()

    client = TestClient(main.app, headers=WRITE)
    response = client.post(
        f"/api/projects/{project.id}/tracks/track1/stem-jobs?model=htdemucs_6s"
    )
    assert response.status_code == 200, response.text
    job = response.json()
    assert job["source_track_id"] == "track1"
    assert job["filename"] == "Piano Guide"

    deadline = time.time() + 8
    while time.time() < deadline:
        job = client.get(f"/api/stems/jobs/{job['id']}").json()
        if job["status"] in {"completed", "failed", "cancelled"}:
            break
        time.sleep(0.05)

    assert job["status"] == "completed", job
    saved = storage.load_project(project.id)
    names = [track.name for track in saved.tracks]
    assert names[0] == "Piano Guide"
    assert "Piano Guide · Vocals" in names
    assert "Piano Guide · Other" in names
    assert source.exists()
