import time
import wave
from pathlib import Path

import numpy as np
from fastapi.testclient import TestClient

WRITE = {"X-MTA-Request": "1"}


def _pcm_peak(path: Path) -> int:
    with wave.open(str(path), "rb") as handle:
        raw = handle.readframes(handle.getnframes())
    return int(np.max(np.abs(np.frombuffer(raw, dtype=np.int16).astype(np.int32))))


def _audio_project():
    from app.models import Chord, Clip, Project, Track

    return Project(
        id="a" * 12,
        title="Normalized guides",
        bpm=120,
        tracks=[
            Track(
                id="music",
                name="Music",
                filename="music.wav",
                duration_ms=2000,
                clips=[Clip(id="clip", source_start_ms=0, source_end_ms=2000, timeline_start_ms=0)],
            )
        ],
        chords=[Chord(time_ms=0, chord="Cmaj7"), Chord(time_ms=1000, chord="G7/B")],
    )


def test_generated_metronome_and_chords_are_peak_normalized_to_zero_dbfs(tmp_path):
    from app.audio_engine import generate_chords_piano_wav, generate_metronome_wav

    project = _audio_project()
    met = tmp_path / "met.wav"
    chords = tmp_path / "chords.wav"
    generate_metronome_wav(project, met)
    generate_chords_piano_wav(project, chords)
    assert _pcm_peak(met) == 32767
    assert _pcm_peak(chords) == 32767


def test_generated_tracks_are_created_with_zero_db_faders(tmp_path, monkeypatch):
    import app.main as main
    import app.storage as storage
    from app.models import Chord, Clip, Track

    monkeypatch.setattr(storage, "ROOT", tmp_path.resolve())
    monkeypatch.setenv("MTA_ALLOW_INSECURE_NO_AUTH", "true")
    project = storage.create_project("Guide tracks")
    source = storage.audio_path(project.id, "music.wav")
    # Minimal valid wav for duration-bearing project source.
    with wave.open(str(source), "wb") as h:
        h.setnchannels(1); h.setsampwidth(2); h.setframerate(44100); h.writeframes(b"\0\0" * 44100)
    project.tracks = [Track(id="music", name="Music", filename="music.wav", duration_ms=1000,
                            clips=[Clip(id="c", source_start_ms=0, source_end_ms=1000, timeline_start_ms=0)])]
    project.chords = [Chord(time_ms=0, chord="C")]
    storage.save_project(project)
    client = TestClient(main.app, headers=WRITE)
    met = client.post(f"/api/projects/{project.id}/metronome-track")
    assert met.status_code == 200
    assert met.json()["track"]["volume_db"] == 0.0
    chords = client.post(f"/api/projects/{project.id}/chords-track")
    assert chords.status_code == 200
    assert chords.json()["track"]["volume_db"] == 0.0


def test_generated_track_delete_is_logical_then_gc_removes_file_and_asset(tmp_path, monkeypatch):
    import app.main as main
    import app.storage as storage
    from app.models import Clip, ProjectClip, Track

    monkeypatch.setattr(storage, "ROOT", tmp_path.resolve())
    monkeypatch.setenv("MTA_ALLOW_INSECURE_NO_AUTH", "true")
    project = storage.create_project("GC")
    audio = storage.audio_path(project.id, "metronome-old.wav")
    audio.write_bytes(b"generated")
    asset = ProjectClip(id="asset1", name="Metronomo", filename=audio.name, duration_ms=1000, type="click")
    project.clip_library = [asset]
    project.tracks = [Track(id="met1", name="Metronomo 120 BPM", type="click", filename=audio.name,
                            source_clip_id=asset.id, duration_ms=1000,
                            clips=[Clip(id="c1", source_start_ms=0, source_end_ms=1000, timeline_start_ms=0)])]
    storage.save_project(project)
    client = TestClient(main.app, headers=WRITE)
    response = client.post(f"/api/projects/{project.id}/delete-tracks", json=["met1"])
    assert response.status_code == 200
    assert response.json()["tracks"] == []
    assert response.json()["clip_library"] == []
    # Logical state is authoritative immediately, before physical cleanup matters.
    assert storage.load_project(project.id).tracks == []
    deadline = time.time() + 2.0
    journal = storage.pdir(project.id) / storage.GC_QUEUE_NAME
    # The GC worker unlinks audio before durably clearing its journal. Wait
    # for both postconditions instead of racing the final journal fsync.
    while (audio.exists() or journal.exists()) and time.time() < deadline:
        time.sleep(0.02)
    assert not audio.exists()
    assert not journal.exists()


def test_gc_resume_reconciles_orphan_after_crash_gap(tmp_path, monkeypatch):
    import app.storage as storage

    monkeypatch.setattr(storage, "ROOT", tmp_path.resolve())
    project = storage.create_project("Resume GC")
    orphan = storage.audio_path(project.id, "orphan.wav")
    orphan.write_bytes(b"orphan")
    # Simulate a crash after project.json stopped referencing a file but before a GC journal was written.
    storage.schedule_project_gc(project.id, reconcile_orphans=True)
    deadline = time.time() + 2.0
    while orphan.exists() and time.time() < deadline:
        time.sleep(0.02)
    assert not orphan.exists()


def test_project_archive_excludes_pending_gc_journal_and_files(tmp_path, monkeypatch):
    import zipfile
    import app.storage as storage

    monkeypatch.setattr(storage, "ROOT", tmp_path.resolve())
    project = storage.create_project("Archive GC")
    orphan = storage.audio_path(project.id, "stale.wav")
    orphan.write_bytes(b"stale")
    storage.reconcile_project_gc(project.id, {orphan.name})
    archive = tmp_path / "project.maeproj"
    storage.write_project_archive(project.id, archive)
    with zipfile.ZipFile(archive) as z:
        names = set(z.namelist())
    assert "project/.gc-pending.json" not in names
    assert "project/audio/stale.wav" not in names


def test_delete_ui_uses_single_snapshot_transaction_and_no_pre_save():
    root = Path(__file__).resolve().parents[1]
    js = (root / "app/static/app.js").read_text(encoding="utf-8")
    start = js.index("async function deleteTracksByIds(ids)")
    end = js.index("\nasync function deleteSelection", start)
    block = js[start:end]
    assert "await save();" not in block
    assert "JSON.stringify({track_ids:ids,project:before})" in block
    assert "void syncNativeProjectFile(saved.id)" in block
