from pathlib import Path

from app.models import Clip, LyricLine, LyricWord, Track
from app.music_text import build_karaoke_ass, map_source_events_to_timeline

ROOT = Path(__file__).resolve().parents[1]


def test_import_separate_exposes_lyrics_chords_options_and_backend_flags():
    js = (ROOT / "app/static/app.js").read_text(encoding="utf-8")
    main = (ROOT / "app/main.py").read_text(encoding="utf-8")
    assert "stemExtractLyrics" in js
    assert "stemExtractChords" in js
    assert "extract_lyrics=${extractLyrics}" in js
    assert "extract_chords=${extractChords}" in js
    assert "extract_lyrics: bool = False" in main
    assert "extract_chords: bool = False" in main
    assert 'project.lyrics = extract_lyrics(lyric_source)' in main
    assert 'project.chords = extract_chords(source)' in main


def test_word_timestamps_are_shifted_with_track_timeline():
    track = Track(
        id="t1", name="Voice", filename="voice.wav", duration_ms=5000,
        clips=[Clip(id="c1", source_start_ms=1000, source_end_ms=4000, timeline_start_ms=3000)],
    )
    line = LyricLine(
        time_ms=1500, end_ms=2500, text="hello world",
        words=[LyricWord(start_ms=1500, end_ms=1900, text="hello"), LyricWord(start_ms=2000, end_ms=2500, text="world")],
    )
    mapped = map_source_events_to_timeline(track, [line])
    assert mapped[0].time_ms == 3500
    assert mapped[0].end_ms == 4500
    assert mapped[0].words[0].start_ms == 3500
    assert mapped[0].words[1].end_ms == 4500


def test_karaoke_ass_uses_word_level_karaoke(tmp_path):
    out = tmp_path / "karaoke.ass"
    lyrics = [LyricLine(
        time_ms=1000, end_ms=2200, text="Hello world",
        words=[LyricWord(start_ms=1000, end_ms=1500, text="Hello"), LyricWord(start_ms=1500, end_ms=2200, text="world")],
    )]
    build_karaoke_ass(out, title="Song", artist="Artist", lyrics=lyrics)
    text = out.read_text(encoding="utf-8")
    assert "Song · Artist" in text
    assert r"{\kf50}Hello" in text
    assert r"{\kf70}world" in text
    assert "Dialogue: 0,0:00:01.00,0:00:02.20,Karaoke" in text


def test_pdf_chord_color_and_mp4_ui_are_exposed():
    js = (ROOT / "app/static/app.js").read_text(encoding="utf-8")
    music = (ROOT / "app/music_text.py").read_text(encoding="utf-8")
    main = (ROOT / "app/main.py").read_text(encoding="utf-8")
    assert "lyricsPdfChordColor" in js
    assert "chord_color=" in js
    assert "HexColor(chord_color)" in music
    assert "MP4 Karaoke" in js
    assert "exportKaraokeBackground" in js
    assert "L'export MP4 richiede lyrics sincronizzate" in main
    assert "/karaoke-export-jobs" in main


def test_accuracy_defaults_prefer_large_whisper_and_chordino():
    music = (ROOT / "app/music_text.py").read_text(encoding="utf-8")
    assert 'MTA_LYRICS_WHISPER_MODEL' in music and '"base"' in music
    assert '"word_timestamps": True' in music
    assert '"beam_size": max(1, int(os.getenv("MTA_LYRICS_BEAM_SIZE", "8")))' in music
    assert "vamp:nnls-chroma:chordino:simplechord" in music
