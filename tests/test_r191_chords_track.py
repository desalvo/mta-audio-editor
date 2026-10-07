import wave
from pathlib import Path

from app.audio_engine import _chord_midi_notes, generate_chords_piano_wav
from app.models import Chord, Clip, Project, Track


def _project() -> Project:
    base = Track(
        id="audio",
        name="Audio",
        type="other",
        filename="audio.wav",
        duration_ms=4000,
        channels=2,
        channel_layout="stereo",
        clips=[Clip(id="clip", source_start_ms=0, source_end_ms=4000, timeline_start_ms=0)],
    )
    return Project(
        id="p",
        title="Song",
        target="DAW",
        tracks=[base],
        chords=[
            Chord(time_ms=0, chord="C"),
            Chord(time_ms=1000, chord="Am7"),
            Chord(time_ms=2000, chord="F#dim"),
            Chord(time_ms=3000, chord="G/B"),
        ],
    )


def test_common_chord_symbols_are_voiced():
    assert _chord_midi_notes("C")
    assert len(_chord_midi_notes("Am7")) >= 4
    assert len(_chord_midi_notes("F#dim")) >= 3
    slash = _chord_midi_notes("G/B")
    assert slash and min(slash) < 48
    assert _chord_midi_notes("N.C.") == []


def test_chords_track_renders_stereo_piano_guide(tmp_path: Path):
    out = tmp_path / "chords.wav"
    duration = generate_chords_piano_wav(_project(), out)
    assert duration == 4000
    assert out.exists() and out.stat().st_size > 1000
    with wave.open(str(out), "rb") as wav:
        assert wav.getnchannels() == 2
        assert wav.getframerate() == 44100
        assert 3.9 <= wav.getnframes() / wav.getframerate() <= 4.1


def test_chords_track_ignores_excluded_and_deleted(tmp_path: Path):
    project = _project()
    project.chords[0].excluded = True
    project.chords[1].deleted = True
    out = tmp_path / "filtered.wav"
    generate_chords_piano_wav(project, out)
    with wave.open(str(out), "rb") as wav:
        assert wav.getnframes() > 0


def test_chords_track_api_is_unique_and_toolbar_exposes_action():
    main = Path("app/main.py").read_text(encoding="utf-8")
    js = Path("app/static/app.js").read_text(encoding="utf-8")
    assert 'CHORDS_TRACK_LOCK = threading.Lock()' in main
    assert '@app.post("/api/projects/{pid}/chords-track")' in main
    assert 'existing = [item for item in project.tracks if is_chords_track(item)]' in main
    assert 'if len(existing) > 1:' in main
    assert 'createChordsTrack()' in js
    assert '♬ Chords' in js


def test_chords_renderer_rejects_missing_duration_and_missing_active_chords(tmp_path: Path):
    empty = Project(id="empty", title="Empty", target="DAW", chords=[Chord(time_ms=0, chord="C")])
    try:
        generate_chords_piano_wav(empty, tmp_path / "empty.wav")
    except ValueError as exc:
        assert "duration" in str(exc)
    else:
        raise AssertionError("expected zero-duration project to be rejected")

    project = _project()
    for chord in project.chords:
        chord.excluded = True
    try:
        generate_chords_piano_wav(project, tmp_path / "none.wav")
    except ValueError as exc:
        assert "active chords" in str(exc)
    else:
        raise AssertionError("expected project without active chords to be rejected")


def test_unparseable_or_out_of_range_chords_are_safely_skipped(tmp_path: Path):
    project = _project()
    project.chords = [Chord(time_ms=0, chord="???"), Chord(time_ms=5000, chord="C")]
    out = tmp_path / "silent-guide.wav"
    generate_chords_piano_wav(project, out)
    with wave.open(str(out), "rb") as wav:
        assert wav.getnframes() > 0
