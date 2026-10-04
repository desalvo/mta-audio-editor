from pathlib import Path

from fastapi.testclient import TestClient

WRITE = {"X-MTA-Request": "1"}


def test_delete_complete_track_route(tmp_path, monkeypatch):
    import app.main as main
    import app.storage as storage
    from app.models import Clip, Track

    monkeypatch.setattr(storage, "ROOT", tmp_path.resolve())
    monkeypatch.setenv("MTA_ALLOW_INSECURE_NO_AUTH", "true")
    project = storage.create_project("Delete tracks")
    audio = storage.audio_path(project.id, "one.wav")
    audio.write_bytes(b"working-audio")
    project.tracks = [
        Track(
            id="t1",
            name="One",
            filename="one.wav",
            duration_ms=1000,
            clips=[Clip(id="c1", source_start_ms=0, source_end_ms=1000, timeline_start_ms=0)],
        )
    ]
    storage.save_project(project)

    client = TestClient(main.app, headers=WRITE)
    response = client.post(f"/api/projects/{project.id}/delete-tracks", json=["t1"])
    assert response.status_code == 200
    assert response.json()["tracks"] == []
    assert len(response.json()["clip_library"]) == 1
    assert audio.exists()


def test_import_audio_starts_on_file_selection_and_delete_tracks_is_not_range_delete():
    root = Path(__file__).resolve().parents[1]
    js = (root / "app/static/app.js").read_text(encoding="utf-8")
    assert 'id="newTrackFile" type="file"' in js
    assert 'onchange="addTrack()"' in js
    assert "/delete-tracks" in js
    assert "if(!wholeSong)" in js
    assert "Seleziona prima un intervallo nella timeline" in js
