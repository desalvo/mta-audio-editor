from pathlib import Path

import fitz

from app.models import Chord, LyricLine
from app.music_text import build_lyrics_pdf


def _word(page, text: str):
    return next(w for w in page.get_text('words') if w[4] == text)


def test_end_anchored_chord_stays_close_to_lyric_text_in_pdf_and_preview_renderer(tmp_path: Path):
    out = tmp_path / 'lyrics-end-anchor.pdf'
    build_lyrics_pdf(
        out,
        title='Song',
        artist='',
        lyrics=[LyricLine(time_ms=0, end_ms=2000, text='short lyric')],
        chords=[Chord(time_ms=1900, chord='G7', manual_anchor=True, anchor_kind='end', anchor_line_time_ms=0)],
    )
    with fitz.open(out) as doc:
        page = doc[0]
        chord = _word(page, 'G7')
        lyric = _word(page, 'lyric')
        # End anchors should sit shortly after the content, not at the far-right margin.
        assert chord[0] >= lyric[2]
        assert chord[0] - lyric[2] < 24
        assert chord[2] < page.rect.width * 0.5


def test_end_anchor_uses_previous_chord_as_minimum_spacing(tmp_path: Path):
    out = tmp_path / 'lyrics-end-sequence.pdf'
    build_lyrics_pdf(
        out,
        title='Song',
        artist='',
        lyrics=[LyricLine(time_ms=0, end_ms=2000, text='short lyric')],
        chords=[
            Chord(time_ms=1700, chord='Fmaj7', manual_anchor=True, anchor_kind='end', anchor_line_time_ms=0, anchor_order=0),
            Chord(time_ms=1900, chord='G7', manual_anchor=True, anchor_kind='end', anchor_line_time_ms=0, anchor_order=1),
        ],
    )
    with fitz.open(out) as doc:
        page = doc[0]
        first = _word(page, 'Fmaj7')
        second = _word(page, 'G7')
        assert second[0] >= first[2] + 4
        assert second[2] < page.rect.width * 0.5
