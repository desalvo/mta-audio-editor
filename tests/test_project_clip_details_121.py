from pathlib import Path

from fastapi.testclient import TestClient

WRITE = {"X-MTA-Request": "1"}


def _seed(tmp_path, monkeypatch):
    import app.main as main
    import app.storage as storage
    from app.models import Clip, Track

    monkeypatch.setattr(storage, "ROOT", tmp_path.resolve())
    monkeypatch.setenv("MTA_ALLOW_INSECURE_NO_AUTH", "true")
    monkeypatch.setattr(
        main,
        "ffprobe",
        lambda _path: {
            "streams": [{
                "codec_type": "audio",
                "codec_name": "flac",
                "channels": 2,
                "channel_layout": "stereo",
                "bit_rate": "921600",
                "tags": {"ARTIST": "Example Artist", "TITLE": "Embedded title"},
            }],
            "format": {
                "format_name": "flac",
                "bit_rate": "921600",
                "tags": {"ALBUM": "Example Album"},
            },
        },
    )
    project = storage.create_project("Clip details")
    audio = storage.audio_path(project.id, "source.flac")
    payload = b"x" * 12345
    audio.write_bytes(payload)
    project.tracks = [Track(
        id="track1", name="Library source", type="guitars", filename="source.flac",
        duration_ms=3_723_000, channels=2, channel_layout="stereo",
        clips=[Clip(id="c1", source_start_ms=0, source_end_ms=3_723_000, timeline_start_ms=0)],
    )]
    storage.save_project(project)
    return main, storage, project, len(payload)


def test_project_clip_metadata_is_scanned_and_persisted(tmp_path, monkeypatch):
    main, storage, project, size = _seed(tmp_path, monkeypatch)
    client = TestClient(main.app, headers=WRITE)
    data = client.get(f"/api/projects/{project.id}").json()
    asset = data["clip_library"][0]

    assert asset["type"] == "guitars"
    assert asset["format"] == "FLAC / flac"
    assert asset["bitrate_bps"] == 921600
    assert asset["size_bytes"] == size
    assert asset["current_location"] == "audio/source.flac"
    assert asset["embedded_metadata"]["audio.ARTIST"] == "Example Artist"
    assert asset["embedded_metadata"]["format.ALBUM"] == "Example Album"
    assert asset["metadata_scanned"] is True

    persisted = storage.load_project(project.id).clip_library[0]
    assert persisted.size_bytes == size
    assert persisted.format == "FLAC / flac"


def test_clip_notes_are_editable_without_changing_track_association(tmp_path, monkeypatch):
    main, _storage, project, _size = _seed(tmp_path, monkeypatch)
    client = TestClient(main.app, headers=WRITE)
    loaded = client.get(f"/api/projects/{project.id}").json()
    clip_id = loaded["clip_library"][0]["id"]
    track_id = loaded["tracks"][0]["id"]

    response = client.patch(
        f"/api/projects/{project.id}/clip-library/{clip_id}",
        json={"notes": "Chorus take, use only after bar 16"},
    )
    assert response.status_code == 200
    data = response.json()["project"]
    assert data["clip_library"][0]["notes"] == "Chorus take, use only after bar 16"
    assert data["tracks"][0]["id"] == track_id
    assert data["tracks"][0]["source_clip_id"] == clip_id


def test_clip_browser_renders_collapsible_technical_details_and_editable_notes():
    root = Path(__file__).resolve().parents[1]
    js = (root / "app/static/app.js").read_text(encoding="utf-8")
    css = (root / "app/static/app.css").read_text(encoding="utf-8")

    assert "expandedProjectClipDetails" in js
    assert "toggleProjectClipDetails" in js
    assert "Tipo clip" in js
    assert "Formato" in js
    assert "Bitrate" in js
    assert "Durata" in js
    assert "Dimensione" in js
    assert "Provenienza" in js
    assert "Locazione attuale" in js
    assert "Metadati clip" in js
    assert "saveProjectClipNotes" in js
    assert "clipDurationHms" in js
    assert ".project-clip-details" in css
    assert ".clip-notes-field" in css
