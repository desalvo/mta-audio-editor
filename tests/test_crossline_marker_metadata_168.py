import json
from pathlib import Path

from app.codec import _synchronized_text_attachments
from app.models import Chord, LyricLine, Marker, Project
from app.music_text import _manual_chord_line_match, build_lyrics_pdf


def test_cross_line_manual_chord_anchor_is_authoritative():
    lyric_a = LyricLine(time_ms=1000, text="first line")
    lyric_b = LyricLine(time_ms=4000, text="target word")
    chord = Chord(
        time_ms=1200,
        chord="G",
        manual_anchor=True,
        anchor_line_time_ms=4000,
        anchor_word_index=1,
        anchor_word_text="word",
    )
    assert not _manual_chord_line_match(chord, lyric_a)
    assert _manual_chord_line_match(chord, lyric_b)


def test_marker_color_persists_and_is_exported_to_mta_sync(monkeypatch, tmp_path):
    import app.codec as codec

    monkeypatch.setattr(codec, "pdir", lambda _pid: tmp_path)
    project = Project(
        id="p168",
        title="Song",
        lyrics=[LyricLine(time_ms=0, text="hello")],
        markers=[Marker(time_ms=0, label="Chorus", color="#CC3366", manual_override=True)],
    )
    paths = _synchronized_text_attachments(project)
    sync = next(x for x in paths if x.name == "mta-synchronized-text.json")
    payload = json.loads(sync.read_text(encoding="utf-8"))
    assert payload["markers"][0]["color"] == "#CC3366"
    tsv = next(x for x in paths if x.name == "markers-synchronized.tsv")
    assert "0\tChorus\t#CC3366" in tsv.read_text(encoding="utf-8")


def test_pdf_accepts_marker_section_color(tmp_path):
    out = tmp_path / "marker-color.pdf"
    build_lyrics_pdf(
        out,
        title="Song",
        artist="Artist",
        lyrics=[LyricLine(time_ms=1000, end_ms=2500, text="hello world")],
        chords=[Chord(time_ms=1500, chord="C")],
        markers=[Marker(time_ms=900, label="Chorus", color="#CC3366")],
    )
    assert out.exists() and out.stat().st_size > 500


def test_musicbrainz_search_normalisation(monkeypatch):
    import app.rights_registry as rr

    monkeypatch.setattr(rr, "_read_json", lambda url, params: {
        "recordings": [{
            "id": "abc",
            "title": "My Song",
            "score": 98,
            "first-release-date": "2020-01-01",
            "isrcs": ["ITABC1234567"],
            "artist-credit": [{"name": "Singer", "artist": {"name": "Singer"}}],
        }]
    })
    rows = rr.search_musicbrainz_metadata(title="My Song")
    assert rows[0]["mbid"] == "abc"
    assert rows[0]["performers"] == ["Singer"]
    assert rows[0]["isrcs"] == ["ITABC1234567"]


def test_ui_has_cross_line_anchor_marker_colors_and_metadata_search():
    js = Path("app/static/app.js").read_text(encoding="utf-8")
    assert "chooseLyricsChordAnchor" in js
    assert "Puoi associare il chord" in js
    assert "Colore sezione (#RRGGBB)" in js
    assert "openProjectMetadataSearch" in js
    assert "metadata-search" in js
    assert "metadata-resolve" in js
