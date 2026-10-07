from pathlib import Path

from app.models import LyricsPdfStyle, Marker

ROOT = Path(__file__).resolve().parents[1]
JS = (ROOT / "app/static/app.js").read_text(encoding="utf-8")
PDF = (ROOT / "app/music_text.py").read_text(encoding="utf-8")


def test_marker_section_spacing_is_persisted_and_exposed_in_pdf_style():
    style = LyricsPdfStyle(marker_section_spacing=14)
    assert style.marker_section_spacing == 14
    assert "lyricsPdfMarkerSectionSpacing" in JS
    assert 'marker_section_spacing' in PDF
    assert "extra = marker_section_spacing if marker_draw_count else 0.0" in PDF


def test_marker_section_indent_is_modelled_and_used_by_pdf_renderer():
    marker = Marker(time_ms=1000, label="Verse", section_indent_enabled=True, section_indent_mm=12.5)
    assert marker.section_indent_enabled is True
    assert marker.section_indent_mm == 12.5
    assert "def marker_indent_points(marker: Marker)" in PDF
    assert "mm * 72.0 / 25.4" in PDF
    assert "section_margin = margin + current_section_indent" in PDF
    assert "usable_width - current_section_indent" in PDF
