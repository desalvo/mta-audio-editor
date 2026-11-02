import shutil
import subprocess

import pytest

from app.models import Clip, Track


@pytest.mark.skipif(shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None, reason="FFmpeg tools required")
def test_proprietary_mta_writer_transport_and_import_roundtrip(tmp_path, monkeypatch):
    import app.storage as storage
    from app.codec import export_mta, ffprobe, import_mta
    from app.mta_reverse import deobfuscate_media_copy, inspect_cluster_transport

    monkeypatch.setattr(storage, "ROOT", tmp_path.resolve())
    source = tmp_path / "tone.wav"
    subprocess.run(
        [
            "ffmpeg", "-y", "-v", "error", "-f", "lavfi",
            "-i", "sine=frequency=440:duration=1",
            "-ar", "44100", "-ac", "2", str(source),
        ],
        check=True,
    )

    project = storage.create_project("Writer smoke", owner_user_id=1)
    shutil.copy2(source, storage.audio_path(project.id, "tone.wav"))
    project.tracks = [
        Track(
            id="track1",
            name="Tone",
            filename="tone.wav",
            duration_ms=1000,
            clips=[Clip(id="clip1", source_start_ms=0, source_end_ms=1000, timeline_start_ms=0)],
        )
    ]
    storage.save_project(project)

    output = tmp_path / "writer-smoke.MTA"
    export_mta(project, output)

    transport = inspect_cluster_transport(output)
    assert transport["validated"] is True
    assert transport["first_cluster_is_canonical"] is False
    assert transport["media_xor_validated"] is True
    assert transport["seek_cluster_absolute"] is not None
    assert transport["cue_point_count"] >= 1

    canonical = tmp_path / "canonical.mka"
    deobfuscate_media_copy(output, canonical)
    streams = [s for s in ffprobe(canonical)["streams"] if s.get("codec_type") == "audio"]
    assert len(streams) == 1

    imported = storage.create_project("Imported", owner_user_id=1)
    import_mta(output, imported)
    assert len(imported.tracks) == 1
    assert imported.tracks[0].name == "Tone"
    assert (storage.pdir(imported.id) / "mta-analysis.json").exists()


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="FFmpeg required")
def test_mta_layout_places_cues_before_first_cluster(tmp_path):
    from app.mta_reverse import inspect_cluster_transport
    from app.mta_writer import normalize_matroska_for_mta

    source = tmp_path / "canonical.mka"
    subprocess.run(
        [
            "ffmpeg", "-y", "-v", "error", "-f", "lavfi",
            "-i", "sine=frequency=220:duration=1",
            "-ar", "44100", "-ac", "2", "-c:a", "libmp3lame",
            "-b:a", "320k", "-f", "matroska", str(source),
        ],
        check=True,
    )
    normalized = tmp_path / "normalized.mka"
    cluster_offset = normalize_matroska_for_mta(source, normalized)
    info = inspect_cluster_transport(normalized)
    assert info["first_cluster_is_canonical"] is True
    assert info["seek_cluster_absolute"] == cluster_offset
    assert info["cue_positions_match_seek_cluster"] is True
    assert info["cue_point_count"] >= 1


def test_mta_layout_reindexes_cues_when_clusters_were_separated(tmp_path):
    import mmap

    from app.mta_reverse import _ebml_children, _ebml_vint
    from app.mta_writer import _build_cues, _elem, _parse_cues, _size_vint, normalize_matroska_for_mta

    info = _elem(0x1549A966, b"")
    tracks = _elem(0x1654AE6B, b"")
    cluster1 = _elem(0x1F43B675, _elem(0xE7, b"\x00"))
    cluster2 = _elem(0x1F43B675, _elem(0xE7, b"\x01"))
    gap = _elem(0xEC, b"\x00" * 100)
    pos1 = len(info) + len(tracks)
    pos2 = pos1 + len(cluster1) + len(gap)
    cues = _build_cues([(0, 1, pos1), (1, 1, pos2)], {pos1: pos1, pos2: pos2})
    payload = info + tracks + cluster1 + gap + cluster2 + cues
    source = tmp_path / "separated.mka"
    source.write_bytes(b"\x1a\x45\xdf\xa3\x80\x18\x53\x80\x67" + _size_vint(len(payload), 8) + payload)
    target = tmp_path / "normalized.mka"
    normalize_matroska_for_mta(source, target)
    with target.open("rb") as fh, mmap.mmap(fh.fileno(), 0, access=mmap.ACCESS_READ) as mm:
        segment = mm.find(b"\x18\x53\x80\x67")
        segment_start = segment + 4 + _ebml_vint(mm, segment + 4)[1]
        children = list(_ebml_children(mm, segment_start, len(mm)))
        clusters = [pos - segment_start for pos, eid, _, _, _ in children if eid == 0x1F43B675]
        _pos, _eid, _size, start, end = next(child for child in children if child[1] == 0x1C53BB6B)
        points = _parse_cues(mm, start, end)
    assert [point[2] for point in points] == clusters


def test_mta_layout_rejects_cues_for_missing_clusters():
    from app.mta_writer import _build_cues

    with pytest.raises(ValueError, match="missing Cluster"):
        _build_cues([(0, 1, 123)], {456: 789})


def test_attachment_order_preserves_content_and_updates_nested_checksums():
    import zlib

    from app.mta_writer import _complete_children, _elem, _normalize_attachment_order

    fields = (
        _elem(0x467E, b"MOD: MTX SETTINGS")
        + _elem(0x466E, b"song.xml")
        + _elem(0x4660, b"application/xml")
        + _elem(0x465C, b"<song/>")
        + _elem(0x46AE, b"\x01\x02")
    )
    entry = _elem(0x61A7, _elem(0xBF, zlib.crc32(fields).to_bytes(4, "little")) + fields)
    source = _elem(0x1941A469, _elem(0xBF, zlib.crc32(entry).to_bytes(4, "little")) + entry)
    result = _normalize_attachment_order(source)
    children = _complete_children(_complete_children(result)[0][2])
    assert int.from_bytes(children[0][2], "little") == zlib.crc32(children[1][1])
    item = _complete_children(children[1][2])
    assert [field[0] for field in item] == [0xBF, 0x466E, 0x4660, 0x465C, 0x46AE, 0x467E]
    assert int.from_bytes(item[0][2], "little") == zlib.crc32(b"".join(field[1] for field in item[1:]))
    assert [field[2] for field in item[1:]] == [b"song.xml", b"application/xml", b"<song/>", b"\x01\x02", b"MOD: MTX SETTINGS"]
    assert _normalize_attachment_order(result) == result


def test_attachment_order_rejects_corrupt_crc():
    from app.mta_writer import _elem, _normalize_attachment_order

    fields = _elem(0x467E, b"title") + _elem(0x466E, b"file.xml")
    source = _elem(0x1941A469, _elem(0xBF, b"\x00" * 4) + _elem(0x61A7, fields))
    with pytest.raises(ValueError, match="CRC mismatch"):
        _normalize_attachment_order(source)


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="FFmpeg required")
def test_ffmpeg_attachment_is_written_with_description_last(tmp_path):
    import mmap
    import zlib

    from app.mta_reverse import _ebml_children, _ebml_vint
    from app.mta_writer import _complete_children, normalize_matroska_for_mta

    attachment = tmp_path / "info.txt"
    attachment.write_bytes(b"user metadata")
    source = tmp_path / "ffmpeg.mka"
    subprocess.run([
        "ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "sine=duration=1",
        "-c:a", "libmp3lame", "-attach", str(attachment),
        "-metadata:s:t:0", "mimetype=text/plain", "-metadata:s:t:0", "title=description", str(source),
    ], check=True)
    target = tmp_path / "normalized.mka"
    normalize_matroska_for_mta(source, target)
    with target.open("rb") as fh, mmap.mmap(fh.fileno(), 0, access=mmap.ACCESS_READ) as mm:
        segment = mm.find(b"\x18\x53\x80\x67")
        start = segment + 4 + _ebml_vint(mm, segment + 4)[1]
        _pos, _eid, _size, a, b = next(child for child in _ebml_children(mm, start, len(mm)) if child[1] == 0x1941A469)
        children = _complete_children(bytes(mm[a:b]))
    crc = next(child for child in children if child[0] == 0xBF)
    assert int.from_bytes(crc[2], "little") == zlib.crc32(b"".join(child[1] for child in children if child[0] != 0xBF))
    item = _complete_children(next(child[2] for child in children if child[0] == 0x61A7))
    assert item[-1][0] == 0x467E and item[-1][2] == b"description"
    assert next(child[2] for child in item if child[0] == 0x465C) == b"user metadata"
