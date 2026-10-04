from pathlib import Path

from app.models import Chord, LyricLine
from app.music_text import build_lyrics_pdf, transpose_chord_symbol, transpose_chords, transpose_key_name


def test_chord_and_key_transposition():
    assert transpose_chord_symbol("Cmaj7/G", 2) == "Dmaj7/A"
    assert transpose_chord_symbol("Bbm7/F", 2) == "Cm7/G"
    assert transpose_chord_symbol("N.C.", 2) == "N.C."
    assert transpose_key_name("Bb minor", 2) == "C minor"
    rows = transpose_chords([Chord(time_ms=0, chord="F#m7")], -2)
    assert rows[0].chord == "Em7"


def test_lyrics_pdf_accepts_current_key_bpm_and_color(tmp_path: Path):
    out = tmp_path / "lyrics.pdf"
    build_lyrics_pdf(
        out, title="Song", artist="Artist", key="D major", bpm=128.5,
        lyrics=[LyricLine(time_ms=0, text="Hello world")],
        chords=[Chord(time_ms=0, chord="D")], chord_color="#3366CC",
    )
    assert out.is_file() and out.stat().st_size > 500


def test_track_ui_has_color_picker_and_drag_drop():
    js = Path("app/static/app.js").read_text(encoding="utf-8")
    assert "track-color-picker" in js
    assert "draggable=\"true\"" in js
    assert "dropTrack(event" in js
    assert "setTrackColor" in js
