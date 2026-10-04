import math
import wave
from pathlib import Path

import numpy as np


def _triad_wav(path: Path, seconds: float = 2.5):
    sr = 11025
    t = np.arange(int(sr * seconds), dtype=np.float64) / sr
    x = sum(np.sin(2 * math.pi * f * t) for f in (261.6256, 329.6276, 391.9954)) / 3
    pcm = np.asarray(x * 24000, dtype=np.int16)
    with wave.open(str(path), "wb") as h:
        h.setnchannels(1); h.setsampwidth(2); h.setframerate(sr); h.writeframes(pcm.tobytes())


def test_track_context_menu_exposes_lyrics_chords_and_downloads():
    root = Path(__file__).resolve().parents[1]
    js = (root / "app/static/app.js").read_text(encoding="utf-8")
    assert "Estrai lyrics" in js
    assert "Estrai chords" in js
    assert "extract-${kind}-jobs" in js
    main = (root / "app/main.py").read_text(encoding="utf-8")
    assert "extract-lyrics-jobs" in main
    assert "extract-chords-jobs" in main
    assert "/lyrics.txt?chords=" in js
    assert "/lyrics.pdf" in js
    assert "Modifica titolo / autore / BPM" in js


def test_source_events_follow_track_clip_timeline():
    from app.models import Clip, LyricLine, Track
    from app.music_text import map_source_events_to_timeline
    track = Track(
        id="t1", name="Voice", filename="voice.wav", duration_ms=12000,
        clips=[Clip(id="c1", source_start_ms=2000, source_end_ms=8000, timeline_start_ms=5000)],
    )
    mapped = map_source_events_to_timeline(track, [
        LyricLine(time_ms=1000, text="before"),
        LyricLine(time_ms=2500, text="inside"),
        LyricLine(time_ms=7900, text="end"),
    ])
    assert [(x.time_ms, x.text) for x in mapped] == [(5500, "inside"), (10900, "end")]


def test_lightweight_chord_extractor_finds_c_major(tmp_path):
    from app.music_text import extract_chords
    source = tmp_path / "c-major.wav"
    _triad_wav(source)
    chords = extract_chords(source, interval_ms=750)
    assert chords
    assert chords[0].chord == "C"


def test_synchronized_text_and_pdf(tmp_path):
    from app.models import Chord, LyricLine
    from app.music_text import build_lyrics_pdf, synchronized_plain_text
    lyrics = [LyricLine(time_ms=1000, text="Hello world"), LyricLine(time_ms=3000, text="Second line")]
    chords = [Chord(time_ms=900, chord="C"), Chord(time_ms=2500, chord="G")]
    text = synchronized_plain_text(lyrics, chords)
    assert "[00:01.00][C] Hello world" in text
    assert "[00:03.00][G] Second line" in text
    out = tmp_path / "lyrics.pdf"
    build_lyrics_pdf(out, title="My Song", artist="The Artist", lyrics=lyrics, chords=chords)
    assert out.read_bytes().startswith(b"%PDF-")
    assert out.stat().st_size > 1000


def test_mta_export_sync_attachments_are_lossless(tmp_path, monkeypatch):
    import app.codec as codec
    import app.storage as storage
    from app.models import Chord, LyricLine
    monkeypatch.setattr(storage, "ROOT", tmp_path)
    monkeypatch.setattr(codec, "pdir", storage.pdir)
    project = storage.create_project("Song", "MTA8")
    project.artist = "Artist"
    project.lyrics = [LyricLine(time_ms=1234, text="Line")]
    project.chords = [Chord(time_ms=1200, chord="Am")]
    files = codec._synchronized_text_attachments(project)
    names = {x.name for x in files}
    assert {"lyrics-synchronized.lrc", "chords-synchronized.tsv", "mta-synchronized-text.json"} <= names
    payload = (storage.pdir(project.id) / "attachments" / "mta-synchronized-text.json").read_text(encoding="utf-8")
    assert '"time_ms": 1234' in payload and '"chord": "Am"' in payload


def test_text_music_worker_updates_project_for_lyrics_and_chords(monkeypatch, tmp_path):
    import app.main as main
    from app.models import Chord, LyricLine, Project, Track

    source = tmp_path / "voice.wav"; source.write_bytes(b"x")
    project = Project(id="p1", title="Song", target="DAW", tracks=[Track(id="t1", name="Voice", filename="voice.wav", duration_ms=1000)])
    saved = []
    monkeypatch.setattr(main, "load_project", lambda pid: project)
    monkeypatch.setattr(main, "save_project", lambda p: saved.append(p.model_copy(deep=True)))
    monkeypatch.setattr(main, "audio_path", lambda pid, filename: source)
    monkeypatch.setattr(main, "extract_lyrics", lambda path: [LyricLine(time_ms=100, text="hello")])
    monkeypatch.setattr(main, "extract_chords", lambda path: [Chord(time_ms=120, chord="C")])
    monkeypatch.setattr(main, "map_source_events_to_timeline", lambda track, events: events)

    for kind in ("lyrics", "chords"):
        jid = f"job-{kind}"
        with main.MEDIA_JOB_LOCK:
            main.MEDIA_JOBS[jid] = {"id": jid, "kind": kind, "project_id": "p1", "status": "queued", "progress": 0, "message": "", "created_at": 0, "updated_at": 0, "result": None, "error": None}
        main._text_music_worker(jid, "p1", "t1", kind)
        with main.MEDIA_JOB_LOCK:
            job = dict(main.MEDIA_JOBS[jid])
        assert job["status"] == "completed"
        assert job["result"]["count"] == 1
    assert project.lyrics[0].text == "hello"
    assert project.chords[0].chord == "C"
    assert saved


def test_text_music_worker_failure_is_reported(monkeypatch, tmp_path):
    import app.main as main
    from app.models import Project, Track
    project = Project(id="p2", title="Song", target="DAW", tracks=[Track(id="t2", name="Voice", filename="x.wav", duration_ms=100)])
    monkeypatch.setattr(main, "load_project", lambda pid: project)
    monkeypatch.setattr(main, "audio_path", lambda pid, filename: tmp_path / filename)
    monkeypatch.setattr(main, "extract_lyrics", lambda path: (_ for _ in ()).throw(RuntimeError("boom")))
    jid = "job-fail"
    with main.MEDIA_JOB_LOCK:
        main.MEDIA_JOBS[jid] = {"id": jid, "kind": "lyrics", "project_id": "p2", "status": "queued", "progress": 0, "message": "", "created_at": 0, "updated_at": 0, "result": None, "error": None}
    main._text_music_worker(jid, "p2", "t2", "lyrics")
    with main.MEDIA_JOB_LOCK:
        job = dict(main.MEDIA_JOBS[jid])
    assert job["status"] == "failed"
    assert "boom" in job["error"]
