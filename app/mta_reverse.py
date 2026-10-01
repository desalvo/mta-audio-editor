"""Conservative reverse-engineering helpers for M-Live MTA containers.

The module reports only structures that can be demonstrated from the bytes.  It
never rewrites undocumented proprietary payloads speculatively.  Known wrappers
(ID3v2.3, Lyrics3-like sections and MtxInfoData XML) are decoded while opaque
payload bytes remain fingerprinted and round-trip safe.
"""
from __future__ import annotations

import hashlib
import json
import logging
import math
import mmap
import re
import struct
import subprocess
import tempfile
from defusedxml import ElementTree as ET
from collections import Counter
from pathlib import Path

LOGGER = logging.getLogger(__name__)

PRINTABLE_RE = re.compile(rb"[\x20-\x7e]{4,}")
SECTION_NAMES = ("LYRICS", "COLORS", "MIDITK", "CHORDS")
SECTION_FOOTER_RE = re.compile(rb"([0-9]{6})(LYRICS|COLORS|MIDITK|CHORDS)200\r?\n?")


def _run(cmd: list[str]) -> str:
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if proc.returncode:
        raise RuntimeError(proc.stderr.strip() or "analysis command failed")
    return proc.stdout


def probe(path: Path) -> dict:
    return json.loads(_run(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)]))


def _entropy(data: bytes) -> float:
    if not data:
        return 0.0
    counts = Counter(data)
    n = len(data)
    return -sum((c / n) * math.log2(c / n) for c in counts.values())


def _utf16_strings(data: bytes, little: bool) -> list[str]:
    enc = "utf-16-le" if little else "utf-16-be"
    out: list[str] = []
    for offset in (0, 1):
        chunk = data[offset:]
        chunk = chunk[: len(chunk) - (len(chunk) % 2)]
        text = chunk.decode(enc, errors="ignore")
        for item in re.findall(r"[ -~À-ÿ]{4,}", text):
            item = item.strip()
            if item and item not in out:
                out.append(item[:240])
            if len(out) >= 40:
                return out
    return out


def _timestamp_candidates(data: bytes, max_ms: int = 6 * 60 * 60 * 1000) -> dict[str, list[dict]]:
    result: dict[str, list[dict]] = {"u32le": [], "u32be": []}
    for name, fmt in (("u32le", "<I"), ("u32be", ">I")):
        last = -1
        for off in range(0, max(0, len(data) - 3), 4):
            value = struct.unpack_from(fmt, data, off)[0]
            if 0 <= value <= max_ms and (value == 0 or value >= last):
                if value == 0 or value - last <= 10 * 60 * 1000:
                    result[name].append({"offset": off, "value_ms": value})
                    last = value
                    if len(result[name]) >= 80:
                        break
    return result


def _synchsafe(value: bytes) -> int:
    if len(value) != 4 or any(x & 0x80 for x in value):
        return 0
    return (value[0] << 21) | (value[1] << 14) | (value[2] << 7) | value[3]


def _decode_id3_text(payload: bytes) -> str | None:
    if not payload:
        return None
    encodings = {0: "latin-1", 1: "utf-16", 2: "utf-16-be", 3: "utf-8"}
    enc = encodings.get(payload[0])
    if not enc:
        return None
    try:
        return payload[1:].decode(enc, errors="replace").rstrip("\x00")
    except (UnicodeDecodeError, LookupError):
        return None



def _decode_colors_observed(body: bytes) -> dict | None:
    """Decode the timing-like fields observed consistently in four real M-Live samples.

    This is intentionally read-only evidence.  It derives a 256-byte XOR keystream
    from record byte 0, removes the observed global 0x0A offset and validates that
    byte positions 1/2/4/5/9 become decimal digits.  The resulting five digits
    behave as a modulo-60000 time field; unwrap is therefore reported as a
    *candidate* timeline, not an authoring contract.
    """
    if len(body) < 3 + 257 * 15 or (len(body) - 3) % 15:
        return None
    records = [body[i:i + 15] for i in range(3, len(body), 15)]
    if len(records) < 257:
        return None
    normal = records[:-1]
    key_prime = [records[i][0] for i in range(256)]
    digit_offsets = (1, 2, 4, 5, 9)
    decoded = []
    valid_digits = 0
    for i, record in enumerate(normal):
        plain = []
        for j, value in enumerate(record):
            phase = (i - 17 * j) % 256
            plain.append(value ^ key_prime[phase] ^ 0x0A)
        digits = [plain[j] for j in digit_offsets]
        valid = all(0 <= x <= 9 for x in digits)
        if valid:
            valid_digits += 1
            mod_value = int("".join(str(x) for x in digits))
        else:
            mod_value = None
        decoded.append({
            "index": i,
            "time_mod_60000_candidate": mod_value,
            "state_7": plain[7],
            "state_8": plain[8],
            "state_14": plain[14],
        })
    if valid_digits != len(normal):
        return {
            "decoder": "observed-keystream-v1",
            "validated": False,
            "valid_decimal_event_fraction": round(valid_digits / max(1, len(normal)), 6),
        }
    base = 0
    previous = None
    negative_small = 0
    wraps = []
    for event in decoded:
        value = event["time_mod_60000_candidate"]
        if previous is not None and value < previous - 20_000:
            base += 60_000
            wraps.append(event["index"])
        elif previous is not None and value < previous:
            negative_small += 1
        event["unwrapped_time_ms_candidate"] = base + value
        previous = value
    return {
        "decoder": "observed-keystream-v1",
        "validated": True,
        "corpus_basis": 4,
        "keystream_period_bytes": 256,
        "keystream_phase_formula": "(record_index - 17 * byte_index) mod 256",
        "global_xor": 10,
        "decimal_digit_offsets": list(digit_offsets),
        "modulus": 60000,
        "wrap_event_indices": wraps,
        "small_backward_jitter_count": negative_small,
        "first_time_ms_candidate": decoded[0]["unwrapped_time_ms_candidate"] if decoded else None,
        "last_time_ms_candidate": decoded[-1]["unwrapped_time_ms_candidate"] if decoded else None,
        "events": decoded,
        "confidence_note": (
            "The decimal/modulo-60000 behavior and 256-byte keystream are consistent across four independent real M-Live files. "
            "Exact field semantics and writer compatibility are not yet claimed."
        ),
    }


def _decode_variable_section_observed(body: bytes, key_prime: list[int], *, section: str) -> dict | None:
    """Read-only decoder for observed M-Live LYRICS/CHORDS records.

    Four independent stock files share the COLORS-derived 256-byte keystream.
    After the common 3-byte prefix, its phase advances continuously per byte as
    ``239 * flat_offset mod 256``. Decrypted records end in ``=:k\x00X``.
    X is the *minute block for the following record*. The four decimal digits in
    bytes 1/2/4/5 are centiseconds within the current minute, yielding
    ``time_ms = (minute * 6000 + dddd) * 10``. Text/chord bytes after marker
    0x6d use an additional XOR 0x30 character transform.

    This exposes corpus-verified evidence for read-only analysis and deliberately
    makes no writer compatibility promise.
    """
    if section not in {"LYRICS", "CHORDS"} or len(body) < 4 or body[:3] != b"\x28\xb6\xa9":
        return None
    if len(key_prime) != 256:
        return None

    cipher = body[3:]
    plain = bytes(
        value ^ key_prime[(239 * offset) % 256] ^ 0x0A
        for offset, value in enumerate(cipher)
    )
    delimiter = re.compile(rb"=:k\x00(.)", re.DOTALL)
    records = []
    start = 0
    valid_layout = 0
    current_minute = 0
    previous_time_ms = None
    monotonic = True
    for index, match in enumerate(delimiter.finditer(plain)):
        raw = plain[start:match.start()]
        start = match.end()
        next_minute = match.group(1)[0]
        item = {
            "index": index,
            "minute_block": current_minute,
            "next_minute_block": next_minute,
            "decoded_size": len(raw),
            "decoded_hex": raw.hex(),
        }
        # Observed record header: LF d d RS d d 'm' ...
        if (
            len(raw) >= 7
            and raw[0] == 0x0A
            and raw[3] == 0x1E
            and raw[6] == 0x6D
            and all(0 <= raw[pos] <= 9 for pos in (1, 2, 4, 5))
        ):
            valid_layout += 1
            centiseconds = raw[1] * 1000 + raw[2] * 100 + raw[4] * 10 + raw[5]
            time_ms = (current_minute * 6000 + centiseconds) * 10
            item["centiseconds_within_minute"] = centiseconds
            item["time_ms"] = time_ms
            # Compatibility alias retained for analysis consumers created during reverse engineering.
            item["decimal_index_candidate"] = centiseconds
            if previous_time_ms is not None and time_ms < previous_time_ms:
                monotonic = False
            previous_time_ms = time_ms
            encoded_text = raw[7:]
            if section == "LYRICS" and encoded_text.endswith(b"0"):
                encoded_text = encoded_text[:-1]
            transformed = bytes(value ^ 0x30 for value in encoded_text)
            item["text"] = transformed.decode("latin-1", errors="replace")
            item["character_xor"] = 0x30
        records.append(item)
        current_minute = next_minute

    tail = plain[start:]
    times = [r["time_ms"] for r in records if "time_ms" in r]
    terminal_marker = b"=:0=:"
    return {
        "decoder": "observed-variable-section-v2",
        "validated": bool(records) and valid_layout == len(records) and monotonic,
        "corpus_basis": 4,
        "section": section,
        "binary_header_hex": body[:3].hex(),
        "keystream_period_bytes": 256,
        "keystream_phase_formula": "239 * flat_payload_offset mod 256",
        "global_xor": 10,
        "character_xor": 48,
        "record_delimiter_hex": "3d3a6b00XX",
        "delimiter_semantics": "XX is the minute block used by the following record",
        "timing_formula": "time_ms = (minute_block * 6000 + centiseconds_within_minute) * 10",
        "record_count": len(records),
        "valid_record_layout_count": valid_layout,
        "timing_monotonic": monotonic if times else None,
        "first_time_ms": times[0] if times else None,
        "last_time_ms": times[-1] if times else None,
        "records": records,
        "tail_size": len(tail),
        "tail_hex": tail.hex(),
        "terminal_marker_present": terminal_marker in tail,
        "confidence_note": (
            "The shared keystream, record delimiter, centisecond-within-minute timing, minute carry and XOR-0x30 text/chord transform "
            "are monotonic and consistent across four independent stock M-Live files. Writer compatibility is not yet claimed."
        ),
    }

def inspect_proprietary_sections(data: bytes) -> dict[str, dict]:
    """Parse the demonstrated Lyrics3-like wrappers without decoding opaque bodies."""
    sections: dict[str, dict] = {}
    raw_bodies: dict[str, bytes] = {}
    for name in SECTION_NAMES:
        marker = (name + "BEGIN").encode()
        start = data.find(marker)
        if start < 0:
            continue
        header_pos = start + len(marker)
        m = re.match(rb"IND([0-9]{5})(.{0,99999}?)LYR([0-9]{5})\r\n", data[header_pos:], re.DOTALL)
        if not m:
            sections[name] = {"offset": start, "wrapper_parsed": False}
            continue
        ind_declared = int(m.group(1))
        ind_payload = m.group(2)[:ind_declared]
        lyr_declared = int(m.group(3))
        body_start = header_pos + m.end()
        footer = None
        for fm in SECTION_FOOTER_RE.finditer(data, body_start):
            if fm.group(2).decode() == name:
                footer = fm
                break
        if footer is None:
            sections[name] = {
                "offset": start,
                "wrapper_parsed": True,
                "ind_declared_size": ind_declared,
                "ind_payload_hex": ind_payload.hex(),
                "lyr_declared_size": lyr_declared,
                "payload_offset": body_start,
                "footer_found": False,
            }
            continue
        body_end = footer.start()
        body = data[body_start:body_end]
        raw_bodies[name] = body
        footer_declared = int(footer.group(1))
        item = {
            "offset": start,
            "wrapper_parsed": True,
            "ind_declared_size": ind_declared,
            "ind_payload_hex": ind_payload.hex(),
            "lyr_declared_size": lyr_declared,
            "payload_offset": body_start,
            "payload_size": len(body),
            "payload_sha256": hashlib.sha256(body).hexdigest(),
            "payload_entropy_bits_per_byte": round(_entropy(body), 4),
            "footer_offset": footer.start(),
            "footer_declared_size": footer_declared,
            "declared_payload_size_matches_actual": lyr_declared == len(body),
            "footer_size_matches_wrapper_plus_payload": footer_declared == (body_start - start + len(body)),
        }
        if name == "COLORS" and len(body) >= 18 and (len(body) - 3) % 15 == 0:
            records = [body[i:i + 15] for i in range(3, len(body), 15)]
            item["colors_structure"] = {
                "binary_header_hex": body[:3].hex(),
                "record_size": 15,
                "record_count": len(records),
                "normal_event_count": max(0, len(records) - 1),
                "has_distinct_terminal_record": len(records) > 1,
                "terminal_record_hex": records[-1].hex() if records else "",
                "observed_timing_decoder": _decode_colors_observed(body),
                "observation": (
                    "Four independent real-world samples use a 3-byte prefix followed by 15-byte records; "
                    "the final record is structurally distinct. A read-only timing-like decoder is exposed only when its decimal invariants validate."
                ),
            }
        sections[name] = item

    colors_body = raw_bodies.get("COLORS")
    if colors_body and len(colors_body) >= 3 + 257 * 15 and (len(colors_body) - 3) % 15 == 0:
        color_records = [colors_body[i:i + 15] for i in range(3, len(colors_body), 15)]
        key_prime = [color_records[i][0] for i in range(256)]
        for name in ("LYRICS", "CHORDS"):
            body = raw_bodies.get(name)
            if body and name in sections:
                decoded = _decode_variable_section_observed(body, key_prime, section=name)
                if decoded is not None:
                    sections[name]["observed_record_decoder"] = decoded
    return sections


def inspect_embedded_id3(data: bytes) -> dict | None:
    """Inspect an ID3v2.3 block embedded in a proprietary SYL attachment."""
    start = data.find(b"ID3")
    if start < 0 or start + 10 > len(data):
        return None
    major, minor, flags = data[start + 3], data[start + 4], data[start + 5]
    tag_size = _synchsafe(data[start + 6:start + 10])
    end = min(len(data), start + 10 + tag_size)
    frames = []
    pos = start + 10
    if major == 3:
        while pos + 10 <= end:
            frame_id = data[pos:pos + 4]
            if frame_id == b"\x00\x00\x00\x00" or not all(0x20 <= x <= 0x7E for x in frame_id):
                break
            size = struct.unpack(">I", data[pos + 4:pos + 8])[0]
            frame_flags = data[pos + 8:pos + 10].hex()
            payload_start = pos + 10
            payload_end = min(end, payload_start + size)
            payload = data[payload_start:payload_end]
            fid = frame_id.decode("ascii", errors="replace")
            entry = {
                "id": fid,
                "offset": pos,
                "size": size,
                "flags_hex": frame_flags,
                "payload_sha256": hashlib.sha256(payload).hexdigest(),
                "ascii_preview": " | ".join(
                    x.group().decode("ascii", errors="replace")[:120] for x in PRINTABLE_RE.finditer(payload[:8192])
                )[:600],
            }
            if fid.startswith("T") and fid != "TXXX":
                decoded = _decode_id3_text(payload)
                if decoded is not None:
                    entry["text"] = decoded
            frames.append(entry)
            if size <= 0:
                break
            pos = payload_start + size
    tag_data = data[start:end]
    proprietary = inspect_proprietary_sections(tag_data)
    labels = {}
    for label in (b"LYRICS", b"CHORDS", b"COLORS", b"MIDITK", b"MARKER"):
        offsets = []
        at = 0
        while True:
            at = tag_data.find(label, at)
            if at < 0:
                break
            offsets.append(at)
            at += len(label)
            if len(offsets) >= 64:
                break
        if offsets:
            labels[label.decode()] = offsets
    delta_start = data.find(b"DELTABEGIN", start, end)
    delta_end = data.find(b"DELTAEND", delta_start + 10, end) if delta_start >= 0 else -1
    return {
        "offset": start,
        "version": f"2.{major}.{minor}",
        "flags": flags,
        "declared_size": tag_size,
        "total_tag_size": min(len(data) - start, 10 + tag_size),
        "frames": frames,
        "delta": {
            "present": delta_start >= 0 and delta_end >= 0,
            "offset": delta_start - start if delta_start >= 0 else None,
            "payload_hex": data[delta_start + 10:delta_end].hex() if delta_start >= 0 and delta_end >= 0 else None,
        },
        "proprietary_sections": proprietary,
        "proprietary_section_labels": labels,
    }


def inspect_mtx_xml(data: bytes) -> dict | None:
    root_end_marker = b"</MtxInfoData>"
    end = data.find(root_end_marker)
    if end < 0:
        return None
    xml_end = end + len(root_end_marker)
    if xml_end < len(data) and data[xml_end:xml_end + 1] == b"\n":
        xml_end += 1
    raw_xml = data[:xml_end]
    try:
        root = ET.fromstring(raw_xml)
    except ET.ParseError:
        return None

    def child_text(parent: ET.Element | None, name: str) -> str:
        if parent is None:
            return ""
        node = parent.find(name)
        return (node.text or "").strip() if node is not None else ""

    identity_node = root.find("Identity")
    general_node = root.find("General")
    duration_text = child_text(general_node, "DurataSec")
    try:
        duration_sec = int(duration_text)
    except ValueError:
        duration_sec = None
    tracks = []
    trk_audio = root.find("TrkAudio")
    if trk_audio is not None:
        for track in trk_audio.findall("Track"):
            note_raw = child_text(track, "NoteOn")
            values = [x.strip() for x in note_raw.split(";") if x.strip() != ""]
            bits = [int(x) for x in values if x in {"0", "1"}]
            tracks.append({
                "num": child_text(track, "Num"),
                "name": child_text(track, "Nome"),
                "type": child_text(track, "Type"),
                "routing": child_text(track, "Routing"),
                "volume": child_text(track, "Volume"),
                "mute_solo": child_text(track, "MuteSolo"),
                "note_on_count": len(values),
                "note_on_binary_count": len(bits),
                "note_on_active_count": sum(bits),
                "note_on_matches_duration_seconds": duration_sec is not None and len(values) == duration_sec,
                "note_on_duration_delta": (len(values) - duration_sec) if duration_sec is not None else None,
                "note_on_is_second_scale_vector": duration_sec is not None and len(values) in {duration_sec, max(0, duration_sec - 1)},
            })
    padding = data[xml_end:]
    return {
        "root": root.tag,
        "version": root.attrib.get("version"),
        "xml_size": xml_end,
        "padding_size": len(padding),
        "padding_all_zero": bool(padding) and all(x == 0 for x in padding),
        "identity": {
            "user_id": child_text(identity_node, "UserId"),
            "apro_id": child_text(identity_node, "AProId"),
        },
        "general": {
            "base_key": child_text(general_node, "BaseKey"),
            "base_bpm": child_text(general_node, "BaseBpm"),
            "duration_sec": duration_sec,
            "pre_count_usec": child_text(general_node, "PreCntUSec"),
        },
        "tracks": tracks,
        "note_on_observation": (
            "Across verified real-world samples the vector length is DurataSec or DurataSec-1, consistent with second-scale bins "
            "and endpoint convention differences. The exact threshold/semantic used by the original writer remains undocumented."
        ),
    }


def analyze_blob(data: bytes, filename: str = "attachment.bin") -> dict:
    magic = data[:32].hex()
    ascii_strings = [m.group().decode("ascii", errors="replace")[:240] for m in PRINTABLE_RE.finditer(data[:2_000_000])][:80]
    lower_name = filename.lower()
    looks_syl = lower_name.endswith(".syl") or data.startswith(b"ID3")
    looks_xml = lower_name.endswith(".xml") or b"<MtxInfoData" in data[:4096]
    return {
        "filename": filename,
        "size": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
        "entropy_bits_per_byte": round(_entropy(data), 4),
        "magic_hex": magic,
        "looks_like_syl": looks_syl,
        "looks_like_mtx_xml": looks_xml,
        "ascii_strings": ascii_strings,
        "utf16le_strings": _utf16_strings(data[:2_000_000], True),
        "utf16be_strings": _utf16_strings(data[:2_000_000], False),
        "timestamp_candidates": _timestamp_candidates(data[:1_000_000]),
        "embedded_id3": inspect_embedded_id3(data) if looks_syl else None,
        "mtx_xml": inspect_mtx_xml(data) if looks_xml else None,
    }


def _ebml_vint(data: mmap.mmap, pos: int) -> tuple[int, int] | None:
    if pos >= len(data):
        return None
    first = data[pos]
    mask = 0x80
    length = 1
    while length <= 8 and not (first & mask):
        mask >>= 1
        length += 1
    if length > 8 or pos + length > len(data):
        return None
    value = first & (mask - 1)
    for i in range(1, length):
        value = (value << 8) | data[pos + i]
    return value, length


def _scan_matroska_filedata(path: Path, expected_sizes: list[int]) -> list[bytes]:
    """Fallback for MTA files whose non-canonical EBML confuses ffmpeg attachment dumping.

    FileData is Matroska element 0x465c.  Candidates are accepted only when their
    EBML size matches an attachment extradata_size reported by ffprobe, reducing
    false positives in audio payloads.
    """
    if not expected_sizes:
        return []
    wanted = Counter(x for x in expected_sizes if x > 0)
    results: list[bytes] = []
    with path.open("rb") as fh, mmap.mmap(fh.fileno(), 0, access=mmap.ACCESS_READ) as mm:
        pos = 0
        while wanted and pos < len(mm):
            hit = mm.find(b"\x46\x5c", pos)
            if hit < 0:
                break
            parsed = _ebml_vint(mm, hit + 2)
            if parsed:
                size, vint_len = parsed
                start = hit + 2 + vint_len
                end = start + size
                if size in wanted and end <= len(mm):
                    results.append(bytes(mm[start:end]))
                    wanted[size] -= 1
                    if wanted[size] <= 0:
                        del wanted[size]
                    pos = end
                    continue
            pos = hit + 2
    return results


def extract_attachments(path: Path, output_dir: Path) -> list[dict]:
    info = probe(path)
    output_dir.mkdir(parents=True, exist_ok=True)
    found: list[dict] = []
    attachments = [s for s in info.get("streams", []) if s.get("codec_type") == "attachment"]
    fallback_payloads: list[bytes] | None = None
    for ordinal, stream in enumerate(attachments):
        tags = stream.get("tags") or {}
        raw_name = tags.get("filename") or f"attachment-{stream.get('index', ordinal)}.bin"
        safe = "".join(c for c in raw_name if c.isalnum() or c in "._-") or f"attachment-{ordinal}.bin"
        target = output_dir / f"{ordinal + 1:02d}-{safe}"
        method = "ffmpeg"
        try:
            _run(["ffmpeg", "-y", "-v", "error", f"-dump_attachment:t:{ordinal}", str(target), "-i", str(path), "-f", "null", "-"])
        except Exception as exc:
            LOGGER.warning("ffmpeg attachment extraction failed for %s attachment %d: %s", path, ordinal, exc)
        if not target.exists():
            if fallback_payloads is None:
                sizes = [int(s.get("extradata_size") or 0) for s in attachments]
                fallback_payloads = _scan_matroska_filedata(path, sizes)
            if ordinal < len(fallback_payloads):
                target.write_bytes(fallback_payloads[ordinal])
                method = "ebml-filedata-fallback"
            else:
                continue
        if target.exists():
            item = analyze_blob(target.read_bytes(), raw_name)
            item["stream_index"] = stream.get("index")
            item["tags"] = tags
            item["local_filename"] = target.name
            item["extraction_method"] = method
            found.append(item)
    return found


def analyze_mta(path: Path, attachment_dir: Path | None = None) -> dict:
    info = probe(path)
    if attachment_dir is None:
        with tempfile.TemporaryDirectory() as td:
            attachments = extract_attachments(path, Path(td))
    else:
        attachments = extract_attachments(path, attachment_dir)
    audio = []
    for s in info.get("streams", []):
        if s.get("codec_type") == "audio":
            audio.append({
                "index": s.get("index"),
                "codec_name": s.get("codec_name"),
                "sample_rate": s.get("sample_rate"),
                "channels": s.get("channels"),
                "channel_layout": s.get("channel_layout"),
                "bit_rate": s.get("bit_rate"),
                "duration": s.get("duration"),
                "tags": s.get("tags") or {},
            })
    by_original_name: dict[str, list[dict]] = {}
    for item in attachments:
        by_original_name.setdefault(item["filename"], []).append(item)
    duplicate_pairs = {
        name: len({x["sha256"] for x in items}) == 1
        for name, items in by_original_name.items()
        if len(items) > 1
    }
    return {
        "schema": "mta-audio-editor/reverse-analysis-v2",
        "file": {"name": path.name, "size": path.stat().st_size, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()},
        "format": info.get("format") or {},
        "audio_streams": audio,
        "attachments": attachments,
        "observations": {
            "container_is_matroska": "matroska" in str((info.get("format") or {}).get("format_name", "")).lower(),
            "syl_candidates": [a["filename"] for a in attachments if a.get("looks_like_syl")],
            "duplicate_attachment_names_are_byte_identical": duplicate_pairs,
            "proprietary_semantics_are_conservative": True,
        },
    }


def diff_blobs(a: bytes, b: bytes) -> dict:
    same_prefix = 0
    for x, y in zip(a, b):
        if x != y:
            break
        same_prefix += 1
    same_suffix = 0
    for x, y in zip(reversed(a), reversed(b)):
        if x != y or same_suffix >= min(len(a), len(b)) - same_prefix:
            break
        same_suffix += 1
    changed = []
    limit = min(len(a), len(b))
    start = None
    for i in range(limit):
        if a[i] != b[i] and start is None:
            start = i
        elif a[i] == b[i] and start is not None:
            changed.append({"start": start, "end": i, "length": i - start})
            start = None
            if len(changed) >= 200:
                break
    if start is not None and len(changed) < 200:
        changed.append({"start": start, "end": limit, "length": limit - start})
    if len(a) != len(b) and len(changed) < 200:
        changed.append({"start": limit, "end": max(len(a), len(b)), "length": abs(len(a) - len(b)), "size_change": len(b) - len(a)})
    return {
        "size_a": len(a),
        "size_b": len(b),
        "sha256_a": hashlib.sha256(a).hexdigest(),
        "sha256_b": hashlib.sha256(b).hexdigest(),
        "common_prefix_bytes": same_prefix,
        "common_suffix_bytes": same_suffix,
        "changed_ranges": changed,
    }
