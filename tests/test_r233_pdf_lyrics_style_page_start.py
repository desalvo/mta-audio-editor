from pathlib import Path

import fitz

from app.models import LyricLine
from app.music_text import build_lyrics_pdf


def _first_lyric_span(page):
    data = page.get_text("dict")
    for block in data.get("blocks", []):
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                if str(span.get("text", "")).startswith("LINE-"):
                    return span
    raise AssertionError("No lyric span found")


def test_lyric_only_row_at_page_start_keeps_lyrics_style(tmp_path: Path):
    out = tmp_path / "lyrics-page-start-style.pdf"
    lyrics = [
        LyricLine(time_ms=i * 1000, end_ms=i * 1000 + 800, text=f"LINE-{i:02d}")
        for i in range(50)
    ]
    build_lyrics_pdf(
        out,
        title="Lyrics page-start style",
        artist="",
        lyrics=lyrics,
        chords=[],
        pdf_style={"lyrics": {"style": "bold", "size": 17, "color": "#CC0000"}},
    )
    with fitz.open(out) as doc:
        assert len(doc) >= 2
        span = _first_lyric_span(doc[1])
        assert "Bold" in span["font"]
        assert span["size"] == 17.0
        assert span["color"] == 0xCC0000
