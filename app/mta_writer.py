"""Deterministic Matroska layout preparation for proprietary MTA transport.

FFmpeg writes a valid Matroska file but may place Cues after media Clusters. Stock
MTA keeps SeekHead/Cues readable before the XOR-transformed media region. This
module rewrites only the top-level Matroska layout: Info/Tracks/Tags/Attachments
are preserved byte-for-byte, Cues are regenerated with adjusted Cluster
positions, a SeekHead including the first Cluster is generated, then the raw
Cluster bytes are appended unchanged.
"""
from __future__ import annotations

import mmap
from pathlib import Path

from .mta_reverse import _ebml_children, _ebml_vint

IDS = {
    "SeekHead": 0x114D9B74,
    "Info": 0x1549A966,
    "Tracks": 0x1654AE6B,
    "Tags": 0x1254C367,
    "Attachments": 0x1941A469,
    "Cues": 0x1C53BB6B,
    "Cluster": 0x1F43B675,
}

ID_BYTES = {value: value.to_bytes((value.bit_length() + 7) // 8, "big") for value in IDS.values()}


def _size_vint(value: int, length: int | None = None) -> bytes:
    if value < 0:
        raise ValueError("negative EBML size")
    lengths = [length] if length else range(1, 9)
    for width in lengths:
        if width is None:
            continue
        max_value = (1 << (7 * width)) - 2
        if value <= max_value:
            encoded = value | (1 << (7 * width))
            return encoded.to_bytes(width, "big")
    raise ValueError("EBML size is too large")


def _uint(value: int) -> bytes:
    if value < 0:
        raise ValueError("negative unsigned EBML integer")
    width = max(1, (value.bit_length() + 7) // 8)
    return value.to_bytes(width, "big")


def _elem(element_id: int, payload: bytes) -> bytes:
    return ID_BYTES.get(element_id, element_id.to_bytes((element_id.bit_length() + 7) // 8, "big")) + _size_vint(len(payload)) + payload


def _void88() -> bytes:
    # EC + one-byte size VINT + 86 payload bytes = 88 total bytes.
    return b"\xec" + _size_vint(86, 1) + (b"\x00" * 86)


def _seek_entry(target_id: int, position: int) -> bytes:
    payload = _elem(0x53AB, ID_BYTES[target_id]) + _elem(0x53AC, _uint(position))
    return _elem(0x4DBB, payload)


def _seek_head(positions: dict[int, int]) -> bytes:
    order = [IDS["Info"], IDS["Tracks"], IDS["Attachments"], IDS["Tags"], IDS["Cues"], IDS["Cluster"]]
    payload = b"".join(_seek_entry(element_id, positions[element_id]) for element_id in order if element_id in positions)
    return _elem(IDS["SeekHead"], payload)


def _parse_cues(mm: mmap.mmap, start: int, end: int) -> list[tuple[int, int, int]]:
    """Return (cue_time, cue_track, cue_cluster_position)."""
    points: list[tuple[int, int, int]] = []
    for _cp, cid, _cs, cstart, cend in _ebml_children(mm, start, end):
        if cid != 0xBB:
            continue
        cue_time = None
        track = 1
        cluster_pos = None
        for _xp, xid, _xs, xstart, xend in _ebml_children(mm, cstart, cend):
            if xid == 0xB3:
                cue_time = int.from_bytes(mm[xstart:xend], "big")
            elif xid == 0xB7:
                for _tp, tid, _ts, tstart, tend in _ebml_children(mm, xstart, xend):
                    if tid == 0xF7:
                        track = int.from_bytes(mm[tstart:tend], "big")
                    elif tid == 0xF1:
                        cluster_pos = int.from_bytes(mm[tstart:tend], "big")
        if cue_time is not None and cluster_pos is not None:
            points.append((cue_time, track, cluster_pos))
    return points


def _build_cues(points: list[tuple[int, int, int]], delta: int) -> bytes:
    payload = bytearray()
    for cue_time, track, old_pos in points:
        positions = _elem(0xF7, _uint(track)) + _elem(0xF1, _uint(old_pos + delta))
        point = _elem(0xB3, _uint(cue_time)) + _elem(0xB7, positions)
        payload += _elem(0xBB, point)
    return _elem(IDS["Cues"], bytes(payload))


def normalize_matroska_for_mta(source: Path, target: Path) -> int:
    """Rewrite canonical Matroska into MTA-friendly pre-media ordering.

    Returns the absolute first-Cluster offset in ``target``. No proprietary XOR
    is applied here.
    """
    with source.open("rb") as fh, mmap.mmap(fh.fileno(), 0, access=mmap.ACCESS_READ) as mm:
        if len(mm) < 32 or mm[:4] != b"\x1a\x45\xdf\xa3":
            raise ValueError("source is not EBML/Matroska")

        segment = mm.find(b"\x18\x53\x80\x67", 0, min(len(mm), 4096))
        if segment < 0:
            raise ValueError("Matroska Segment not found")
        parsed = _ebml_vint(mm, segment + 4)
        if parsed is None:
            raise ValueError("invalid Segment size")
        _segment_size, old_size_len = parsed
        old_segment_data = segment + 4 + old_size_len

        raw: dict[int, bytes] = {}
        clusters: list[tuple[int, bytes]] = []
        cue_points: list[tuple[int, int, int]] = []

        for pos, element_id, _size, payload_start, payload_end in _ebml_children(mm, old_segment_data, len(mm)):
            full = bytes(mm[pos:payload_end])
            if element_id == IDS["Cluster"]:
                clusters.append((pos - old_segment_data, full))
            elif element_id == IDS["Cues"]:
                cue_points = _parse_cues(mm, payload_start, payload_end)
            elif element_id in {IDS["Info"], IDS["Tracks"], IDS["Tags"], IDS["Attachments"]} and element_id not in raw:
                raw[element_id] = full

        if not clusters:
            raise ValueError("canonical Matroska has no Cluster")
        if IDS["Info"] not in raw or IDS["Tracks"] not in raw:
            raise ValueError("canonical Matroska is missing Info/Tracks")

        old_first_cluster = clusters[0][0]
        void = _void88()
        cues = _build_cues(cue_points, 0) if cue_points else _elem(IDS["Cues"], b"")
        seek = b""

        # Seek width and Cue position widths can affect their own offsets. Iterate
        # until the serialized bytes stop changing.
        for _ in range(16):
            cursor = len(seek) + len(void)
            positions: dict[int, int] = {}
            ordered_pre_media: list[tuple[int, bytes]] = []
            for element_id in (IDS["Info"], IDS["Tracks"], IDS["Tags"], IDS["Attachments"]):
                blob = raw.get(element_id)
                if blob:
                    positions[element_id] = cursor
                    ordered_pre_media.append((element_id, blob))
                    cursor += len(blob)

            positions[IDS["Cues"]] = cursor
            cursor += len(cues)
            positions[IDS["Cluster"]] = cursor
            new_first_cluster = cursor
            delta = new_first_cluster - old_first_cluster
            new_cues = _build_cues(cue_points, delta) if cue_points else _elem(IDS["Cues"], b"")
            positions[IDS["Cues"]] = sum(
                [len(seek), len(void)] +
                [len(raw[eid]) for eid in (IDS["Info"], IDS["Tracks"], IDS["Tags"], IDS["Attachments"]) if eid in raw]
            )
            positions[IDS["Cluster"]] = positions[IDS["Cues"]] + len(new_cues)
            new_seek = _seek_head(positions)
            if new_seek == seek and new_cues == cues:
                cues = new_cues
                seek = new_seek
                break
            seek, cues = new_seek, new_cues
        else:
            raise RuntimeError("MTA layout fixed-point did not converge")

        pre_media = bytearray(seek)
        pre_media += void
        for element_id in (IDS["Info"], IDS["Tracks"], IDS["Tags"], IDS["Attachments"]):
            if element_id in raw:
                pre_media += raw[element_id]
        pre_media += cues
        first_cluster_relative = len(pre_media)
        media = b"".join(blob for _old_pos, blob in clusters)

        segment_payload = bytes(pre_media) + media
        # Fixed 8-byte Segment-size VINT makes absolute header size deterministic.
        segment_header = b"\x18\x53\x80\x67" + _size_vint(len(segment_payload), 8)
        prefix = bytes(mm[:segment])
        target.write_bytes(prefix + segment_header + segment_payload)

    return len(prefix) + len(segment_header) + first_cluster_relative
