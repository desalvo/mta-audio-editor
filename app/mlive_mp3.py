from __future__ import annotations

import struct
from pathlib import Path

from .models import Project


def _synchsafe(value: int) -> bytes:
    return bytes(((value >> 21) & 0x7F, (value >> 14) & 0x7F, (value >> 7) & 0x7F, value & 0x7F))


def _frame(frame_id: str, payload: bytes) -> bytes:
    return frame_id.encode("ascii") + struct.pack(">I", len(payload)) + b"\x00\x00" + payload


def _latin1(text: str) -> bytes:
    # ID3v2.3 encoding 0. Merish-class hardware is traditionally tolerant of
    # ISO-8859-1 and this avoids UTF-16/BOM interpretation differences.
    return str(text or "").encode("latin-1", "replace")


def _text_frame(frame_id: str, text: str) -> bytes:
    return _frame(frame_id, b"\x00" + _latin1(text))


def _uslt(text: str, language: str = "ita", descriptor: str = "Lyrics") -> bytes:
    payload = b"\x00" + language.encode("ascii")[:3].ljust(3, b"x")
    payload += _latin1(descriptor) + b"\x00" + _latin1(text)
    return _frame("USLT", payload)


def _sylt(events: list[tuple[int, str]], *, content_type: int, language: str = "ita", descriptor: str) -> bytes:
    # ID3v2.3 SYLT: encoding, language, timestamp format=2 (ms), content type,
    # descriptor, then repeated text<NUL> + timestamp(u32 BE).
    payload = b"\x00" + language.encode("ascii")[:3].ljust(3, b"x") + b"\x02" + bytes((content_type,))
    payload += _latin1(descriptor) + b"\x00"
    for time_ms, text in sorted(events, key=lambda item: (max(0, int(item[0])), item[1])):
        payload += _latin1(text) + b"\x00" + struct.pack(">I", max(0, min(0xFFFFFFFF, int(time_ms))))
    return _frame("SYLT", payload)


def _strip_id3v2(blob: bytes) -> bytes:
    if len(blob) < 10 or blob[:3] != b"ID3":
        return blob
    size_bytes = blob[6:10]
    if any(value & 0x80 for value in size_bytes):
        return blob
    size = (size_bytes[0] << 21) | (size_bytes[1] << 14) | (size_bytes[2] << 7) | size_bytes[3]
    end = 10 + size
    if blob[5] & 0x10:  # footer flag (v2.4; tolerated defensively)
        end += 10
    return blob[end:] if end <= len(blob) else blob


def lyric_events(project: Project) -> list[tuple[int, str]]:
    result: list[tuple[int, str]] = []
    for line in sorted((x for x in project.lyrics if not x.deleted and not x.disabled), key=lambda x: x.time_ms):
        tokens: list[tuple[int, str]] = []
        for word_index, word in enumerate(line.words):
            trailing = " " if word_index < len(line.words) - 1 else ""
            if word.syllables:
                syllables = [(s.start_ms, s.text) for s in word.syllables if s.text]
                if syllables:
                    last_time, last_text = syllables[-1]
                    syllables[-1] = (last_time, last_text + trailing)
                tokens.extend(syllables)
            elif word.text:
                tokens.append((word.start_ms, word.text + trailing))
        if not tokens:
            tokens = [(line.time_ms, line.text)]
        if tokens:
            # Preserve the line boundary inside SYLT without creating a fake timestamp.
            last_time, last_text = tokens[-1]
            tokens[-1] = (last_time, last_text + "\n")
        result.extend(tokens)
    return result


def chord_events(project: Project) -> list[tuple[int, str]]:
    return [
        (chord.time_ms, chord.chord)
        for chord in sorted(project.chords, key=lambda x: x.time_ms)
        if not chord.deleted and not chord.excluded and chord.chord.strip()
    ]


def marker_events(project: Project) -> list[tuple[int, str]]:
    return [
        (marker.time_ms, marker.label)
        for marker in sorted(project.markers, key=lambda x: x.time_ms)
        if not marker.deleted and not marker.disabled and marker.label.strip()
    ]


def embed_mlive_merish_metadata(mp3_path: Path, project: Project) -> Path:
    """Write an ID3v2.3 karaoke profile intended for M-Live/Merish-class devices.

    The audio stream is untouched. Lyrics use SYLT type 1 plus USLT fallback;
    chords use standard SYLT content type 5; markers use SYLT event type 4.
    """
    original = _strip_id3v2(Path(mp3_path).read_bytes())
    lyrics = lyric_events(project)
    chords = chord_events(project)
    markers = marker_events(project)
    full_lyrics = "\n".join(line.text for line in project.lyrics if not line.deleted and not line.disabled)

    frames: list[bytes] = []
    if project.title:
        frames.append(_text_frame("TIT2", project.title))
    if project.artist:
        frames.append(_text_frame("TPE1", project.artist))
    if project.authors:
        frames.append(_text_frame("TCOM", "; ".join(project.authors)))
    if full_lyrics:
        frames.append(_uslt(full_lyrics))
    if lyrics:
        frames.append(_sylt(lyrics, content_type=1, descriptor="MTA Lyrics"))
    if chords:
        frames.append(_sylt(chords, content_type=5, descriptor="MTA Chords"))
    if markers:
        frames.append(_sylt(markers, content_type=4, descriptor="MTA Markers"))
    frames.append(_frame("TXXX", b"\x00MTA Audio Editor profile\x00M-Live/Merish ID3-SYLT"))

    body = b"".join(frames)
    tag = b"ID3\x03\x00\x00" + _synchsafe(len(body)) + body
    Path(mp3_path).write_bytes(tag + original)
    return Path(mp3_path)
