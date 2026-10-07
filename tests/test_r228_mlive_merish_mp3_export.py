from pathlib import Path

from app.mlive_mp3 import embed_mlive_merish_metadata
from app.models import Chord, LyricLine, Marker, Project, Track


def _project() -> Project:
    return Project(
        id="p1",
        title="Canzone",
        artist="Artista",
        authors=["Autore Uno"],
        target="DAW",
        tracks=[Track(id="t1", name="Base", filename="base.wav")],
        lyrics=[LyricLine(time_ms=1000, text="Ciao mondo"), LyricLine(time_ms=3000, text="Seconda riga")],
        chords=[Chord(time_ms=900, chord="C"), Chord(time_ms=2900, chord="G7")],
        markers=[Marker(time_ms=0, label="Intro"), Marker(time_ms=2800, label="Verse")],
    )


def _frame_payloads(blob: bytes, frame_id: bytes) -> list[bytes]:
    assert blob.startswith(b"ID3\x03")
    tag_size = (blob[6] << 21) | (blob[7] << 14) | (blob[8] << 7) | blob[9]
    pos = 10
    end = 10 + tag_size
    out = []
    while pos + 10 <= end:
        fid = blob[pos : pos + 4]
        size = int.from_bytes(blob[pos + 4 : pos + 8], "big")
        if not fid.strip(b"\x00") or size <= 0:
            break
        payload = blob[pos + 10 : pos + 10 + size]
        if fid == frame_id:
            out.append(payload)
        pos += 10 + size
    return out


def test_merish_profile_embeds_v23_sylt_lyrics_chords_markers(tmp_path):
    path = tmp_path / "song.mp3"
    path.write_bytes(b"\xff\xfb\x90d" + b"audio" * 20)
    embed_mlive_merish_metadata(path, _project())
    blob = path.read_bytes()
    sylts = _frame_payloads(blob, b"SYLT")
    assert len(sylts) == 3
    assert {payload[5] for payload in sylts} == {1, 4, 5}
    assert any(b"C\x00" in payload and b"G7\x00" in payload for payload in sylts if payload[5] == 5)
    assert any(b"Intro\x00" in payload and b"Verse\x00" in payload for payload in sylts if payload[5] == 4)
    assert _frame_payloads(blob, b"USLT")
    assert _frame_payloads(blob, b"TIT2")
    assert _frame_payloads(blob, b"TPE1")


def test_existing_id3v2_tag_is_replaced_not_nested(tmp_path):
    path = tmp_path / "song.mp3"
    old = b"ID3\x03\x00\x00\x00\x00\x00\x04ABCD" + b"\xff\xfbDATA"
    path.write_bytes(old)
    embed_mlive_merish_metadata(path, _project())
    blob = path.read_bytes()
    assert blob.startswith(b"ID3\x03")
    assert b"ABCD" not in blob
    assert b"\xff\xfbDATA" in blob


def test_ui_exposes_merish_mp3_export_and_maps_extension():
    js = Path("app/static/app.js").read_text(encoding="utf-8")
    assert "MP3 M-Live / Merish" in js
    assert "doExport('mlive_mp3')" in js
    assert "format==='mlive_mp3'?'mp3':format" in js
    assert "config.format==='mlive_mp3'?'mp3':config.format" in js


def test_backend_configured_export_accepts_merish_profile():
    models = Path("app/models.py").read_text(encoding="utf-8")
    main = Path("app/main.py").read_text(encoding="utf-8")
    assert '"mlive_mp3"' in models
    assert 'embed_mlive_merish_metadata(out, source_project)' in main
    assert 'fmt="mp3" if fmt == "mlive_mp3" else fmt' in main
