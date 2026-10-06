from pathlib import Path

from app.models import Chord, LyricLine
from app import music_text


def test_segment_only_lyrics_get_word_and_syllable_best_guess():
    lines = [LyricLine(time_ms=1000, end_ms=3000, text="hello beautiful world")]
    out = music_text._estimated_word_and_syllable_timing(lines)
    assert [w.text for w in out[0].words] == ["hello", "beautiful", "world"]
    assert out[0].words[0].start_ms == 1000
    assert out[0].words[-1].end_ms == 3000
    assert all(w.syllables for w in out[0].words)


def test_advanced_alignment_guarantees_words_even_if_whisper_has_segments_only(monkeypatch, tmp_path):
    monkeypatch.setattr(music_text, "_pcm_mono", lambda *_args, **_kwargs: (__import__("numpy").zeros(16000, dtype=__import__("numpy").float32), 16000))
    out = music_text.forced_align_lyrics(tmp_path / "x.wav", [LyricLine(time_ms=0, end_ms=1500, text="sing it again")])
    assert len(out[0].words) == 3
    assert all(w.syllables for w in out[0].words)
    assert out[0].words[0].start_ms <= out[0].words[1].start_ms <= out[0].words[2].start_ms


def test_pdf_layout_uses_best_guess_when_word_timing_missing(tmp_path):
    out = tmp_path / "guess.pdf"
    music_text.build_lyrics_pdf(
        out, title="Song", artist="Artist",
        lyrics=[LyricLine(time_ms=0, end_ms=4000, text="one two three four")],
        chords=[Chord(time_ms=300, chord="C"), Chord(time_ms=3200, chord="G")],
    )
    assert out.is_file() and out.stat().st_size > 500


def test_pdf_preview_and_download_use_same_server_generator():
    js = Path("app/static/app.js").read_text(encoding="utf-8")
    assert "/lyrics.pdf.preview" in js
    assert "lyricsPdfUrl(false)" in js
    assert "response.blob()" in js
    assert "saveGeneratedBlob" in js
    assert "save_generated_file" in js


def test_show_lyrics_chords_buttons_have_dedicated_visible_active_style():
    html = Path("app/templates/index.html").read_text(encoding="utf-8")
    css = Path("app/static/app.css").read_text(encoding="utf-8")
    assert 'id="showLyricsBtn" class="transport-btn timed-display-mode"' in html
    assert 'id="showChordsBtn" class="transport-btn timed-display-mode"' in html
    assert ".transport-btn.timed-display-mode.active" in css
    assert "width:auto" in css
    assert ".meta-actions .tool" in css and "overflow:visible" in css


def test_native_generated_pdf_uses_os_save_dialog():
    native = Path("native/mta_audio_editor_native.py").read_text(encoding="utf-8")
    assert '"pdf": "PDF Document (*.pdf)"' in native
    assert "def save_generated_file" in native
    assert "create_file_dialog" in native
    assert "os.replace(temp, target)" in native
