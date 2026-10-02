from pathlib import Path
import time

from fastapi.testclient import TestClient

from app.models import Clip, Project, Track
from app.audio_engine import project_time_pitch_filter

WRITE = {"X-MTA-Request": "1"}


def test_project_time_pitch_filter_has_independent_tempo_and_pitch():
    project = Project(id="p", title="P", bpm=120, base_bpm=120, pitch_semitones=0)
    neutral = project_time_pitch_filter(project)
    assert "asetrate=44100.000000" in neutral
    assert "atempo=1.00000000" in neutral

    project.bpm = 90
    slower = project_time_pitch_filter(project)
    assert "atempo=0.75000000" in slower

    project.bpm = 120
    project.pitch_semitones = 6
    shifted = project_time_pitch_filter(project)
    assert "asetrate=" in shifted
    assert "aresample=44100" in shifted
    assert "atempo=" in shifted


def test_project_model_persists_waveform_and_ui_audio_state():
    project = Project(
        id="p",
        title="Persist",
        bpm=100,
        base_bpm=100,
        pitch_semitones=-3,
        track_panel_width_px=340,
        realtime_meter_enabled=True,
        render_preview_enabled=True,
        tracks=[
            Track(
                id="t",
                name="T",
                filename="t.wav",
                duration_ms=1000,
                waveform_peaks=[0.0, 0.5, 1.0],
                waveform_revision="t.wav:123:456",
                clips=[Clip(id="c", source_start_ms=0, source_end_ms=1000, timeline_start_ms=0)],
            )
        ],
    )
    restored = Project.model_validate_json(project.model_dump_json())
    assert restored.track_panel_width_px == 340
    assert restored.pitch_semitones == -3
    assert restored.realtime_meter_enabled is True
    assert restored.render_preview_enabled is True
    assert restored.tracks[0].waveform_peaks == [0.0, 0.5, 1.0]


def test_waveform_job_persists_peaks(tmp_path, monkeypatch):
    import app.main as main
    import app.storage as storage

    monkeypatch.setattr(storage, "ROOT", tmp_path.resolve())
    monkeypatch.setenv("MTA_ALLOW_INSECURE_NO_AUTH", "true")
    monkeypatch.setattr(main, "waveform_peaks", lambda path, points=1024, progress=None: [0.1, 0.8, 0.2])

    project = storage.create_project("Wave")
    audio = storage.audio_path(project.id, "track.wav")
    audio.write_bytes(b"fake")
    project.tracks = [
        Track(
            id="t1",
            name="Track",
            filename="track.wav",
            duration_ms=1000,
            clips=[Clip(id="c1", source_start_ms=0, source_end_ms=1000, timeline_start_ms=0)],
        )
    ]
    storage.save_project(project)

    client = TestClient(main.app, headers=WRITE)
    response = client.post(f"/api/projects/{project.id}/tracks/t1/waveform-jobs")
    assert response.status_code == 200
    job = response.json()
    deadline = time.time() + 3
    while job["status"] not in {"completed", "failed"} and time.time() < deadline:
        time.sleep(0.02)
        job = client.get(f"/api/media-jobs/{job['id']}").json()
    assert job["status"] == "completed"

    saved = storage.load_project(project.id)
    assert saved.tracks[0].waveform_peaks == [0.1, 0.8, 0.2]
    assert saved.tracks[0].waveform_revision


def test_ui_has_synced_tracks_waveforms_meters_render_tempo_pitch_and_double_delete_confirmation():
    root = Path(__file__).resolve().parents[1]
    js = (root / "app/static/app.js").read_text(encoding="utf-8")
    css = (root / "app/static/app.css").read_text(encoding="utf-8")
    html = (root / "app/templates/index.html").read_text(encoding="utf-8")

    assert "bindTrackTimelineScroll" in js
    assert "trackResizer" in js
    assert "track_panel_width_px" in js
    assert "waveform-jobs" in js
    assert "waveform-progress" in css
    assert "captureUiState" in js and "restoreUiState" in js
    assert "data-mute-track" in js and "data-solo-track" in js
    assert "meter-realtime" in js
    assert "toggleRealtimeMeters" in js
    assert "toggleRenderPreview" in js
    assert 'id="renderBtn"' in html
    assert 'id="transportBpmInput"' in html
    assert 'id="transportPitchInput"' in html
    assert js.count("confirm(`") >= 3
    assert "Sei sicuro di voler eliminare il progetto" in js
    assert "Questa operazione è irreversibile" in js


def test_project_delete_removes_entire_workspace(tmp_path, monkeypatch):
    import app.main as main
    import app.storage as storage

    monkeypatch.setattr(storage, "ROOT", tmp_path.resolve())
    monkeypatch.setenv("MTA_ALLOW_INSECURE_NO_AUTH", "true")
    project = storage.create_project("Delete all")
    (storage.pdir(project.id) / "audio" / "a.wav").write_bytes(b"a")
    (storage.pdir(project.id) / "attachments" / "meta.bin").write_bytes(b"b")
    (storage.pdir(project.id) / "originals" / "source.mp3").write_bytes(b"c")
    project_dir = storage.pdir(project.id)

    client = TestClient(main.app, headers=WRITE)
    response = client.delete(f"/api/projects/{project.id}")
    assert response.status_code == 200
    assert not project_dir.exists()
