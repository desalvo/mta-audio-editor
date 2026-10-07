from __future__ import annotations

import math
import unicodedata
import zipfile
from pathlib import Path

import fitz

from .models import Project

CDG_COMMAND = 0x09
CDG_MEMORY_PRESET = 0x01
CDG_BORDER_PRESET = 0x02
CDG_TILE_BLOCK = 0x06
CDG_LOAD_CLUT_LOW = 0x1E
CDG_LOAD_CLUT_HIGH = 0x1F
PACKETS_PER_SECOND = 300
WIDTH = 300
HEIGHT = 216
TILE_W = 6
TILE_H = 12
COLS = WIDTH // TILE_W
ROWS = HEIGHT // TILE_H


def _packet(instruction: int = 0, data: bytes = b"") -> bytes:
    payload = bytearray(24)
    if instruction:
        payload[0] = CDG_COMMAND
        payload[1] = instruction & 0x3F
        clipped = bytes((value & 0x3F) for value in data[:16])
        payload[4:4 + len(clipped)] = clipped
    return bytes(payload)


def _color_word(rgb: tuple[int, int, int]) -> int:
    r, g, b = (max(0, min(255, int(v))) >> 4 for v in rgb)
    return (r << 8) | (g << 4) | b


def _clut_packet(instruction: int, colors: list[tuple[int, int, int]]) -> bytes:
    data = bytearray(16)
    for index, rgb in enumerate(colors[:8]):
        value = _color_word(rgb)
        data[index * 2] = (value >> 6) & 0x3F
        data[index * 2 + 1] = value & 0x3F
    return _packet(instruction, bytes(data))


def _latin(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", str(text or ""))
    return "".join(ch for ch in normalized if not unicodedata.combining(ch)).encode("ascii", "replace").decode("ascii")


def _screen_bitmap(project: Project, lyric_text: str, chord_text: str) -> list[list[int]]:
    doc = fitz.open()
    page = doc.new_page(width=WIDTH, height=HEIGHT)
    page.draw_rect(fitz.Rect(0, 0, WIDTH, HEIGHT), color=(0, 0, 0), fill=(0, 0, 0))
    title = _latin(project.title)[:48]
    artist = _latin(project.artist)[:48]
    chord = _latin(chord_text)[:72]
    lyric = _latin(lyric_text)[:160]
    if title:
        page.insert_textbox(fitz.Rect(12, 10, 288, 30), title, fontsize=10, fontname="helv", color=(0.55, 0.8, 1.0), align=1)
    if artist:
        page.insert_textbox(fitz.Rect(12, 29, 288, 47), artist, fontsize=8, fontname="helv", color=(0.55, 0.8, 1.0), align=1)
    if chord:
        page.insert_textbox(fitz.Rect(12, 70, 288, 96), chord, fontsize=15, fontname="hebo", color=(1.0, 0.85, 0.1), align=1)
    if lyric:
        page.insert_textbox(fitz.Rect(12, 105, 288, 198), lyric, fontsize=16, fontname="hebo", color=(1.0, 1.0, 1.0), align=1)
    pix = page.get_pixmap(matrix=fitz.Matrix(1, 1), colorspace=fitz.csRGB, alpha=False)
    samples = pix.samples
    bitmap = [[0] * WIDTH for _ in range(HEIGHT)]
    stride = pix.stride
    for y in range(min(HEIGHT, pix.height)):
        rowoff = y * stride
        for x in range(min(WIDTH, pix.width)):
            off = rowoff + x * 3
            r, g, b = samples[off], samples[off + 1], samples[off + 2]
            if r + g + b < 90:
                continue
            if r > 180 and g > 140 and b < 120:
                bitmap[y][x] = 2
            elif b > r and b > g:
                bitmap[y][x] = 3
            else:
                bitmap[y][x] = 1
    doc.close()
    return bitmap


def _tile_packets(bitmap: list[list[int]]) -> list[bytes]:
    packets: list[bytes] = []
    for row in range(ROWS):
        for col in range(COLS):
            values = {bitmap[y][x] for y in range(row * TILE_H, min((row + 1) * TILE_H, HEIGHT)) for x in range(col * TILE_W, min((col + 1) * TILE_W, WIDTH))}
            values.discard(0)
            if not values:
                continue
            color1 = max(values, key=lambda value: sum(1 for y in range(row * TILE_H, min((row + 1) * TILE_H, HEIGHT)) for x in range(col * TILE_W, min((col + 1) * TILE_W, WIDTH)) if bitmap[y][x] == value))
            data = bytearray(16)
            data[0] = 0
            data[1] = color1 & 0x0F
            data[2] = row & 0x1F
            data[3] = col & 0x3F
            for yy in range(TILE_H):
                bits = 0
                y = row * TILE_H + yy
                if y < HEIGHT:
                    for xx in range(TILE_W):
                        x = col * TILE_W + xx
                        if x < WIDTH and bitmap[y][x] == color1:
                            bits |= 1 << (5 - xx)
                data[4 + yy] = bits & 0x3F
            packets.append(_packet(CDG_TILE_BLOCK, bytes(data)))
    return packets


def _active_chord(project: Project, time_ms: int) -> str:
    events = sorted((c for c in project.chords if not c.excluded and not c.deleted), key=lambda c: c.time_ms)
    current = ""
    for chord in events:
        if chord.time_ms > time_ms:
            break
        current = chord.chord
    return current


def build_cdg(project: Project, out: Path, duration_ms: int) -> Path:
    """Build a conservative CD+G graphics stream synchronized to lyric lines and chords."""
    total_packets = max(1, math.ceil(max(1000, duration_ms) / 1000 * PACKETS_PER_SECOND))
    packets = [_packet() for _ in range(total_packets)]
    setup = [
        _clut_packet(CDG_LOAD_CLUT_LOW, [(0, 0, 0), (255, 255, 255), (255, 220, 24), (96, 194, 255), (0, 0, 0), (0, 0, 0), (0, 0, 0), (0, 0, 0)]),
        _clut_packet(CDG_LOAD_CLUT_HIGH, [(0, 0, 0)] * 8),
        _packet(CDG_MEMORY_PRESET, bytes([0, 0])),
        _packet(CDG_BORDER_PRESET, bytes([0])),
    ]
    for idx, pack in enumerate(setup):
        if idx < len(packets):
            packets[idx] = pack
    lyrics = sorted((line for line in project.lyrics if not line.disabled and not line.deleted and str(line.text).strip()), key=lambda line: line.time_ms)
    if not lyrics:
        lyrics = []
    for line in lyrics:
        screen = _screen_bitmap(project, line.text, _active_chord(project, int(line.time_ms)))
        commands = [_packet(CDG_MEMORY_PRESET, bytes([0, 0]))] + _tile_packets(screen)
        # Pre-roll enough packets so the screen is complete by the lyric timestamp.
        start = max(len(setup), int(line.time_ms / 1000 * PACKETS_PER_SECOND) - len(commands))
        for offset, pack in enumerate(commands):
            pos = start + offset
            if pos >= len(packets):
                break
            packets[pos] = pack
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(b"".join(packets))
    return out


def build_mp3g_zip(project: Project, mp3_path: Path, out_zip: Path, basename: str, duration_ms: int) -> Path:
    safe = basename.strip() or "karaoke"
    cdg_path = out_zip.with_suffix(".cdg.tmp")
    build_cdg(project, cdg_path, duration_ms)
    with zipfile.ZipFile(out_zip, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.write(mp3_path, f"{safe}.mp3")
        archive.write(cdg_path, f"{safe}.cdg")
    cdg_path.unlink(missing_ok=True)
    return out_zip
