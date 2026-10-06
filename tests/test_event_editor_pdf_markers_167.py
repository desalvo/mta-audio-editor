from pathlib import Path

from app.codec import _synchronized_text_attachments
from app.models import Chord, LyricLine, Marker, Project
from app.music_text import build_lyrics_pdf


def test_project_has_persistent_pdf_typography_defaults():
    p = Project(id="p1", title="Song")
    assert p.lyrics_pdf_style.title.style == "bold"
    assert p.lyrics_pdf_style.chords.color == "#7B1FA2"
    assert p.lyrics_pdf_style.markers.size >= 6


def test_event_override_fields_roundtrip():
    line = LyricLine(time_ms=1000, text=".", manual_override=True, source_snapshot={"text": "old"})
    chord = Chord(time_ms=1000, chord="C", excluded=True, deleted=False, manual_override=True)
    marker = Marker(time_ms=1000, label="Instrumental", disabled=True, manual_override=True)
    assert LyricLine(**line.model_dump()).manual_override
    assert Chord(**chord.model_dump()).excluded
    assert Marker(**marker.model_dump()).disabled


def test_mta_sync_omits_disabled_deleted_but_includes_markers(monkeypatch, tmp_path):
    import app.codec as codec

    monkeypatch.setattr(codec, "pdir", lambda _pid: tmp_path)
    p = Project(
        id="p1",
        title="Song",
        lyrics=[LyricLine(time_ms=0, text="keep"), LyricLine(time_ms=1000, text="hide", disabled=True)],
        chords=[Chord(time_ms=0, chord="C"), Chord(time_ms=1000, chord="G", excluded=True)],
        markers=[Marker(time_ms=0, label="Intro"), Marker(time_ms=1000, label="Skip", disabled=True)],
    )
    paths = _synchronized_text_attachments(p)
    sync = next(x for x in paths if x.name == "mta-synchronized-text.json")
    text = sync.read_text(encoding="utf-8")
    assert '"Intro"' in text
    assert '"Skip"' not in text
    assert '"keep"' in text and '"hide"' not in text
    assert '"C"' in text and '"G"' not in text


def test_pdf_accepts_markers_and_independent_styles(tmp_path):
    out = tmp_path / "lyrics.pdf"
    build_lyrics_pdf(
        out,
        title="Song",
        artist="Artist",
        lyrics=[LyricLine(time_ms=1000, end_ms=3000, text="hello world")],
        chords=[Chord(time_ms=1500, chord="C")],
        markers=[Marker(time_ms=900, label="Intro")],
        bpm=120,
        pdf_style={
            "title": {"style": "italic", "size": 20, "color": "#111111"},
            "subtitle": {"style": "normal", "size": 10, "color": "#222222"},
            "bpm": {"style": "bold", "size": 9, "color": "#333333"},
            "lyrics": {"style": "normal", "size": 12, "color": "#111111"},
            "chords": {"style": "bold", "size": 10, "color": "#7B1FA2"},
            "markers": {"style": "italic", "size": 13, "color": "#204A87"},
        },
    )
    assert out.exists() and out.stat().st_size > 500


def test_joint_editor_and_render_meter_regression_strings_present():
    js = Path("app/static/app.js").read_text(encoding="utf-8")
    assert "addInstrumentalSection" in js
    assert "restoreDraftEvent" in js
    assert "lyricsChordsEditorMarkersDraft" in js
    assert "openLyricsPdfStylePanel" in js
    assert "extractMarkersFromSelectedTrack" in js
    assert "sinkGain" in js
    assert "engageRenderLiveFallback" in js
    assert "Hidden legacy textareas are display mirrors only" in js
