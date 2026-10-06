from pathlib import Path
import importlib

from app.models import Chord, Clip, Project, Track

ROOT = Path(__file__).resolve().parents[1]
JS = (ROOT / "app/static/app.js").read_text(encoding="utf-8")
MUSIC = (ROOT / "app/music_text.py").read_text(encoding="utf-8")
MODELS = (ROOT / "app/models.py").read_text(encoding="utf-8")
MAIN = (ROOT / "app/main.py").read_text(encoding="utf-8")


def test_pdf_does_not_carry_previous_chord_to_first_word():
    assert "Never carry a previous automatic chord onto the next lyric line" in MUSIC
    assert "if ch.manual_anchor or int(ch.time_ms) >= first_word_start" in MUSIC
    assert 'return float("nan")' in MUSIC


def test_manual_first_word_chord_wins_over_automatic_overlap():
    assert "manual_first = any(" in MUSIC
    assert "not (first_word_start <= int(ch.time_ms) <= int(words[0].get" in MUSIC


def test_marker_edit_dialog_supports_color():
    assert 'id="lcEventEditColor" type="color"' in JS
    assert "ev.color=color" in JS


def test_chords_never_inherit_marker_color_in_pdf():
    assert 'c.setFillColor(st("chords")[2])' in MUSIC
    chord_block = MUSIC[MUSIC.index("if line_chords:"):MUSIC.index("lyric_font,lyric_size", MUSIC.index("if line_chords:"))]
    assert 'current_section_color or st("chords")' not in chord_block


def test_chord_anchor_supports_character_offset_inside_word():
    assert "anchor_char_offset" in MODELS
    assert "lcWordCharOffset" in JS
    assert "anchor_char_offset=kind==='word'" in JS
    assert "char_offset = getattr(chord, \"anchor_char_offset\", None)" in MUSIC
    c = Chord(time_ms=1000, chord="C", anchor_char_offset=2)
    assert c.anchor_char_offset == 2


def test_metronome_endpoint_enforces_single_track_and_frontend_debounces():
    assert "one project, one metronome" in MAIN
    assert "duplicate_ids" in MAIN
    assert "METRONOME_TRACK_LOCK" in MAIN
    assert '"reused": reused' in MAIN
    assert "metronomeCreatePending" in JS
    assert "Creazione/aggiornamento metronomo già in corso" in JS



def test_metronome_helper_creates_then_reuses_single_track(monkeypatch, tmp_path):
    main_module = importlib.import_module("app.main")
    project = Project(
        id="p1",
        title="Song",
        bpm=120,
        tracks=[
            Track(
                id="audio1",
                name="Audio",
                filename="audio.wav",
                duration_ms=4000,
                clips=[Clip(id="clip1", source_start_ms=0, source_end_ms=4000, timeline_start_ms=0)],
            )
        ],
    )
    saved = []
    monkeypatch.setattr(main_module, "_project_for_actor", lambda request, pid: project)
    monkeypatch.setattr(main_module, "project_duration_ms", lambda p: 4000)
    monkeypatch.setattr(main_module, "audio_path", lambda pid, filename: tmp_path / filename)
    monkeypatch.setattr(main_module, "generate_metronome_wav", lambda p, out: 4000)
    monkeypatch.setattr(main_module, "waveform_peaks", lambda out: [0.1, 0.2])
    monkeypatch.setattr(main_module, "_track_waveform_revision", lambda track, out: "rev")
    monkeypatch.setattr(main_module, "save_project", lambda p: saved.append(p.model_copy(deep=True)))

    first = main_module._create_metronome_track_locked("p1", object())
    assert first["reused"] is False
    assert len([t for t in project.tracks if t.type == "click"]) == 1
    metronome_id = first["track"].id

    second = main_module._create_metronome_track_locked("p1", object())
    assert second["reused"] is True
    assert second["track"].id == metronome_id
    assert len([t for t in project.tracks if t.type == "click"]) == 1
    assert len(saved) == 2


def test_metronome_helper_consolidates_old_duplicates(monkeypatch, tmp_path):
    main_module = importlib.import_module("app.main")
    project = Project(
        id="p2",
        title="Song",
        bpm=100,
        tracks=[
            Track(id="audio", name="Audio", filename="audio.wav", duration_ms=3000),
            Track(id="m1", name="Metronomo 100 BPM", type="click", filename="m1.wav", duration_ms=3000),
            Track(id="m2", name="Metronomo duplicate", type="click", filename="m2.wav", duration_ms=3000),
        ],
    )
    monkeypatch.setattr(main_module, "_project_for_actor", lambda request, pid: project)
    monkeypatch.setattr(main_module, "project_duration_ms", lambda p: 3000)
    monkeypatch.setattr(main_module, "audio_path", lambda pid, filename: tmp_path / filename)
    monkeypatch.setattr(main_module, "generate_metronome_wav", lambda p, out: 3000)
    monkeypatch.setattr(main_module, "waveform_peaks", lambda out: [])
    monkeypatch.setattr(main_module, "save_project", lambda p: None)

    result = main_module._create_metronome_track_locked("p2", object())
    assert result["reused"] is True
    clicks = [t for t in project.tracks if t.type == "click"]
    assert len(clicks) == 1
    assert clicks[0].id == "m1"
