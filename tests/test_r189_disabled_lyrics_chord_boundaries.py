from pathlib import Path

MUSIC = Path('app/music_text.py').read_text(encoding='utf-8')


def test_disabled_lyrics_remain_timing_boundaries_for_pdf_chords():
    assert 'boundary_lyrics=sorted((x for x in lyrics if not getattr(x,"deleted",False))' in MUSIC
    assert 'next_boundary=next((t for t in boundary_times if t>line_start), None)' in MUSIC
    assert 'line_end=int(next_boundary if next_boundary is not None' in MUSIC
