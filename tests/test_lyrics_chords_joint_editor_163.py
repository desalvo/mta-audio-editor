from pathlib import Path


def test_chord_manual_anchor_round_trip_and_transpose():
    from app.models import Chord, Project
    from app.music_text import transpose_chords

    chord = Chord(
        time_ms=1200,
        chord="C",
        anchor_line_time_ms=1000,
        anchor_word_index=2,
        anchor_word_text="world",
        manual_anchor=True,
    )
    project = Project(id="p", title="Song", chords=[chord])
    restored = Project.model_validate_json(project.model_dump_json())
    assert restored.chords[0].manual_anchor is True
    assert restored.chords[0].anchor_line_time_ms == 1000
    assert restored.chords[0].anchor_word_index == 2
    shifted = transpose_chords(restored.chords, 2)[0]
    assert shifted.chord == "D"
    assert shifted.manual_anchor is True
    assert shifted.anchor_word_index == 2
    assert shifted.anchor_word_text == "world"


def test_manual_anchor_helpers_clamp_word_index():
    from app.models import Chord, LyricLine
    from app.music_text import _manual_chord_line_match, _manual_chord_word_index

    lyric = LyricLine(time_ms=5000, text="one two three")
    chord = Chord(
        time_ms=100,
        chord="G",
        anchor_line_time_ms=5000,
        anchor_word_index=99,
        manual_anchor=True,
    )
    assert _manual_chord_line_match(chord, lyric)
    assert _manual_chord_word_index(chord, 3) == 2


def test_joint_editor_ui_is_present_and_persists_manual_anchor():
    js = Path("app/static/app.js").read_text(encoding="utf-8")
    css = Path("app/static/app.css").read_text(encoding="utf-8")
    assert "Editor Lyrics + Chords" in js
    assert "openLyricsChordsEditor()" in js
    assert "draggable=\"true\"" in js
    assert "anchor_line_time_ms" in js
    assert "anchor_word_index" in js
    assert "manual_anchor=true" in js
    assert "Salva editor e sincronizzazione MTA" in js
    assert "syncNativeProjectFile(saved.id)" in js
    assert ".lyrics-chords-editor" in css
    assert ".lc-word" in css
    assert ".lc-chord.manual" in css


def test_pdf_renderer_uses_manual_word_override_before_timing_guess():
    source = Path("app/music_text.py").read_text(encoding="utf-8")
    assert "manual_index = _manual_chord_word_index(chord, len(word_entries))" in source
    assert 'return word_entries[manual_index]["x"]' in source
    assert "_manual_chord_line_match(ch, lyric)" in source
