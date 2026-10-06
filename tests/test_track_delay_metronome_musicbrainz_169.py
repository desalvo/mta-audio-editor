from pathlib import Path

from fastapi.testclient import TestClient

from app.models import Clip, Project, Track


def test_musicbrainz_user_agent_uses_release(monkeypatch):
    import app.rights_registry as rr

    captured = {}

    class DummyResponse:
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return False
        def read(self, _limit):
            return b'{}'

    def fake_urlopen(req, timeout=20):
        captured["ua"] = req.headers.get("User-agent")
        return DummyResponse()

    monkeypatch.setattr(rr, "urlopen", fake_urlopen)
    rr._read_json("https://musicbrainz.org/ws/2/recording/", {"fmt": "json"})
    assert rr.APP_RELEASE in captured["ua"]


def test_track_delay_is_persistent_and_non_destructive(tmp_path, monkeypatch):
    import app.main as main
    import app.storage as storage

    monkeypatch.setattr(storage, "ROOT", tmp_path.resolve())
    monkeypatch.setenv("MTA_ALLOW_INSECURE_NO_AUTH", "true")
    client = TestClient(main.app, headers={"X-MTA-Request": "1"})
    project = storage.create_project("Delay")
    project.tracks = [Track(id="t1", name="Track", filename="x.wav", duration_ms=1000,
                            clips=[Clip(id="c1", source_start_ms=0, source_end_ms=1000, timeline_start_ms=250)])]
    storage.save_project(project)
    response = client.post(f"/api/projects/{project.id}/tracks/t1/delay", json={"delay_ms": -125})
    assert response.status_code == 200
    saved = storage.load_project(project.id)
    assert saved.tracks[0].delay_ms == -125
    assert saved.tracks[0].clips[0].timeline_start_ms == 250


def test_sync_metronome_sets_delay_on_click_track(tmp_path, monkeypatch):
    import app.main as main
    import app.storage as storage

    monkeypatch.setattr(storage, "ROOT", tmp_path.resolve())
    monkeypatch.setenv("MTA_ALLOW_INSECURE_NO_AUTH", "true")
    client = TestClient(main.app, headers={"X-MTA-Request": "1"})
    project = storage.create_project("Sync")
    project.tracks = [
        Track(id="ref", name="Song", filename="song.wav", duration_ms=1000,
              clips=[Clip(id="r", source_start_ms=0, source_end_ms=1000, timeline_start_ms=0)]),
        Track(id="metro", name="Metronomo", type="click", filename="metro.wav", duration_ms=1000,
              clips=[Clip(id="m", source_start_ms=0, source_end_ms=1000, timeline_start_ms=0)]),
    ]
    storage.save_project(project)
    monkeypatch.setattr(main, "auto_align_ms", lambda _a, _b: 187)
    response = client.post(f"/api/projects/{project.id}/tracks/ref/sync-metronome")
    assert response.status_code == 200
    assert response.json()["delta_ms"] == 187
    saved = storage.load_project(project.id)
    metro = next(t for t in saved.tracks if t.id == "metro")
    assert metro.delay_ms == 187


def test_ui_exposes_metronome_sync_and_signed_delay_controls():
    js = Path("app/static/app.js").read_text(encoding="utf-8")
    assert "Sincronizza metronomo" in js
    assert "Delay / anticipo traccia" in js
    assert "delayMsFromUnit" in js
    assert "quarters" in js and "bars" in js
    assert "track.delay_ms" not in js or "delay_ms" in js
