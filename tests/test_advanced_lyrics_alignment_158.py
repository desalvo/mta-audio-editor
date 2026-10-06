from pathlib import Path

import numpy as np

from app.models import LyricLine, LyricWord
from app import music_text


def test_forced_alignment_adds_syllables(monkeypatch, tmp_path):
    monkeypatch.setattr(music_text, "_pcm_mono", lambda path, sample_rate=16000: (np.zeros(32000, dtype=np.float32), 16000))
    lines=[LyricLine(time_ms=0,end_ms=1200,text="amore",words=[LyricWord(start_ms=100,end_ms=1100,text="amore")])]
    out=music_text.forced_align_lyrics(tmp_path/"x.wav", lines)
    assert out[0].words
    assert out[0].words[0].syllables
    assert out[0].words[0].syllables[0].start_ms >= 0
    assert out[0].words[0].syllables[-1].end_ms == out[0].words[0].end_ms


def test_whisper_defaults_disable_previous_text_conditioning():
    kwargs=music_text._lyrics_transcribe_kwargs(None,"cpu")
    assert kwargs["word_timestamps"] is True
    assert kwargs["condition_on_previous_text"] is False


def test_ui_contains_alignment_and_live_overlays():
    root=Path(__file__).parents[1]
    js=(root/"app/static/app.js").read_text()
    html=(root/"app/templates/index.html").read_text()
    assert "lyricsAdvancedAlignment" in js
    assert "advanced_alignment=true" in js
    assert "Show Lyrics" in html and "Show Chords" in html
    assert "updateTimedPlaybackOverlay" in js
