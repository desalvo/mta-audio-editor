from pathlib import Path

from fastapi.testclient import TestClient

WRITE = {"X-MTA-Request": "1"}


def _seed_project(tmp_path, monkeypatch):
    import app.main as main
    import app.storage as storage
    from app.models import Clip, Track

    monkeypatch.setattr(storage, "ROOT", tmp_path.resolve())
    monkeypatch.setenv("MTA_ALLOW_INSECURE_NO_AUTH", "true")
    project = storage.create_project("Clip library")
    audio = storage.audio_path(project.id, "source.wav")
    audio.write_bytes(b"shared-working-audio")
    project.tracks = [
        Track(
            id="track1",
            name="Reusable guitar",
            type="guitars",
            filename="source.wav",
            duration_ms=2400,
            channels=2,
            channel_layout="stereo",
            clips=[Clip(id="clip1", source_start_ms=0, source_end_ms=2400, timeline_start_ms=0)],
        )
    ]
    storage.save_project(project)
    return main, storage, project, audio


def test_existing_tracks_are_backfilled_into_project_clip_library(tmp_path, monkeypatch):
    main, storage, project, _audio = _seed_project(tmp_path, monkeypatch)
    client = TestClient(main.app, headers=WRITE)
    data = client.get(f"/api/projects/{project.id}").json()
    assert len(data["clip_library"]) == 1
    asset = data["clip_library"][0]
    assert asset["name"] == "Reusable guitar"
    assert asset["filename"] == "source.wav"
    assert asset["duration_ms"] == 2400
    assert storage.load_project(project.id).clip_library[0].filename == "source.wav"


def test_same_library_clip_can_create_multiple_timeline_tracks_without_copying_audio(tmp_path, monkeypatch):
    main, storage, project, audio = _seed_project(tmp_path, monkeypatch)
    monkeypatch.setattr(main, "waveform_peaks", lambda *_args, **_kwargs: [0.1, 0.2])
    client = TestClient(main.app, headers=WRITE)
    loaded = client.get(f"/api/projects/{project.id}").json()
    clip_id = loaded["clip_library"][0]["id"]

    first = client.post(
        f"/api/projects/{project.id}/clip-library/{clip_id}/instantiate",
        json={"timeline_start_ms": 1500},
    )
    second = client.post(
        f"/api/projects/{project.id}/clip-library/{clip_id}/instantiate",
        json={"timeline_start_ms": 4200},
    )
    assert first.status_code == 200
    assert second.status_code == 200
    data = second.json()["project"]
    assert len(data["tracks"]) == 3
    assert len(data["clip_library"]) == 1
    assert {track["filename"] for track in data["tracks"]} == {"source.wav"}
    assert data["tracks"][-2]["clips"][0]["timeline_start_ms"] == 1500
    assert data["tracks"][-1]["clips"][0]["timeline_start_ms"] == 4200
    assert audio.exists()

    ids = [track["id"] for track in data["tracks"]]
    deleted = client.post(f"/api/projects/{project.id}/delete-tracks", json=ids)
    assert deleted.status_code == 200
    assert deleted.json()["tracks"] == []
    assert len(deleted.json()["clip_library"]) == 1
    assert audio.exists(), "library asset must survive after all timeline instances are removed"


def test_web_ui_has_drag_drop_project_clip_browser():
    root = Path(__file__).resolve().parents[1]
    js = (root / "app/static/app.js").read_text(encoding="utf-8")
    css = (root / "app/static/app.css").read_text(encoding="utf-8")
    assert "CLIP DEL PROGETTO" in js
    assert "beginProjectClipDrag" in js
    assert "beginProjectClipPointer" in js
    assert "bindProjectClipDrop" in js
    assert "/clip-library/${encodeURIComponent(id)}/instantiate" in js
    assert "timelineMsFromClientX" in js
    assert ".project-clip-card" in css
    assert ".clip-touch-ghost" in css
