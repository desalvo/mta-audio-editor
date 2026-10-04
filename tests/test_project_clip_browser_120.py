from pathlib import Path

from fastapi.testclient import TestClient

WRITE = {"X-MTA-Request": "1"}


def _seed(tmp_path, monkeypatch):
    import app.main as main
    import app.storage as storage
    from app.models import Clip, Track

    monkeypatch.setattr(storage, "ROOT", tmp_path.resolve())
    monkeypatch.setenv("MTA_ALLOW_INSECURE_NO_AUTH", "true")
    project = storage.create_project("Clip browser")
    audio = storage.audio_path(project.id, "source.wav")
    audio.write_bytes(b"audio")
    project.tracks = [Track(
        id="track1", name="Original track", type="guitars", filename="source.wav",
        duration_ms=1200, channels=2, channel_layout="stereo",
        clips=[Clip(id="c1", source_start_ms=0, source_end_ms=1200, timeline_start_ms=0)],
    )]
    storage.save_project(project)
    return main, storage, project


def test_clip_rename_uses_stable_asset_id_and_does_not_rename_track(tmp_path, monkeypatch):
    main, storage, project = _seed(tmp_path, monkeypatch)
    client = TestClient(main.app, headers=WRITE)
    loaded = client.get(f"/api/projects/{project.id}").json()
    clip_id = loaded["clip_library"][0]["id"]
    assert loaded["tracks"][0]["source_clip_id"] == clip_id

    response = client.patch(
        f"/api/projects/{project.id}/clip-library/{clip_id}",
        json={"name": "My renamed library clip"},
    )
    assert response.status_code == 200
    data = response.json()["project"]
    assert data["clip_library"][0]["name"] == "My renamed library clip"
    assert data["tracks"][0]["name"] == "Original track"
    assert data["tracks"][0]["source_clip_id"] == clip_id

    monkeypatch.setattr(main, "waveform_peaks", lambda *_a, **_k: [0.1])
    created = client.post(
        f"/api/projects/{project.id}/clip-library/{clip_id}/instantiate",
        json={"timeline_start_ms": 500},
    )
    assert created.status_code == 200
    track = created.json()["track"]
    assert track["source_clip_id"] == clip_id
    assert track["name"] == "My renamed library clip"


def test_old_tracks_are_migrated_to_stable_source_clip_id(tmp_path, monkeypatch):
    main, storage, project = _seed(tmp_path, monkeypatch)
    assert storage.load_project(project.id).tracks[0].source_clip_id is None
    client = TestClient(main.app, headers=WRITE)
    data = client.get(f"/api/projects/{project.id}").json()
    assert data["tracks"][0]["source_clip_id"] == data["clip_library"][0]["id"]


def test_clip_browser_has_preview_search_and_ten_item_pagination():
    root = Path(__file__).resolve().parents[1]
    js = (root / "app/static/app.js").read_text(encoding="utf-8")
    css = (root / "app/static/app.css").read_text(encoding="utf-8")
    assert "CLIP_BROWSER_PAGE_SIZE=10" in js
    assert "Cerca clip per nome" in js
    assert "renameProjectClip" in js
    assert "previewProjectClip" in js
    assert "/audio/${encodeURIComponent(asset.filename)}" in js
    assert "method:'PATCH'" in js
    assert ".clip-browser-search" in css
    assert ".clip-preview-btn" in css
