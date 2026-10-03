from __future__ import annotations

import wave
from pathlib import Path

import pytest

from app import audio_engine
from app.models import Clip, Project, Track


def make_track(*, duration_ms: int = 1000, clips=None) -> Track:
    return Track(
        id="t1",
        name="Track 1",
        filename="track.wav",
        duration_ms=duration_ms,
        clips=[] if clips is None else clips,
    )


def make_project(track: Track | None = None, *, bpm: float = 120.0) -> Project:
    return Project(
        id="p1",
        title="Coverage",
        target="DAW",
        bpm=bpm,
        tracks=[] if track is None else [track],
    )


def test_media_duration_ms_handles_valid_and_invalid_ffprobe(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(audio_engine, "_run", lambda cmd: "1.234\n")
    assert audio_engine.media_duration_ms(tmp_path / "a.wav") == 1234

    monkeypatch.setattr(audio_engine, "_run", lambda cmd: "not-a-number")
    assert audio_engine.media_duration_ms(tmp_path / "a.wav") == 0


def test_ensure_clips_and_project_duration_create_default_clip():
    track = make_track(duration_ms=1250)
    assert track.clips == []
    audio_engine.ensure_clips(track)
    assert len(track.clips) == 1
    assert track.clips[0].source_start_ms == 0
    assert track.clips[0].source_end_ms == 1250
    assert track.clips[0].timeline_start_ms == 0
    assert audio_engine.project_duration_ms(make_project(track)) == 1250


def test_project_duration_uses_latest_clip_end():
    track = make_track(
        duration_ms=0,
        clips=[
            Clip(id="c1", source_start_ms=0, source_end_ms=500, timeline_start_ms=100),
            Clip(id="c2", source_start_ms=0, source_end_ms=700, timeline_start_ms=900),
        ],
    )
    assert audio_engine.project_duration_ms(make_project(track)) == 1600


def test_generate_metronome_wav_writes_valid_pcm_and_accents(tmp_path: Path):
    track = make_track(duration_ms=1100)
    project = make_project(track, bpm=120.0)
    out = tmp_path / "metronome.wav"

    duration = audio_engine.generate_metronome_wav(project, out, beats_per_bar=4)

    assert duration == 1100
    assert out.is_file() and out.stat().st_size > 1000
    with wave.open(str(out), "rb") as handle:
        assert handle.getnchannels() == 1
        assert handle.getsampwidth() == 2
        assert handle.getframerate() == 44100
        assert handle.getnframes() >= 48000
        frames = handle.readframes(4096)
        assert any(frames)


def test_generate_metronome_rejects_zero_duration(tmp_path: Path):
    with pytest.raises(ValueError, match="project duration is zero"):
        audio_engine.generate_metronome_wav(make_project(), tmp_path / "empty.wav")


def test_shift_track_negative_trims_and_drops_clips():
    track = make_track(
        duration_ms=0,
        clips=[
            Clip(id="drop", source_start_ms=0, source_end_ms=100, timeline_start_ms=0),
            Clip(id="trim", source_start_ms=10, source_end_ms=410, timeline_start_ms=50),
            Clip(id="move", source_start_ms=0, source_end_ms=200, timeline_start_ms=500),
        ],
    )
    audio_engine.shift_track(track, -150)
    assert [c.id for c in track.clips] == ["trim", "move"]
    assert track.clips[0].timeline_start_ms == 0
    assert track.clips[0].source_start_ms == 110
    assert track.clips[1].timeline_start_ms == 350


def test_shift_track_positive_moves_all_clips():
    track = make_track(
        duration_ms=0,
        clips=[Clip(id="c1", source_start_ms=0, source_end_ms=100, timeline_start_ms=25)],
    )
    audio_engine.shift_track(track, 75)
    assert track.clips[0].timeline_start_ms == 100
