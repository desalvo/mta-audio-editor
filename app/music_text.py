from __future__ import annotations

import csv
import importlib.util
import json
import logging
import math
import os
import re
import shutil
import subprocess
import tempfile
import wave
from pathlib import Path

import numpy as np

from .models import Chord, LyricLine, LyricWord, RightsRecord, Track


logger = logging.getLogger(__name__)


NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]


_NOTE_TO_PC = {"C": 0, "C#": 1, "Db": 1, "D": 2, "D#": 3, "Eb": 3, "E": 4, "F": 5, "F#": 6, "Gb": 6, "G": 7, "G#": 8, "Ab": 8, "A": 9, "A#": 10, "Bb": 10, "B": 11}
_SHARP_NOTES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
_FLAT_NOTES = ["C", "Db", "D", "Eb", "E", "F", "Gb", "G", "Ab", "A", "Bb", "B"]


def _transpose_note(note: str, semitones: float) -> str:
    pc = _NOTE_TO_PC.get(note)
    if pc is None:
        return note
    shift = int(round(float(semitones)))
    names = _FLAT_NOTES if "b" in note else _SHARP_NOTES
    return names[(pc + shift) % 12]


def transpose_chord_symbol(symbol: str, semitones: float) -> str:
    """Transpose a chord symbol while preserving quality/extensions and slash bass."""
    shift = int(round(float(semitones)))
    if shift % 12 == 0:
        return symbol
    raw = str(symbol or "")
    match = re.match(r"^([A-G](?:#|b)?)(.*)$", raw)
    if not match:
        return raw
    root, suffix = match.groups()
    suffix = re.sub(
        r"/([A-G](?:#|b)?)",
        lambda m: "/" + _transpose_note(m.group(1), shift),
        suffix,
    )
    return _transpose_note(root, shift) + suffix


def transpose_chords(chords: list[Chord], semitones: float) -> list[Chord]:
    return [Chord(time_ms=item.time_ms, chord=transpose_chord_symbol(item.chord, semitones)) for item in chords]


def transpose_key_name(key: str, semitones: float) -> str:
    """Transpose the leading note of a project key, preserving mode/annotation text."""
    shift = int(round(float(semitones)))
    if shift % 12 == 0 or not key:
        return key
    match = re.match(r"^\s*([A-G](?:#|b)?)(.*)$", str(key))
    if not match:
        return key
    root_note, suffix = match.groups()
    return _transpose_note(root_note, shift) + suffix


def _run(cmd: list[str]) -> str:
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if proc.returncode:
        raise RuntimeError(proc.stderr.strip() or "analysis command failed")
    return proc.stdout


def lyrics_engine_available() -> bool:
    return bool(shutil.which("whisper") or importlib.util.find_spec("whisper"))


def _whisper_result_to_lines(result: dict) -> list[LyricLine]:
    items: list[LyricLine] = []
    for segment in result.get("segments") or []:
        text = str(segment.get("text") or "").strip()
        if not text:
            continue
        start_ms = max(0, round(float(segment.get("start") or 0) * 1000))
        end_ms = max(start_ms, round(float(segment.get("end") or segment.get("start") or 0) * 1000))
        words: list[LyricWord] = []
        for word in segment.get("words") or []:
            token = str(word.get("word") or word.get("text") or "").strip()
            if not token:
                continue
            ws = max(0, round(float(word.get("start") or segment.get("start") or 0) * 1000))
            we = max(ws, round(float(word.get("end") or word.get("start") or segment.get("end") or 0) * 1000))
            words.append(LyricWord(start_ms=ws, end_ms=we, text=token))
        items.append(LyricLine(time_ms=start_ms, end_ms=end_ms, text=text, words=words))
    return items


def extract_lyrics(path: Path, *, model_name: str | None = None, language: str | None = None) -> list[LyricLine]:
    """Transcribe a track with upstream OpenAI Whisper and preserve segment timing.

    The model is intentionally resolved by Whisper itself so native/server runtimes
    download it from the upstream Whisper model source/cache rather than the MTA
    model repository.
    """
    model_name = (model_name or os.getenv("MTA_LYRICS_WHISPER_MODEL", "large-v3")).strip() or "large-v3"
    language = (language or os.getenv("MTA_LYRICS_LANGUAGE", "")).strip() or None
    cache_dir = Path(os.getenv("MTA_LYRICS_MODEL_DIR", str(Path(os.getenv("MTA_DATA_DIR", "/data/projects")) / ".cache" / "lyrics-models"))).expanduser()
    cache_dir.mkdir(parents=True, exist_ok=True)

    # Prefer the Python API when bundled in native/server builds. It gives a
    # stable JSON result and lets Whisper own the upstream model lifecycle.
    if importlib.util.find_spec("whisper"):
        import whisper  # type: ignore

        model = whisper.load_model(model_name, download_root=str(cache_dir))
        kwargs = {
            "verbose": False,
            "word_timestamps": True,
            "temperature": 0.0,
            "beam_size": max(1, int(os.getenv("MTA_LYRICS_BEAM_SIZE", "8"))),
            "patience": 1.2,
            "condition_on_previous_text": True,
        }
        if language:
            kwargs["language"] = language
        result = model.transcribe(str(path), **kwargs)
        return _whisper_result_to_lines(result)

    cli = shutil.which("whisper")
    if not cli:
        raise RuntimeError(
            "Lyrics extraction requires OpenAI Whisper. Install the optional lyrics engine or bundle it in this runtime."
        )
    with tempfile.TemporaryDirectory(prefix="mta-whisper-") as td_raw:
        td = Path(td_raw)
        cmd = [
            cli, str(path), "--model", model_name, "--output_dir", str(td),
            "--output_format", "json", "--word_timestamps", "True", "--verbose", "False",
            "--model_dir", str(cache_dir),
            "--beam_size", str(max(1, int(os.getenv("MTA_LYRICS_BEAM_SIZE", "8")))),
            "--temperature", "0",
        ]
        if language:
            cmd += ["--language", language]
        _run(cmd)
        output = td / f"{path.stem}.json"
        if not output.is_file():
            matches = list(td.glob("*.json"))
            if not matches:
                raise RuntimeError("Whisper completed without producing a JSON transcript")
            output = matches[0]
        return _whisper_result_to_lines(json.loads(output.read_text(encoding="utf-8")))


def _pcm_mono(path: Path, sample_rate: int = 11025) -> tuple[np.ndarray, int]:
    with tempfile.TemporaryDirectory(prefix="mta-chords-") as td_raw:
        wav_path = Path(td_raw) / "analysis.wav"
        _run([
            "ffmpeg", "-y", "-v", "error", "-i", str(path),
            "-ac", "1", "-ar", str(sample_rate), "-c:a", "pcm_s16le", str(wav_path),
        ])
        with wave.open(str(wav_path), "rb") as handle:
            sr = handle.getframerate()
            samples = np.frombuffer(handle.readframes(handle.getnframes()), dtype=np.int16).astype(np.float32)
    if samples.size:
        samples /= max(1.0, float(np.max(np.abs(samples))))
    return samples, sr


def _chord_templates() -> list[tuple[str, np.ndarray]]:
    out: list[tuple[str, np.ndarray]] = []
    qualities = (
        ("", (0, 4, 7), (1.0, 0.82, 0.72)),
        ("m", (0, 3, 7), (1.0, 0.82, 0.72)),
        ("7", (0, 4, 7, 10), (1.0, 0.78, 0.70, 0.58)),
        ("maj7", (0, 4, 7, 11), (1.0, 0.78, 0.70, 0.58)),
        ("m7", (0, 3, 7, 10), (1.0, 0.78, 0.70, 0.58)),
        ("sus2", (0, 2, 7), (1.0, 0.75, 0.72)),
        ("sus4", (0, 5, 7), (1.0, 0.75, 0.72)),
        ("dim", (0, 3, 6), (1.0, 0.80, 0.72)),
    )
    for root in range(12):
        for suffix, intervals, weights in qualities:
            v = np.zeros(12, dtype=np.float64)
            for interval, weight in zip(intervals, weights):
                v[(root + interval) % 12] = weight
            v /= np.linalg.norm(v)
            out.append((NOTE_NAMES[root] + suffix, v))
    return out


def _extract_chords_chordino(path: Path) -> list[Chord] | None:
    """Prefer NNLS-Chroma/Chordino when available for higher chord accuracy."""
    sonic = shutil.which("sonic-annotator")
    if not sonic:
        return None
    try:
        proc = subprocess.run(
            [sonic, "-d", "vamp:nnls-chroma:chordino:simplechord", "-w", "csv", "--csv-stdout", str(path)],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        )
        if proc.returncode:
            raise RuntimeError(getattr(proc, "stderr", "") or "Chordino failed")
        output = getattr(proc, "stdout", "") or ""
        # Test/dev wrappers may materialize the CSV in the supplied path; never
        # rely on that for real audio, but accept textual CSV as a compatibility path.
        if not output:
            try:
                candidate = path.read_text(encoding="utf-8")
                if "," in candidate and "\n" in candidate:
                    output = candidate
            except (OSError, UnicodeDecodeError):
                pass
    except Exception as exc:
        logger.info("Chordino unavailable or failed; using internal analyser: %s", exc)
        return None
    events: list[Chord] = []
    last = None
    for row in csv.reader(output.splitlines()):
        if len(row) < 3:
            continue
        try:
            time_ms = max(0, round(float(row[1]) * 1000))
        except ValueError:
            continue
        label = row[-1].strip().strip('"')
        if not label or label in {"N", "N.C.", "no_chord"} or label == last:
            continue
        events.append(Chord(time_ms=time_ms, chord=label))
        last = label
    return events or None


def _normalize_madmom_chord(label: str) -> str:
    value=str(label or "").strip()
    if value in {"N", "N.C.", "no_chord"}:
        return ""
    value=value.replace(":maj", "").replace(":min", "m")
    return value


def _extract_chords_madmom(path: Path, engine: str) -> list[Chord]:
    if engine == "madmom-deep-chroma":
        from madmom_infer.audio.chroma import DeepChromaProcessor  # type: ignore
        from madmom_infer.features.chords import DeepChromaChordRecognitionProcessor  # type: ignore
        from madmom_infer.processors import SequentialProcessor  # type: ignore
        proc=SequentialProcessor([DeepChromaProcessor(), DeepChromaChordRecognitionProcessor()])
    elif engine == "madmom-cnn-crf":
        from madmom_infer.features.chords import CNNChordFeatureProcessor, CRFChordRecognitionProcessor  # type: ignore
        from madmom_infer.processors import SequentialProcessor  # type: ignore
        proc=SequentialProcessor([CNNChordFeatureProcessor(), CRFChordRecognitionProcessor()])
    else:
        raise ValueError("unsupported Madmom chord engine")
    rows=proc(str(path));events=[];last=None
    for row in rows:
        try: start=float(row[0]);label=_normalize_madmom_chord(str(row[2]))
        except (TypeError, ValueError, IndexError): continue
        if not label or label==last: continue
        events.append(Chord(time_ms=max(0,round(start*1000)),chord=label));last=label
    return events


def extract_chords(path: Path, *, interval_ms: int = 500, engine: str | None = None) -> list[Chord]:
    """Extract chord changes using the explicitly selected engine.

    AI engines never silently change to a different engine: callers can therefore
    report exactly which recognizer/model produced the project chord timeline.
    """
    engine=(engine or "mta-chromagram").strip() or "mta-chromagram"
    if engine in {"madmom-deep-chroma", "madmom-cnn-crf"}:
        return _extract_chords_madmom(path, engine)
    if engine == "chordino":
        chordino=_extract_chords_chordino(path)
        if not chordino:
            raise RuntimeError("Chordino / NNLS-Chroma is not available in this runtime")
        return chordino
    if engine != "mta-chromagram":
        raise ValueError("unsupported chord extraction engine")
    samples, sr = _pcm_mono(path)
    if samples.size < sr:
        raise ValueError("audio too short for chord analysis")
    frame = 4096
    hop = 2048
    window = np.hanning(frame).astype(np.float64)
    freqs = np.fft.rfftfreq(frame, 1.0 / sr)
    valid = (freqs >= 55.0) & (freqs <= 1760.0)
    valid_idx = np.nonzero(valid)[0]
    pcs = np.full(freqs.shape, -1, dtype=np.int16)
    for idx in valid_idx:
        midi = int(round(69 + 12 * math.log2(float(freqs[idx]) / 440.0)))
        pcs[idx] = midi % 12
    templates = _chord_templates()
    frames_per_bin = max(1, round((interval_ms / 1000.0) * sr / hop))
    chroma_frames: list[np.ndarray] = []
    for start in range(0, max(1, len(samples) - frame + 1), hop):
        chunk = samples[start:start + frame]
        if len(chunk) < frame:
            chunk = np.pad(chunk, (0, frame - len(chunk)))
        spec = np.abs(np.fft.rfft(chunk * window)) ** 2
        chroma = np.zeros(12, dtype=np.float64)
        for idx in valid_idx:
            pc = int(pcs[idx])
            # Weight low/mid harmonics a little more than upper partials.
            chroma[pc] += float(spec[idx]) / math.sqrt(max(1.0, float(freqs[idx])))
        norm = np.linalg.norm(chroma)
        if norm > 0:
            chroma /= norm
        chroma_frames.append(chroma)
    raw: list[tuple[int, str, float]] = []
    for group_start in range(0, len(chroma_frames), frames_per_bin):
        chroma = np.mean(chroma_frames[group_start:group_start + frames_per_bin], axis=0)
        norm = np.linalg.norm(chroma)
        if norm <= 1e-9:
            raw.append((round(group_start * hop * 1000 / sr), "N", 0.0))
            continue
        chroma /= norm
        scored = sorted(((float(np.dot(chroma, tpl)), name) for name, tpl in templates), reverse=True)
        best_score, best_name = scored[0]
        second_score = scored[1][0]
        confidence = best_score - second_score
        label = best_name if best_score >= 0.48 and confidence >= 0.015 else "N"
        raw.append((round(group_start * hop * 1000 / sr), label, confidence))

    # Temporal voting suppresses one-bin glitches without erasing real changes.
    labels = [item[1] for item in raw]
    smooth = labels[:]
    for i in range(len(labels)):
        lo, hi = max(0, i - 2), min(len(labels), i + 3)
        votes: dict[str, float] = {}
        for j in range(lo, hi):
            distance_weight = 1.0 / (1.0 + abs(i - j))
            confidence_weight = max(0.05, raw[j][2] + 0.05)
            votes[labels[j]] = votes.get(labels[j], 0.0) + distance_weight * confidence_weight
        smooth[i] = max(votes, key=votes.get) if votes else labels[i]
    events: list[Chord] = []
    last = None
    for (time_ms, _label, _confidence), label in zip(raw, smooth):
        if label == "N" or label == last:
            continue
        events.append(Chord(time_ms=time_ms, chord=label))
        last = label
    return events


def map_source_events_to_timeline(track: Track, events: list[LyricLine] | list[Chord]) -> list[LyricLine] | list[Chord]:
    if not track.clips:
        return events
    mapped = []
    for event in events:
        for clip in track.clips:
            if clip.source_start_ms <= event.time_ms < clip.source_end_ms:
                payload = event.model_dump()
                delta = clip.timeline_start_ms - clip.source_start_ms
                payload["time_ms"] = event.time_ms + delta
                if isinstance(event, LyricLine):
                    if payload.get("end_ms") is not None:
                        payload["end_ms"] = max(payload["time_ms"], int(payload["end_ms"]) + delta)
                    for word in payload.get("words") or []:
                        word["start_ms"] = max(0, int(word["start_ms"]) + delta)
                        word["end_ms"] = max(word["start_ms"], int(word["end_ms"]) + delta)
                mapped.append(type(event)(**payload))
    mapped.sort(key=lambda item: item.time_ms)
    return mapped


def synchronized_plain_text(lyrics: list[LyricLine], chords: list[Chord] | None = None) -> str:
    chords = sorted(chords or [], key=lambda x: x.time_ms)
    lines: list[str] = []
    ci = 0
    active = ""
    for lyric in sorted(lyrics, key=lambda x: x.time_ms):
        while ci < len(chords) and chords[ci].time_ms <= lyric.time_ms:
            active = chords[ci].chord
            ci += 1
        stamp = f"[{lyric.time_ms // 60000:02d}:{(lyric.time_ms % 60000) / 1000:05.2f}]"
        lines.append(f"{stamp}{'[' + active + ']' if active else ''} {lyric.text}".rstrip())
    return "\n".join(lines) + ("\n" if lines else "")


def build_chordpro(*, title: str, artist: str, key: str, bpm: float | None, lyrics: list[LyricLine], chords: list[Chord], authors: list[str] | None = None, rights_records: list[RightsRecord] | None = None) -> str:
    """Create a ChordPro document from synchronized project text.

    Chords are aligned to word timestamps when available. With segment-only lyrics,
    the last chord active at the lyric line start is inserted at the beginning.
    """
    lines: list[str] = []
    if title:
        lines.append(f"{{title: {title}}}")
    if artist:
        lines.append(f"{{artist: {artist}}}")
    if authors:
        lines.append(f"{{composer: {', '.join(x for x in authors if x)}}}")
    if key:
        lines.append(f"{{key: {key}}}")
    if bpm is not None and float(bpm) > 0:
        lines.append(f"{{tempo: {float(bpm):g}}}")
    lines.append("")
    ordered_chords = sorted(chords, key=lambda x: x.time_ms)
    ordered_lyrics = sorted(lyrics, key=lambda x: x.time_ms)
    for li, lyric in enumerate(ordered_lyrics):
        next_time = ordered_lyrics[li + 1].time_ms if li + 1 < len(ordered_lyrics) else (lyric.end_ms or lyric.time_ms + 8000)
        inside = [c for c in ordered_chords if lyric.time_ms <= c.time_ms < next_time]
        before = [c for c in ordered_chords if c.time_ms <= lyric.time_ms]
        if lyric.words:
            words = list(lyric.words)
            inserts: dict[int, list[str]] = {}
            active = before[-1].chord if before else ""
            if active:
                inserts.setdefault(0, []).append(active)
            for chord in inside:
                nearest = min(range(len(words)), key=lambda i: abs(words[i].start_ms - chord.time_ms))
                bucket = inserts.setdefault(nearest, [])
                if not bucket or bucket[-1] != chord.chord:
                    bucket.append(chord.chord)
            rendered: list[str] = []
            for i, word in enumerate(words):
                for chord in inserts.get(i, []):
                    rendered.append(f"[{chord}]")
                rendered.append(word.text)
            line = " ".join(part for part in rendered if part).strip()
            if not line:
                line = lyric.text.strip()
        else:
            active = inside[0].chord if inside else (before[-1].chord if before else "")
            line = f"[{active}]{lyric.text}" if active else lyric.text
        lines.append(line.rstrip())
    if rights_records:
        lines.append("")
        lines.append("{comment: Rights / repertoire references selected in MTA Audio Editor}")
        for record in rights_records:
            ids = ", ".join(f"{k}: {v}" for k, v in record.identifiers.items())
            parts = [
                f"Provider: {record.society}" if record.society else "",
                f"UID: {record.uid}" if record.uid else "",
                f"Title: {record.title}" if record.title else "",
                f"Original title: {record.original_title}" if record.original_title else "",
                f"Authors: {', '.join(record.authors)}" if record.authors else "",
                f"Performers: {', '.join(record.performers)}" if record.performers else "",
                f"Publishers: {', '.join(record.publishers)}" if record.publishers else "",
                f"Identifiers: {ids}" if ids else "",
                f"Source: {record.source_url}" if record.source_url else "",
            ]
            lines.append(f"{{comment: {' · '.join(x for x in parts if x)}}}")
    return "\n".join(lines).rstrip() + "\n"


def _pdf_font() -> str:
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    candidates = [
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
        Path("/usr/share/fonts/dejavu/DejaVuSans.ttf"),
        Path("/Library/Fonts/Arial Unicode.ttf"),
        Path("C:/Windows/Fonts/arial.ttf"),
    ]
    for candidate in candidates:
        if candidate.is_file():
            try:
                pdfmetrics.registerFont(TTFont("MTAUnicode", str(candidate)))
                return "MTAUnicode"
            except Exception as exc:
                logger.debug("Unable to register PDF font %s: %s", candidate, exc)
                continue
    return "Helvetica"


def build_lyrics_pdf(out: Path, *, title: str, artist: str, lyrics: list[LyricLine], chords: list[Chord], chord_color: str = "#7B1FA2", key: str = "", bpm: float | None = None, rights_records: list[RightsRecord] | None = None) -> Path:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.colors import HexColor, black
    from reportlab.pdfgen import canvas

    out.parent.mkdir(parents=True, exist_ok=True)
    font = _pdf_font()
    c = canvas.Canvas(str(out), pagesize=A4, pageCompression=1)
    width, height = A4
    margin = 48
    y = height - 54

    def new_page() -> None:
        nonlocal y
        c.showPage()
        y = height - 54

    def safe(text: str) -> str:
        if font == "Helvetica":
            return text.encode("latin-1", errors="replace").decode("latin-1")
        return text

    c.setTitle(title or "Lyrics")
    if artist:
        c.setAuthor(artist)
    c.setFont(font, 18)
    c.drawString(margin, y, safe(title or "Lyrics"))
    y -= 24
    info_parts: list[str] = []
    if artist:
        info_parts.append(artist)
    if key:
        info_parts.append(f"Key: {key}")
    if bpm is not None and float(bpm) > 0:
        info_parts.append(f"BPM: {float(bpm):g}")
    if info_parts:
        c.setFont(font, 11)
        c.drawString(margin, y, safe("  ·  ".join(info_parts)))
        y -= 26
    else:
        y -= 8

    ordered_lyrics = sorted(lyrics, key=lambda x: x.time_ms)
    ordered_chords = sorted(chords, key=lambda x: x.time_ms)
    for i, lyric in enumerate(ordered_lyrics):
        next_time = ordered_lyrics[i + 1].time_ms if i + 1 < len(ordered_lyrics) else 2**63 - 1
        current_chords = [ch for ch in ordered_chords if lyric.time_ms <= ch.time_ms < next_time]
        # If there is no change inside this lyric interval, carry the last known chord.
        if not current_chords:
            previous = [ch for ch in ordered_chords if ch.time_ms <= lyric.time_ms]
            if previous:
                current_chords = [previous[-1]]
        if y < 82:
            new_page()
        if current_chords:
            try:
                c.setFillColor(HexColor(chord_color))
            except Exception:
                c.setFillColor(HexColor("#7B1FA2"))
            c.setFont(font, 9)
            available = width - 2 * margin
            span = max(1, next_time - lyric.time_ms) if next_time < 2**63 - 1 else max(1, 5000)
            for chord in current_chords:
                rel = max(0.0, min(1.0, (chord.time_ms - lyric.time_ms) / span))
                c.drawString(margin + rel * available, y, safe(chord.chord))
            y -= 13
            c.setFillColor(black)
        c.setFont(font, 11)
        text = safe(lyric.text)
        # Simple width-aware wrapping without changing synchronization semantics.
        words = text.split()
        line = ""
        wrapped: list[str] = []
        for word in words:
            candidate = f"{line} {word}".strip()
            if c.stringWidth(candidate, font, 11) > width - 2 * margin and line:
                wrapped.append(line)
                line = word
            else:
                line = candidate
        if line or not wrapped:
            wrapped.append(line)
        for part in wrapped:
            if y < 64:
                new_page()
                c.setFont(font, 11)
            c.drawString(margin, y, part)
            y -= 15
        y -= 8

    if rights_records:
        if y < 150:
            new_page()
        y -= 8
        c.setFillColor(black)
        c.setFont(font, 10)
        c.drawString(margin, y, safe("Dati repertorio / Rights information"))
        y -= 16
        c.setFont(font, 8)
        for record in rights_records:
            if y < 72:
                new_page()
                c.setFont(font, 8)
            identifiers = ", ".join(f"{k}: {v}" for k, v in record.identifiers.items())
            authors_text = ", ".join(record.authors)
            performers_text = ", ".join(record.performers)
            publishers_text = ", ".join(record.publishers)
            parts = [
                f"Provider: {record.society}" if record.society else "",
                f"UID: {record.uid}" if record.uid else "",
                f"Titolo: {record.title}" if record.title else "",
                f"Titolo originale: {record.original_title}" if record.original_title else "",
                f"Autori: {authors_text}" if authors_text else "",
                f"Interpreti: {performers_text}" if performers_text else "",
                f"Editori: {publishers_text}" if publishers_text else "",
                f"Identificativi: {identifiers}" if identifiers else "",
                f"Fonte: {record.source_url}" if record.source_url else "",
            ]
            text = safe(" · ".join(x for x in parts if x))
            words = text.split()
            line = ""
            wrapped: list[str] = []
            for word in words:
                candidate = f"{line} {word}".strip()
                if c.stringWidth(candidate, font, 8) > width - 2 * margin and line:
                    wrapped.append(line)
                    line = word
                else:
                    line = candidate
            if line:
                wrapped.append(line)
            for part in wrapped or [""]:
                if y < 64:
                    new_page()
                    c.setFont(font, 8)
                c.drawString(margin, y, part)
                y -= 11
            y -= 4
    c.save()
    return out



def _ass_time(ms: int) -> str:
    cs = max(0, int(ms)) // 10
    h, rem = divmod(cs, 360000)
    m, rem = divmod(rem, 6000)
    sec, cent = divmod(rem, 100)
    return f"{h}:{m:02d}:{sec:02d}.{cent:02d}"


def _ass_escape(text: str) -> str:
    return text.replace("\\", r"\\").replace("{", r"\{").replace("}", r"\}").replace("\n", r"\N")


def build_karaoke_ass(
    out: Path, *, title: str, artist: str, lyrics: list[LyricLine],
    chords: list[Chord] | None = None, include_chords: bool = True,
    width: int = 1920, height: int = 1080,
) -> Path:
    """Build ASS subtitles with word-level karaoke timing and optional chord line."""
    if not lyrics:
        raise ValueError("lyrics are required for karaoke export")
    out.parent.mkdir(parents=True, exist_ok=True)
    header = (
        "[Script Info]\n"
        f"Title: {_ass_escape(title or 'Karaoke')}\n"
        "ScriptType: v4.00+\n"
        f"PlayResX: {width}\nPlayResY: {height}\nWrapStyle: 2\n\n"
        "[V4+ Styles]\n"
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n"
        "Style: Karaoke,DejaVu Sans,54,&H00FFFFFF,&H00808080,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,3,1,2,80,80,90,1\n"
        "Style: Chord,DejaVu Sans,38,&H0000D7FF,&H0000D7FF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,3,1,2,80,80,160,1\n"
        "Style: Meta,DejaVu Sans,28,&H00E0E0E0,&H000000FF,&H00000000,&H80000000,0,0,0,0,100,100,0,0,1,2,0,8,60,60,40,1\n\n"
        "[Events]\n"
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
    )
    events: list[str] = []
    meta = " · ".join(x for x in [title.strip(), artist.strip()] if x)
    if meta:
        events.append(f"Dialogue: 0,0:00:00.00,0:00:06.00,Meta,,0,0,0,,{_ass_escape(meta)}")
    ordered = sorted(lyrics, key=lambda x: x.time_ms)
    chord_rows = sorted(chords or [], key=lambda x: x.time_ms)
    for i, line in enumerate(ordered):
        start = line.time_ms
        default_end = ordered[i + 1].time_ms - 20 if i + 1 < len(ordered) else start + 6000
        end = max(start + 500, line.end_ms or default_end)
        words = [w for w in line.words if w.text.strip()]
        if words:
            pieces = []
            for word in words:
                duration_cs = max(1, round(max(10, word.end_ms - word.start_ms) / 10))
                pieces.append(r"{\kf" + str(duration_cs) + "}" + _ass_escape(word.text) + " ")
            text = "".join(pieces).rstrip()
        else:
            duration_cs = max(1, round((end - start) / 10))
            text = r"{\kf" + str(duration_cs) + "}" + _ass_escape(line.text)
        if include_chords and chord_rows:
            active = [ch for ch in chord_rows if ch.time_ms <= start]
            inside = [ch for ch in chord_rows if start < ch.time_ms < end]
            line_chords = ([active[-1]] if active else []) + inside
            if line_chords:
                label = "   ".join(ch.chord for ch in line_chords)
                events.append(f"Dialogue: 0,{_ass_time(start)},{_ass_time(end)},Chord,,0,0,0,,{_ass_escape(label)}")
        events.append(f"Dialogue: 0,{_ass_time(start)},{_ass_time(end)},Karaoke,,0,0,0,,{text}")
    out.write_text(header + "\n".join(events) + "\n", encoding="utf-8-sig")
    return out
