from pathlib import Path

from app.audio_engine import generate_metronome_wav
from app.models import Clip, Project, Track


def _project(sig: str) -> Project:
    track = Track(id="t", name="Audio", filename="a.wav", duration_ms=4000, clips=[Clip(id="c", source_start_ms=0, source_end_ms=4000, timeline_start_ms=0)])
    return Project(id="p", title="Song", bpm=120, time_signature=sig, tracks=[track])


def test_metronome_honours_signature_denominator(tmp_path):
    import wave
    p4 = tmp_path / "four.wav"
    p6 = tmp_path / "six.wav"
    generate_metronome_wav(_project("4/4"), p4)
    generate_metronome_wav(_project("6/8"), p6)
    with wave.open(str(p4), "rb") as a, wave.open(str(p6), "rb") as b:
        assert a.getnframes() == b.getnframes()
    # Meter changes must not alter the audible pulse rate; compound meters only
    # change grouping/accent structure.
    source = Path("app/audio_engine.py").read_text(encoding="utf-8")
    assert "beat_seconds = 60.0 / float(project.bpm)" in source
    assert "numerator in {6, 9, 12}" in source


def test_r179_ui_features_present():
    js = Path("app/static/app.js").read_text(encoding="utf-8")
    css = Path("app/static/app.css").read_text(encoding="utf-8")
    assert "Estrai marker automaticamente" in js
    assert "metadataSearchPageSize=10" in js
    assert "showMetadataCandidateDetails" in js
    assert "metadata-results-scroll" in css
    assert "pdf-preview-return" in css and "pdf-preview-save" in css
    assert "lyricsPdfLineSpacing" in js
    assert "waveformMeterLevel" in js
    assert "toolbar-destructive-group" in js
    assert "openLyricsChordsContextMenu(event,'chords'" in js
    assert "toggleDraftEvent(kind,index)" in js
    assert "lc-chord-toggle" in css


def test_pdf_style_has_line_spacing():
    p = Project(id="p", title="Song")
    assert p.lyrics_pdf_style.line_spacing == 8.0
