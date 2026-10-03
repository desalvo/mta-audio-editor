import shutil
import subprocess
import time

import pytest
from fastapi.testclient import TestClient

WRITE = {"X-MTA-Request": "1"}


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="FFmpeg required")
def test_only_first_mp3_import_estimates_and_sets_bpm(tmp_path, monkeypatch):
    import app.main as main
    import app.storage as storage

    monkeypatch.setattr(storage, "ROOT", tmp_path.resolve())
    monkeypatch.setenv("MTA_ALLOW_INSECURE_NO_AUTH", "true")
    with main.MEDIA_JOB_LOCK:
        main.MEDIA_JOBS.clear()

    calls = []
    def fake_bpm(path, progress=None):
        calls.append(path)
        if progress:
            progress(50, "Stima BPM")
            progress(90, "BPM stimati: 128.0")
        return 128.0

    monkeypatch.setattr(main, "estimate_bpm", fake_bpm)

    mp3 = tmp_path / "song.mp3"
    mp3_second = tmp_path / "song2.mp3"
    subprocess.run(
        ["ffmpeg","-y","-v","error","-f","lavfi","-i","sine=frequency=440:duration=0.5",
         "-ar","44100","-ac","2","-b:a","192k",str(mp3)],
        check=True,
    )
    subprocess.run(
        ["ffmpeg","-y","-v","error","-f","lavfi","-i","sine=frequency=660:duration=0.5",
         "-ar","44100","-ac","2","-b:a","192k",str(mp3_second)],
        check=True,
    )

    client = TestClient(main.app, headers=WRITE)
    created = client.post("/api/projects?title=BPM%20Test&target=MTA8").json()
    pid = created["id"]

    def upload(name, source=mp3):
        with source.open("rb") as fh:
            r = client.post(
                f"/api/projects/{pid}/track-import-jobs?name={name}",
                files={"file": (f"{name}.mp3", fh, "audio/mpeg")},
            )
        assert r.status_code == 200
        job_id = r.json()["id"]
        deadline = time.time() + 5
        while time.time() < deadline:
            job = client.get(f"/api/media-jobs/{job_id}").json()
            if job["status"] in {"completed", "failed"}:
                return job
            time.sleep(0.03)
        raise AssertionError("job did not finish")

    first = upload("First")
    assert first["status"] == "completed"
    project = storage.load_project(pid)
    assert project.bpm == 128.0
    assert len(calls) == 1

    second = upload("Second", mp3_second)
    assert second["status"] == "completed"
    project = storage.load_project(pid)
    assert project.bpm == 128.0
    assert len(calls) == 1
    assert len(project.tracks) == 2
