from pathlib import Path

import fitz

from app.models import LyricLine, Marker
from app.music_text import build_lyrics_pdf


def _page_texts(path: Path) -> list[str]:
    doc = fitz.open(path)
    try:
        return [page.get_text("text") for page in doc]
    finally:
        doc.close()


def test_pdf_marker_keeps_at_least_two_following_lyrics_on_same_page(tmp_path):
    lyrics = [
        LyricLine(time_ms=i * 1000, end_ms=i * 1000 + 800, text=f"LYRIC-{i:02d}")
        for i in range(42)
    ]
    marker_index = 26
    out = tmp_path / "marker-orphan.pdf"
    build_lyrics_pdf(
        out,
        title="Marker orphan test",
        artist="",
        lyrics=lyrics,
        chords=[],
        markers=[Marker(time_ms=marker_index * 1000, label="VERSE")],
    )
    pages = _page_texts(out)
    assert len(pages) >= 2
    marker_page = next(text for text in pages if "VERSE:" in text)
    assert f"LYRIC-{marker_index:02d}" in marker_page
    assert f"LYRIC-{marker_index + 1:02d}" in marker_page


def test_pdf_always_numbers_pages_as_current_over_total(tmp_path):
    lyrics = [
        LyricLine(time_ms=i * 1000, end_ms=i * 1000 + 800, text=f"ROW-{i:02d}")
        for i in range(55)
    ]
    out = tmp_path / "numbered.pdf"
    build_lyrics_pdf(out, title="Numbered", artist="", lyrics=lyrics, chords=[], markers=[])
    pages = _page_texts(out)
    total = len(pages)
    assert total >= 2
    for index, text in enumerate(pages, start=1):
        assert f"{index}/{total}" in text


def test_marker_delete_is_hard_delete_across_editor_paths():
    js = Path("app/static/app.js").read_text(encoding="utf-8")
    assert "if(kind==='chords'||kind==='markers'){arr.splice(i,1)" in js
    assert "if(f.kind==='chords'||f.kind==='markers')arr.splice(f.index,1)" in js
    assert "action==='delete'&&(kind==='chords'||kind==='markers')" in js
    assert "current.markers=current.markers.filter(marker=>!marker?.deleted)" in js
    assert "ev.disabled=!!ev.disabled&&!!next.disabled;arr.splice(j,1)" in js
