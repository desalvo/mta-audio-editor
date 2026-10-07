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
from typing import Callable

import numpy as np

from .models import Chord, LyricLine, LyricSyllable, LyricWord, Marker, RightsRecord, Track


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
    # Preserve manual Lyrics + Chords editor anchors while transposing only the symbol.
    return [
        item.model_copy(update={"chord": transpose_chord_symbol(item.chord, semitones)})
        for item in chords
    ]


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


def _normalize_word_token(token: str) -> str:
    return re.sub(r"\s+", " ", str(token or "").strip())


def _clean_lyric_text(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "").strip())


def _normalize_lyric_items(items: list[LyricLine]) -> list[LyricLine]:
    """Normalize Whisper output and drop obvious chunk-boundary duplicates."""
    normalized: list[LyricLine] = []
    for item in sorted(items, key=lambda x: (x.time_ms, x.end_ms or x.time_ms, x.text)):
        text = _clean_lyric_text(item.text)
        if not text:
            continue
        words: list[LyricWord] = []
        last_word_key = None
        for word in item.words or []:
            token = _normalize_word_token(word.text)
            if not token:
                continue
            start_ms = int(max(0, word.start_ms))
            end_ms = int(max(start_ms, word.end_ms))
            key = (token.casefold(), start_ms, end_ms)
            if key == last_word_key:
                continue
            syllables=[LyricSyllable(**x.model_dump()) for x in getattr(word, "syllables", [])]
            words.append(LyricWord(start_ms=start_ms, end_ms=end_ms, text=token, syllables=syllables))
            last_word_key = key
        cleaned = LyricLine(
            time_ms=int(max(0, item.time_ms)),
            end_ms=(None if item.end_ms is None else int(max(item.time_ms, item.end_ms))),
            text=text,
            words=words,
        )
        if normalized:
            prev = normalized[-1]
            # Only collapse the same text when the two segments clearly describe
            # the *same audio interval*. Repeated lyrics are legitimate content:
            # identical words/phrases at distinct timestamps must be preserved.
            prev_end = int(prev.end_ms or prev.time_ms)
            cur_end = int(cleaned.end_ms or cleaned.time_ms)
            overlap_ms = max(0, min(prev_end, cur_end) - max(prev.time_ms, cleaned.time_ms))
            prev_span = max(1, prev_end - prev.time_ms)
            cur_span = max(1, cur_end - cleaned.time_ms)
            overlap_ratio = overlap_ms / max(1, min(prev_span, cur_span))
            prev_word_keys = {(w.text.casefold(), w.start_ms, w.end_ms) for w in prev.words}
            cur_word_keys = {(w.text.casefold(), w.start_ms, w.end_ms) for w in cleaned.words}
            exact_word_overlap = bool(prev_word_keys and cur_word_keys and (prev_word_keys & cur_word_keys))
            same_audio_duplicate = (
                prev.text.casefold() == cleaned.text.casefold()
                and (overlap_ratio >= 0.55 or exact_word_overlap)
            )
            if same_audio_duplicate:
                prev.end_ms = max(prev_end, cur_end)
                merged_words = list(prev.words)
                seen = {(w.text.casefold(), w.start_ms, w.end_ms) for w in merged_words}
                for word in cleaned.words:
                    key = (word.text.casefold(), word.start_ms, word.end_ms)
                    if key not in seen:
                        merged_words.append(word)
                        seen.add(key)
                merged_words.sort(key=lambda w: (w.start_ms, w.end_ms, w.text))
                prev.words = merged_words
                continue
        normalized.append(cleaned)
    return normalized


def _syllable_parts(token: str) -> list[str]:
    """Conservative language-agnostic syllable approximation for timing anchors."""
    raw = str(token or "").strip()
    if not raw:
        return []
    prefix = re.match(r"^[^A-Za-zÀ-ÖØ-öø-ÿ]+", raw)
    suffix = re.search(r"[^A-Za-zÀ-ÖØ-öø-ÿ]+$", raw)
    core = raw[(len(prefix.group(0)) if prefix else 0):(len(raw)-len(suffix.group(0)) if suffix else len(raw))]
    if not core:
        return [raw]
    vowels = "aeiouyàèéìòóùAEIOUYÀÈÉÌÒÓÙ"
    parts: list[str] = []
    start = 0
    seen_vowel = False
    for i, ch in enumerate(core):
        if ch in vowels:
            seen_vowel = True
            continue
        if seen_vowel and i + 1 < len(core) and core[i + 1] in vowels:
            parts.append(core[start:i + 1])
            start = i + 1
            seen_vowel = False
    if start < len(core):
        parts.append(core[start:])
    parts = [p for p in parts if p]
    if not parts:
        parts = [core]
    if prefix:
        parts[0] = prefix.group(0) + parts[0]
    if suffix:
        parts[-1] = parts[-1] + suffix.group(0)
    return parts


def _snap_to_energy_minimum(samples: np.ndarray, sr: int, time_ms: int, radius_ms: int = 75) -> int:
    if samples.size == 0 or sr <= 0:
        return max(0, int(time_ms))
    center = int(max(0, time_ms) * sr / 1000)
    radius = max(1, int(radius_ms * sr / 1000))
    lo = max(0, center - radius)
    hi = min(samples.size, center + radius)
    if hi - lo < 8:
        return max(0, int(time_ms))
    window = max(8, int(0.012 * sr))
    best_i, best_e = center, None
    step = max(1, window // 3)
    for i in range(lo, hi, step):
        a = max(0, i - window // 2)
        b = min(samples.size, i + window // 2)
        if b <= a:
            continue
        block = samples[a:b].astype(np.float32, copy=False)
        energy = float(np.mean(block * block))
        distance_penalty = abs(i - center) / max(1, radius) * 0.08
        score = energy + distance_penalty
        if best_e is None or score < best_e:
            best_e = score
            best_i = i
    return max(0, round(best_i * 1000 / sr))


def _estimated_word_and_syllable_timing(items: list[LyricLine]) -> list[LyricLine]:
    """Guarantee fine-grained timing even when Whisper only returns segments.

    Whisper word timestamps are preserved when present. Missing word timing is
    conservatively estimated from the segment duration and token lengths; each
    word then receives syllable timing. This is intentionally a fallback for
    downstream chord placement, not a replacement for acoustic alignment.
    """
    ordered = _normalize_lyric_items(items)
    out: list[LyricLine] = []
    for idx, line in enumerate(ordered):
        next_start = ordered[idx + 1].time_ms if idx + 1 < len(ordered) else None
        line_start = int(max(0, line.time_ms))
        default_duration = max(900, min(12000, len(line.text) * 85))
        line_end = int(line.end_ms or (next_start if next_start is not None and next_start > line_start else line_start + default_duration))
        line_end = max(line_start + 120, line_end)
        words = [LyricWord(**w.model_dump()) for w in (line.words or []) if str(w.text or '').strip()]
        if not words:
            tokens = [x for x in re.findall(r"\S+", line.text or "") if x.strip()]
            if tokens:
                weights = [max(1, len(re.sub(r"[^A-Za-zÀ-ÖØ-öø-ÿ0-9]", "", token))) for token in tokens]
                total = max(1, sum(weights))
                cursor = line_start
                used = 0
                words = []
                for wi, (token, weight) in enumerate(zip(tokens, weights)):
                    if wi == len(tokens) - 1:
                        end = line_end
                    else:
                        used += weight
                        end = line_start + round((line_end - line_start) * used / total)
                    end = max(cursor + 20, end)
                    words.append(LyricWord(start_ms=cursor, end_ms=end, text=token))
                    cursor = end
        fine_words: list[LyricWord] = []
        for word in words:
            start = max(line_start, int(word.start_ms))
            end = min(line_end, max(start + 20, int(word.end_ms)))
            syllables = [LyricSyllable(**x.model_dump()) for x in getattr(word, "syllables", [])]
            if not syllables:
                parts = _syllable_parts(word.text)
                if parts:
                    weights = [max(1, len(re.sub(r"[^A-Za-zÀ-ÖØ-öø-ÿ0-9]", "", part))) for part in parts]
                    total = max(1, sum(weights))
                    cursor = start
                    used = 0
                    syllables = []
                    for si, (part, weight) in enumerate(zip(parts, weights)):
                        if si == len(parts) - 1:
                            s_end = end
                        else:
                            used += weight
                            s_end = start + round((end - start) * used / total)
                        s_end = max(cursor, s_end)
                        syllables.append(LyricSyllable(start_ms=cursor, end_ms=s_end, text=part))
                        cursor = s_end
            fine_words.append(LyricWord(start_ms=start, end_ms=end, text=word.text, syllables=syllables))
        if fine_words:
            line_start = fine_words[0].start_ms
            line_end = fine_words[-1].end_ms
        out.append(LyricLine(time_ms=line_start, end_ms=line_end, text=line.text, words=fine_words))
    return out


def forced_align_lyrics(path: Path, items: list[LyricLine]) -> list[LyricLine]:
    """Refine Whisper word timing against local acoustic minima and add syllable timing."""
    normalized = _estimated_word_and_syllable_timing(items)
    try:
        samples, sr = _pcm_mono(path, sample_rate=16000)
    except Exception as exc:
        logger.warning("Forced alignment PCM extraction failed, using Whisper word timing: %s", exc)
        samples = np.zeros(0, dtype=np.float32)
        sr = 16000
    out: list[LyricLine] = []
    last_end = 0
    for line in normalized:
        words: list[LyricWord] = []
        for word in line.words:
            start = max(last_end, _snap_to_energy_minimum(samples, sr, word.start_ms, 65))
            end = max(start + 20, _snap_to_energy_minimum(samples, sr, word.end_ms, 65))
            if end <= start:
                end = max(start + 40, word.end_ms)
            parts = _syllable_parts(word.text)
            syllables: list[LyricSyllable] = []
            if parts:
                weights = [max(1, len(re.sub(r"[^A-Za-zÀ-ÖØ-öø-ÿ]", "", p))) for p in parts]
                total = sum(weights)
                cursor = start
                remaining = end - start
                used = 0
                for idx, (part, weight) in enumerate(zip(parts, weights)):
                    if idx == len(parts) - 1:
                        s_end = end
                    else:
                        used += weight
                        s_end = start + round(remaining * used / total)
                    syllables.append(LyricSyllable(start_ms=cursor, end_ms=max(cursor, s_end), text=part))
                    cursor = s_end
            words.append(LyricWord(start_ms=start, end_ms=end, text=word.text, syllables=syllables))
            last_end = end
        if words:
            line_start = words[0].start_ms
            line_end = words[-1].end_ms
        else:
            line_start = max(last_end, line.time_ms)
            line_end = max(line_start, line.end_ms or line.time_ms)
        out.append(LyricLine(time_ms=line_start, end_ms=line_end, text=line.text, words=words))
    return _normalize_lyric_items(out)


def native_ai_device() -> str:
    """Return the best PyTorch device available to native/server AI workloads.

    Explicit MTA_AI_DEVICE wins. Otherwise CUDA is preferred, then Apple MPS,
    then CPU. This keeps inference portable while using hardware acceleration
    whenever the bundled runtime exposes it.
    """
    forced = os.getenv("MTA_AI_DEVICE", "").strip()
    if forced:
        return forced
    try:
        import torch  # type: ignore
        if torch.cuda.is_available():
            return "cuda"
        mps = getattr(getattr(torch, "backends", None), "mps", None)
        if mps is not None and mps.is_available():
            return "mps"
    except Exception as exc:
        logger.debug("AI accelerator detection fell back to CPU: %s", exc)
    return "cpu"


def _lyrics_transcribe_kwargs(language: str | None, device: str) -> dict:
    kwargs = {
        "verbose": False,
        "word_timestamps": True,
        "temperature": 0.0,
        "beam_size": max(1, int(os.getenv("MTA_LYRICS_BEAM_SIZE", "8"))),
        "patience": 1.2,
        "condition_on_previous_text": False,
        "fp16": device == "cuda",
    }
    if language:
        kwargs["language"] = language
    return kwargs


def _whisper_transcribe(model, source: str, *, language: str | None, device: str):
    """Run Whisper safely on CUDA/MPS/CPU, avoiding unsupported MPS float64 tensors.

    Upstream Whisper and some torch/NumPy paths may create float64 intermediates on
    Apple MPS. Keep the model in float32 and transparently retry on CPU if MPS still
    rejects a float64 conversion.
    """
    try:
        if hasattr(model, "float"):
            model.float()
        return model.transcribe(source, **_lyrics_transcribe_kwargs(language, device))
    except (RuntimeError, TypeError) as exc:
        message = str(exc).lower()
        if device != "mps" or ("float64" not in message and "mps" not in message):
            raise
        logger.warning("Whisper MPS float64 incompatibility; retrying transcription on CPU: %s", exc)
        try:
            if hasattr(model, "to"):
                model = model.to("cpu")
            if hasattr(model, "float"):
                model.float()
        except Exception:
            logger.exception("Could not move Whisper model from MPS to CPU")
            raise
        return model.transcribe(source, **_lyrics_transcribe_kwargs(language, "cpu"))


def _offset_lyrics(items: list[LyricLine], offset_ms: int) -> list[LyricLine]:
    out=[]
    for item in items:
        words=[LyricWord(start_ms=w.start_ms+offset_ms,end_ms=w.end_ms+offset_ms,text=w.text,syllables=[LyricSyllable(start_ms=s.start_ms+offset_ms,end_ms=s.end_ms+offset_ms,text=s.text) for s in getattr(w,"syllables",[])]) for w in item.words]
        out.append(LyricLine(time_ms=item.time_ms+offset_ms,end_ms=(item.end_ms+offset_ms if item.end_ms is not None else None),text=item.text,words=words))
    return out


def _duration_seconds(path: Path) -> float:
    try:
        raw=_run(["ffprobe","-v","error","-show_entries","format=duration","-of","default=noprint_wrappers=1:nokey=1",str(path)]).strip()
        return max(0.0,float(raw))
    except Exception:
        return 0.0


def extract_lyrics_progressive(
    path: Path, *, model_name: str | None = None, language: str | None = None,
    progress: Callable[[int, list[LyricLine], str], None] | None = None,
    cancelled: Callable[[], bool] | None = None, chunk_seconds: int = 5, advanced_alignment: bool = False,
) -> list[LyricLine]:
    """High-accuracy lyrics transcription for UI jobs.

    Live partial text can perturb chunk-based stitching and lead to repeated or
    missing phrases around chunk boundaries. For interactive jobs we therefore
    prioritize accuracy over incremental text preview: run a single complete
    Whisper pass and publish only status updates until the final result is ready.
    """
    model_name = (model_name or os.getenv("MTA_LYRICS_WHISPER_MODEL", "turbo")).strip() or "turbo"
    language = (language or os.getenv("MTA_LYRICS_LANGUAGE", "")).strip() or None
    device = native_ai_device()
    if cancelled and cancelled():
        raise InterruptedError("Lyrics extraction cancelled")
    if progress:
        progress(8, [], f"Verifica modello Whisper {model_name} · {device}")
        progress(18, [], f"Trascrizione completa in corso · {device}")
    result = extract_lyrics(path, model_name=model_name, language=language, advanced_alignment=advanced_alignment)
    if cancelled and cancelled():
        raise InterruptedError("Lyrics extraction cancelled")
    if progress:
        progress(94, [], "Trascrizione completa terminata")
        progress(96, result, "Lyrics elaborate")
    return _normalize_lyric_items(result)


def extract_lyrics(path: Path, *, model_name: str | None = None, language: str | None = None, advanced_alignment: bool = False) -> list[LyricLine]:
    """Transcribe a track with upstream OpenAI Whisper and preserve segment timing.

    The model is intentionally resolved by Whisper itself so native/server runtimes
    download it from the upstream Whisper model source/cache rather than the MTA
    model repository.
    """
    model_name = (model_name or os.getenv("MTA_LYRICS_WHISPER_MODEL", "turbo")).strip() or "turbo"
    language = (language or os.getenv("MTA_LYRICS_LANGUAGE", "")).strip() or None
    cache_dir = Path(os.getenv("MTA_LYRICS_MODEL_DIR", str(Path(os.getenv("MTA_DATA_DIR", "/data/projects")) / ".cache" / "lyrics-models"))).expanduser()
    cache_dir.mkdir(parents=True, exist_ok=True)

    # Prefer the Python API when bundled in native/server builds. It gives a
    # stable JSON result and lets Whisper own the upstream model lifecycle.
    if importlib.util.find_spec("whisper"):
        import whisper  # type: ignore

        device = native_ai_device()
        try:
            model = whisper.load_model(model_name, download_root=str(cache_dir), device=device)
        except TypeError as exc:
            if "device" not in str(exc):
                raise
            model = whisper.load_model(model_name, download_root=str(cache_dir))
        result = _whisper_transcribe(model, str(path), language=language, device=device)
        lines = _normalize_lyric_items(_whisper_result_to_lines(result))
        return forced_align_lyrics(path, lines) if advanced_alignment else lines

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
        lines = _normalize_lyric_items(_whisper_result_to_lines(json.loads(output.read_text(encoding="utf-8"))))
        return forced_align_lyrics(path, lines) if advanced_alignment else lines


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
    """Extended harmonic vocabulary used by MTA's refinement stage.

    The first recognizer (Madmom/Chordino/internal) is treated as a robust source
    of chord-change/root priors.  These templates refine quality/extensions and
    inversion from the actual spectrum instead of being limited to maj/min.
    """
    out: list[tuple[str, np.ndarray]] = []
    qualities = (
        ("", (0, 4, 7), (1.00, 0.90, 0.80)),
        ("m", (0, 3, 7), (1.00, 0.90, 0.80)),
        ("7", (0, 4, 7, 10), (1.00, 0.86, 0.76, 0.64)),
        ("maj7", (0, 4, 7, 11), (1.00, 0.86, 0.76, 0.64)),
        ("m7", (0, 3, 7, 10), (1.00, 0.86, 0.76, 0.64)),
        ("dim", (0, 3, 6), (1.00, 0.88, 0.80)),
        ("aug", (0, 4, 8), (1.00, 0.88, 0.80)),
        ("sus2", (0, 2, 7), (1.00, 0.84, 0.78)),
        ("sus4", (0, 5, 7), (1.00, 0.84, 0.78)),
    )
    for root in range(12):
        for suffix, intervals, weights in qualities:
            v = np.zeros(12, dtype=np.float64)
            for interval, weight in zip(intervals, weights):
                v[(root + interval) % 12] = weight
            v /= np.linalg.norm(v)
            out.append((NOTE_NAMES[root] + suffix, v))
    return out


def _chord_root_pc(label: str) -> int | None:
    match = re.match(r"^([A-G](?:#|b)?)", str(label or ""))
    return _NOTE_TO_PC.get(match.group(1)) if match else None


def _chord_pitch_classes(label: str) -> set[int]:
    root = _chord_root_pc(label)
    if root is None:
        return set()
    symbol = str(label).split("/", 1)[0]
    suffix = symbol[len(re.match(r"^[A-G](?:#|b)?", symbol).group(0)):]
    intervals = {
        "": (0, 4, 7), "m": (0, 3, 7), "5": (0, 7),
        "6": (0, 4, 7, 9), "m6": (0, 3, 7, 9),
        "7": (0, 4, 7, 10), "maj7": (0, 4, 7, 11), "m7": (0, 3, 7, 10),
        "mMaj7": (0, 3, 7, 11), "dim": (0, 3, 6), "dim7": (0, 3, 6, 9),
        "m7b5": (0, 3, 6, 10), "aug": (0, 4, 8), "sus2": (0, 2, 7),
        "sus4": (0, 5, 7), "add9": (0, 2, 4, 7), "9": (0, 2, 4, 7, 10),
        "maj9": (0, 2, 4, 7, 11), "m9": (0, 2, 3, 7, 10),
        "7sus4": (0, 5, 7, 10), "7b5": (0, 4, 6, 10), "7#5": (0, 4, 8, 10),
        "7b9": (0, 1, 4, 7, 10), "7#9": (0, 3, 4, 7, 10),
    }.get(suffix, (0, 4, 7))
    return {(root + x) % 12 for x in intervals}


def _harmonic_features(path: Path, *, interval_ms: int = 250) -> tuple[list[int], np.ndarray, np.ndarray, np.ndarray]:
    """Return timestamps, chroma, bass-chroma and energy for harmonic refinement."""
    samples, sr = _pcm_mono(path)
    if samples.size < sr:
        raise ValueError("audio too short for chord analysis")
    frame = 8192
    hop = 2048
    window = np.hanning(frame).astype(np.float64)
    freqs = np.fft.rfftfreq(frame, 1.0 / sr)
    full_idx = np.nonzero((freqs >= 55.0) & (freqs <= 2200.0))[0]
    bass_idx = np.nonzero((freqs >= 41.0) & (freqs <= 300.0))[0]
    pcs = np.full(freqs.shape, -1, dtype=np.int16)
    for idx in np.unique(np.concatenate((full_idx, bass_idx))):
        midi = int(round(69 + 12 * math.log2(float(freqs[idx]) / 440.0)))
        pcs[idx] = midi % 12
    chroma_frames: list[np.ndarray] = []
    bass_frames: list[np.ndarray] = []
    energies: list[float] = []
    for start in range(0, max(1, len(samples) - frame + 1), hop):
        chunk = samples[start:start + frame]
        if len(chunk) < frame:
            chunk = np.pad(chunk, (0, frame - len(chunk)))
        spec = np.abs(np.fft.rfft(chunk * window)) ** 2
        chroma = np.zeros(12, dtype=np.float64)
        bass = np.zeros(12, dtype=np.float64)
        for idx in full_idx:
            chroma[int(pcs[idx])] += float(spec[idx]) / math.sqrt(max(1.0, float(freqs[idx])))
        for idx in bass_idx:
            # stronger preference for fundamentals in the true bass range
            bass[int(pcs[idx])] += float(spec[idx]) / max(1.0, float(freqs[idx]) ** 0.35)
        cn = np.linalg.norm(chroma)
        bn = np.linalg.norm(bass)
        if cn > 0:
            chroma /= cn
        if bn > 0:
            bass /= bn
        chroma_frames.append(chroma)
        bass_frames.append(bass)
        energies.append(float(np.sqrt(np.mean(np.square(chunk, dtype=np.float64)) + 1e-12)))
    group = max(1, round((interval_ms / 1000.0) * sr / hop))
    times: list[int] = []
    cgroups: list[np.ndarray] = []
    bgroups: list[np.ndarray] = []
    egroups: list[float] = []
    for start in range(0, len(chroma_frames), group):
        times.append(round(start * hop * 1000 / sr))
        cgroups.append(np.mean(chroma_frames[start:start + group], axis=0))
        bgroups.append(np.mean(bass_frames[start:start + group], axis=0))
        egroups.append(float(np.mean(energies[start:start + group])))
    return times, np.asarray(cgroups), np.asarray(bgroups), np.asarray(egroups)


def _base_label_at(events: list[Chord], time_ms: int) -> str:
    label = ""
    for item in events:
        if item.time_ms > time_ms:
            break
        label = item.chord
    return label


def _copy_chord_with_label(item: Chord, label: str) -> Chord:
    return item.model_copy(update={"chord": label})


def _simplify_chord_label(label: str) -> str:
    """Collapse extended/altered labels to a conservative live-performance vocabulary."""
    value = str(label or "").strip()
    if not value or value in {"N", "N.C.", "no_chord"}:
        return "N"
    bass = ""
    if "/" in value:
        value, bass = value.split("/", 1)
    match = re.match(r"^([A-G](?:#|b)?)(.*)$", value)
    if not match:
        return value
    root, suffix = match.groups()
    mapping = {
        "": "", "5": "", "6": "", "add9": "", "9": "7", "maj9": "maj7",
        "m": "m", "m6": "m", "m9": "m7", "mMaj7": "m",
        "7": "7", "7b5": "7", "7#5": "7", "7b9": "7", "7#9": "7",
        "maj7": "maj7", "m7": "m7", "dim": "dim", "dim7": "dim", "m7b5": "dim",
        "aug": "aug", "sus2": "sus2", "sus4": "sus4", "7sus4": "sus4",
    }
    simple = root + mapping.get(suffix, ("m" if suffix.startswith("m") else ""))
    if bass and bass != root and re.match(r"^[A-G](?:#|b)?$", bass):
        simple += f"/{bass}"
    return simple




def _normalize_chord_options(options: dict | None = None) -> dict:
    raw = dict(options or {})
    preset = str(raw.get("preset") or "stable")
    defaults = {
        "stable": dict(sensitivity=25, harmonic_refinement=False, detect_sevenths=False, detect_sus=False, detect_dim_aug=False, detect_slash_bass=False, temporal_smoothing=True, beat_sync=False, min_chord_ms=1800, max_changes_per_minute=24),
        "balanced": dict(sensitivity=45, harmonic_refinement=True, detect_sevenths=True, detect_sus=True, detect_dim_aug=False, detect_slash_bass=False, temporal_smoothing=True, beat_sync=False, min_chord_ms=1100, max_changes_per_minute=36),
        "detailed": dict(sensitivity=70, harmonic_refinement=True, detect_sevenths=True, detect_sus=True, detect_dim_aug=True, detect_slash_bass=True, temporal_smoothing=True, beat_sync=False, min_chord_ms=550, max_changes_per_minute=60),
        "raw": dict(sensitivity=100, harmonic_refinement=False, detect_sevenths=True, detect_sus=True, detect_dim_aug=True, detect_slash_bass=True, temporal_smoothing=False, beat_sync=False, min_chord_ms=0, max_changes_per_minute=0),
    }.get(preset, {})
    out = {"preset": preset, **defaults}
    out.update({k: v for k, v in raw.items() if v is not None})
    out["sensitivity"] = max(0, min(100, int(out.get("sensitivity", 25))))
    out["min_chord_ms"] = max(0, min(10000, int(out.get("min_chord_ms", 0))))
    out["max_changes_per_minute"] = max(0, min(240, int(out.get("max_changes_per_minute", 0))))
    for key in ("harmonic_refinement", "detect_sevenths", "detect_sus", "detect_dim_aug", "detect_slash_bass", "temporal_smoothing", "beat_sync"):
        out[key] = bool(out.get(key, False))
    return out


def _limit_chord_vocabulary(label: str, options: dict) -> str:
    value = _simplify_chord_label(label)
    if value == "N":
        return value
    bass = ""
    if "/" in value:
        value, bass = value.split("/", 1)
    match = re.match(r"^([A-G](?:#|b)?)(.*)$", value)
    if not match:
        return value
    root, suffix = match.groups()
    if suffix in {"7", "maj7", "m7"} and not options.get("detect_sevenths"):
        suffix = "m" if suffix == "m7" else ""
    if suffix in {"sus2", "sus4"} and not options.get("detect_sus"):
        suffix = ""
    if suffix in {"dim", "aug"} and not options.get("detect_dim_aug"):
        suffix = "m" if suffix == "dim" else ""
    result = root + suffix
    if options.get("detect_slash_bass") and bass and bass != root:
        result += f"/{bass}"
    return result


def _postprocess_chord_events(
    events: list[Chord], options: dict | None = None, *, bpm: float | None = None, beat_origin_ms: int = 0,
) -> list[Chord]:
    opts = _normalize_chord_options(options)
    if not events:
        return []
    cleaned: list[Chord] = []
    for item in sorted(events, key=lambda x: int(x.time_ms)):
        label = _limit_chord_vocabulary(item.chord, opts)
        if label == "N":
            continue
        candidate = _copy_chord_with_label(item, label)
        if cleaned and candidate.chord == cleaned[-1].chord:
            continue
        cleaned.append(candidate)
    if not opts.get("temporal_smoothing"):
        return cleaned

    sensitivity = int(opts["sensitivity"])
    min_ms = int(opts.get("min_chord_ms", round(2800 - 24 * sensitivity)))
    min_ms = max(250, min_ms) if min_ms else 0

    # Remove fleeting labels. Prefer merging A-B-A back into A, otherwise absorb
    # a very short event into the previous stable chord. Repeat because removing
    # one transient can expose another adjacent transient.
    if min_ms and len(cleaned) >= 2:
        changed = True
        while changed and len(cleaned) >= 2:
            changed = False
            out: list[Chord] = []
            for idx, item in enumerate(cleaned):
                if idx == len(cleaned) - 1:
                    out.append(item); continue
                duration = int(cleaned[idx + 1].time_ms) - int(item.time_ms)
                if idx > 0 and duration < min_ms:
                    if idx + 1 < len(cleaned) and out and out[-1].chord == cleaned[idx + 1].chord:
                        changed = True
                        continue
                    # Conservative mode absorbs a fleeting event into the prior chord.
                    if sensitivity < 80:
                        changed = True
                        continue
                out.append(item)
            cleaned = out

    # Optional beat-grid snapping. This uses the project BPM and therefore avoids
    # inventing sub-beat harmonic changes from frame noise.
    if opts.get("beat_sync") and bpm and bpm > 0:
        beat_ms = 60000.0 / float(bpm)
        snapped: list[Chord] = []
        for item in cleaned:
            q = round((int(item.time_ms) - beat_origin_ms) / beat_ms)
            t = max(0, round(beat_origin_ms + q * beat_ms))
            candidate = item.model_copy(update={"time_ms": t})
            if snapped and candidate.time_ms == snapped[-1].time_ms:
                snapped[-1] = candidate
            elif not snapped or candidate.chord != snapped[-1].chord:
                snapped.append(candidate)
        cleaned = snapped

    # Hard density ceiling, useful for songbook-style output. Remove the shortest
    # segments first until the requested changes/minute ceiling is met.
    limit = int(opts.get("max_changes_per_minute") or 0)
    if limit > 0 and len(cleaned) > 2:
        span_ms = max(60000, int(cleaned[-1].time_ms) - int(cleaned[0].time_ms) + max(min_ms, 1000))
        max_events = max(2, int(math.ceil((span_ms / 60000.0) * limit)) + 1)
        while len(cleaned) > max_events and len(cleaned) > 2:
            durations = []
            for idx in range(1, len(cleaned) - 1):
                durations.append((int(cleaned[idx + 1].time_ms) - int(cleaned[idx].time_ms), idx))
            if not durations:
                break
            _, idx = min(durations)
            del cleaned[idx]
        # collapse equal neighbours created by removals
        collapsed: list[Chord] = []
        for item in cleaned:
            if not collapsed or item.chord != collapsed[-1].chord:
                collapsed.append(item)
        cleaned = collapsed
    return cleaned
def _refine_extended_harmony(
    path: Path, base_events: list[Chord], *, progress: Callable[[int, list[Chord], str], None] | None = None,
    cancelled: Callable[[], bool] | None = None, options: dict | None = None,
) -> list[Chord]:
    """Refine root/quality/inversion using extended chroma and bass-chroma analysis."""
    # Unit/integration wrappers can supply synthetic recognizer results without a
    # physical audio file. In production the source always exists; in wrappers,
    # preserve the base recognizer result rather than failing an unrelated FFmpeg step.
    if not Path(path).is_file():
        if progress:
            progress(90, [], "Raffinamento armonico non disponibile: mantengo il risultato base")
        return base_events
    if progress:
        progress(52, [], "Estrazione chroma armonica ad alta risoluzione")
    times, chroma, bass, energy = _harmonic_features(path, interval_ms=250)
    if cancelled and cancelled():
        raise InterruptedError("Chord extraction cancelled")
    if not len(times):
        return base_events
    # Direct legacy/internal calls without pipeline options keep the historical
    # detailed behaviour. The user-facing progressive pipeline always supplies
    # explicit options, so Stable/Balanced can disable slash bass and extensions.
    opts = _normalize_chord_options(options if options is not None else {"preset": "detailed"})
    templates = _chord_templates()
    def allowed(name: str) -> bool:
        suffix = re.sub(r"^[A-G](?:#|b)?", "", name)
        if suffix in {"7", "maj7", "m7"} and not opts.get("detect_sevenths"): return False
        if suffix in {"sus2", "sus4"} and not opts.get("detect_sus"): return False
        if suffix in {"dim", "aug"} and not opts.get("detect_dim_aug"): return False
        return True
    templates = [item for item in templates if allowed(item[0])]
    names = [name for name, _ in templates]
    matrix = np.stack([tpl for _, tpl in templates], axis=0)
    roots = np.asarray([_chord_root_pc(name) for name in names], dtype=np.int16)
    # More complex qualities need a slightly clearer spectral advantage to avoid
    # over-labelling ordinary triads as altered/extended chords.
    complexity = np.asarray([
        0.000 if re.match(r"^[A-G](?:#|b)?m?$", n) else
        0.014 if any(n.endswith(x) for x in ("7", "maj7", "m7", "sus2", "sus4", "dim", "aug")) else 0.030
        for n in names
    ], dtype=np.float64)
    labels: list[str] = []
    confidences: list[float] = []
    median_energy = max(1e-9, float(np.median(energy)))
    if progress:
        progress(68, [], "Classificazione armonica semplificata: triadi, 7e, sus, dim e aug")
    for i, time_ms in enumerate(times):
        if cancelled and cancelled():
            raise InterruptedError("Chord extraction cancelled")
        c = chroma[i]
        norm = np.linalg.norm(c)
        if norm <= 1e-9 or energy[i] < median_energy * 0.08:
            labels.append("N"); confidences.append(0.0); continue
        c = c / norm
        score = matrix @ c - complexity
        prior = _chord_root_pc(_base_label_at(base_events, time_ms))
        if prior is not None:
            score = score + (roots == prior) * 0.055
        order = np.argsort(score)[::-1]
        best, second = int(order[0]), int(order[1])
        margin = float(score[best] - score[second])
        label = names[best] if float(score[best]) >= 0.49 and margin >= 0.012 else (_simplify_chord_label(_base_label_at(base_events, time_ms)) or "N")
        labels.append(label)
        confidences.append(max(0.0, margin))
    if progress:
        progress(78, [], "Analisi basso e inversioni / slash chords" if opts.get("detect_slash_bass") else "Inversioni / slash bass disattivati")
    # Attach a slash bass only when the bass evidence is stable and meaningfully
    # stronger than the runner-up. Non-chord pedal bass is allowed, but requires
    # stronger evidence than an inversion using a chord tone.
    for i, label in enumerate(labels):
        if not opts.get("detect_slash_bass"):
            break
        if label == "N" or "/" in label:
            continue
        b = bass[i]
        order = np.argsort(b)[::-1]
        bass_pc, second_pc = int(order[0]), int(order[1])
        root = _chord_root_pc(label)
        if root is None or bass_pc == root:
            continue
        ratio = float((b[bass_pc] + 1e-9) / (b[second_pc] + 1e-9))
        chord_pcs = _chord_pitch_classes(label)
        threshold = 1.35 if bass_pc in chord_pcs else 9.99
        if ratio >= threshold and float(b[bass_pc]) >= 0.42:
            labels[i] = f"{label}/{NOTE_NAMES[bass_pc]}"
    if progress:
        progress(86, [], "Stabilizzazione temporale e rimozione transitori armonici")
    # Weighted local voting + hysteresis. Keep slash/inversion information only
    # when it persists long enough to be musically plausible.
    smooth = labels[:]
    for i in range(len(labels)):
        votes: dict[str, float] = {}
        for j in range(max(0, i - 3), min(len(labels), i + 4)):
            weight = (1.0 / (1.0 + abs(i - j))) * max(0.04, confidences[j] + 0.04)
            votes[labels[j]] = votes.get(labels[j], 0.0) + weight
        if votes:
            smooth[i] = max(votes, key=votes.get)
    events: list[Chord] = []
    last = ""
    for time_ms, label in zip(times, smooth):
        if label == "N" or label == last:
            continue
        # suppress isolated <500 ms labels between equal neighbours
        events.append(Chord(time_ms=int(time_ms), chord=label))
        last = label
    if len(events) >= 3:
        filtered: list[Chord] = []
        for idx, item in enumerate(events):
            if 0 < idx < len(events) - 1:
                duration = events[idx + 1].time_ms - item.time_ms
                if duration < 1000 and filtered and filtered[-1].chord == events[idx + 1].chord:
                    continue
            filtered.append(item)
        events = filtered
    return events or base_events

def _extract_chords_chordino(path: Path) -> list[Chord] | None:
    """Run bundled/system Chordino using Sonic Annotator or vamp-simple-host."""
    from .chordino_runtime import chordino_host_path, chordino_status, host_kind
    status = chordino_status()
    host = chordino_host_path() if status.get("available") else None
    kind = host_kind(host)
    if not host or not kind:
        return None
    try:
        if kind == "sonic-annotator":
            command = [host, "-d", "vamp:nnls-chroma:chordino:simplechord", "-w", "csv", "--csv-stdout", str(path)]
        else:
            command = [host, "nnls-chroma:chordino:simplechord", str(path)]
        proc = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if proc.returncode:
            raise RuntimeError(getattr(proc, "stderr", "") or "Chordino failed")
        output = getattr(proc, "stdout", "") or ""
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
    if kind == "sonic-annotator":
        rows = []
        for row in csv.reader(output.splitlines()):
            if len(row) < 3:
                continue
            try:
                seconds = float(row[1])
            except ValueError:
                continue
            rows.append((seconds, row[-1].strip().strip('"')))
    else:
        rows = []
        for line in output.splitlines():
            line = line.strip()
            if not line or ":" not in line:
                continue
            left, label = line.split(":", 1)
            try:
                seconds = float(left.strip())
            except ValueError:
                continue
            rows.append((seconds, label.strip().strip('"')))
    for seconds, label in rows:
        if not label or label in {"N", "N.C.", "no_chord"} or label == last:
            continue
        events.append(Chord(time_ms=max(0, round(seconds * 1000)), chord=label))
        last = label
    return events or None


def _normalize_madmom_chord(label: str) -> str:
    value=str(label or "").strip()
    if value in {"N", "N.C.", "no_chord"}:
        return ""
    value=value.replace(":maj", "").replace(":min", "m")
    return value


def _madmom_processor(engine: str):
    device=native_ai_device()
    use_torch=device != "cpu"
    if engine == "madmom-deep-chroma":
        from madmom_infer.audio.chroma import DeepChromaProcessor  # type: ignore
        from madmom_infer.features.chords import DeepChromaChordRecognitionProcessor  # type: ignore
        from madmom_infer.processors import SequentialProcessor  # type: ignore
        try:
            feature=DeepChromaProcessor(backend="torch",device=device) if use_torch else DeepChromaProcessor()
        except Exception as exc:
            logger.warning("Madmom accelerator %s unavailable, using NumPy backend: %s",device,exc)
            feature=DeepChromaProcessor()
        return SequentialProcessor([feature,DeepChromaChordRecognitionProcessor()]),device if use_torch else "cpu"
    if engine == "madmom-cnn-crf":
        from madmom_infer.features.chords import CNNChordFeatureProcessor, CRFChordRecognitionProcessor  # type: ignore
        from madmom_infer.processors import SequentialProcessor  # type: ignore
        try:
            feature=CNNChordFeatureProcessor(backend="torch",device=device) if use_torch else CNNChordFeatureProcessor()
        except Exception as exc:
            logger.warning("Madmom accelerator %s unavailable, using NumPy backend: %s",device,exc)
            feature=CNNChordFeatureProcessor()
        return SequentialProcessor([feature,CRFChordRecognitionProcessor()]),device if use_torch else "cpu"
    raise ValueError("unsupported Madmom chord engine")


def _madmom_pcm_wav(path: Path, destination: Path) -> Path:
    # madmom-infer's wave reader accepts RIFF/RIFX/RF64 PCM, not MP3/M4A/AAC
    # payloads. Always canonicalise the analysis input and leave project media intact.
    _run(["ffmpeg","-y","-v","error","-i",str(path),"-ac","1","-ar","44100","-c:a","pcm_s16le",str(destination)])
    return destination


def _madmom_rows_to_events(rows, offset_ms: int = 0) -> list[Chord]:
    events=[];last=None
    for row in rows:
        try: start=float(row[0]);label=_normalize_madmom_chord(str(row[2]))
        except (TypeError,ValueError,IndexError): continue
        if not label or label==last: continue
        events.append(Chord(time_ms=max(0,round(start*1000)+offset_ms),chord=label));last=label
    return events


def _extract_chords_madmom(path: Path, engine: str) -> list[Chord]:
    proc,_device=_madmom_processor(engine)
    with tempfile.TemporaryDirectory(prefix="mta-madmom-") as td_raw:
        wav=_madmom_pcm_wav(path,Path(td_raw)/"analysis.wav")
        return _madmom_rows_to_events(proc(str(wav)))



def _profile_engine_candidates(profile: str) -> list[str]:
    from .ai_models import chord_engine_available
    if profile == "stable":
        ordered = ["madmom-deep-chroma", "madmom-cnn-crf", "chordino", "mta-chromagram"]
    elif profile == "fast":
        ordered = ["chordino", "mta-chromagram"]
    elif profile == "accurate":
        ordered = ["chordformer", "btc-hcqt", "madmom-deep-chroma", "chordino", "mta-chromagram"]
    else:
        ordered = ["chordformer", "btc-hcqt", "chordino", "madmom-deep-chroma", "mta-chromagram"]
    return [engine for engine in ordered if chord_engine_available(engine)]


def _label_at(events: list[Chord], time_ms: int) -> str | None:
    label = None
    for event in events:
        if event.time_ms > time_ms:
            break
        if not event.deleted and not event.excluded:
            label = event.chord
    return label


def _ensemble_chord_events(results: dict[str, list[Chord]]) -> list[Chord]:
    if not results:
        return []
    weights = {"chordformer": 1.45, "btc-hcqt": 1.30, "chordino": 1.05, "madmom-deep-chroma": 0.90, "madmom-cnn-crf": 0.85, "mta-chromagram": 0.65}
    boundaries = sorted({0, *(event.time_ms for events in results.values() for event in events)})
    out: list[Chord] = []
    last = None
    for idx, start in enumerate(boundaries):
        next_start = boundaries[idx + 1] if idx + 1 < len(boundaries) else start + 500
        probe = start + max(1, (next_start - start) // 2)
        votes: dict[str, float] = {}
        for engine, events in results.items():
            label = _label_at(events, probe)
            if not label:
                continue
            votes[label] = votes.get(label, 0.0) + weights.get(engine, 0.75)
        if not votes:
            continue
        chosen = max(votes.items(), key=lambda item: (item[1], item[0]))[0]
        if chosen != last:
            out.append(Chord(time_ms=start, chord=chosen))
            last = chosen
    return out


def _extract_profile_base(path: Path, profile: str, progress=None, cancelled=None) -> tuple[list[Chord], str]:
    candidates = _profile_engine_candidates(profile)
    if not candidates:
        raise RuntimeError("No chord recognition engine is available")
    if profile != "maximum":
        engine = candidates[0]
        if progress:
            progress(28, [], f"Recognizer {engine} · analisi base")
        return extract_chords(path, engine=engine), engine
    selected = candidates[:4]
    results: dict[str, list[Chord]] = {}
    start_pct, end_pct = 18, 56
    for index, engine in enumerate(selected):
        if cancelled and cancelled():
            raise InterruptedError("Chord extraction cancelled")
        pct = start_pct + round((end_pct - start_pct) * index / max(1, len(selected)))
        if progress:
            progress(pct, [], f"Ensemble {index + 1}/{len(selected)} · {engine}")
        try:
            result = extract_chords(path, engine=engine)
        except Exception as exc:
            logger.warning("Chord ensemble engine %s failed: %s", engine, exc)
            continue
        if result:
            results[engine] = result
    if not results:
        raise RuntimeError("All ensemble chord engines failed")
    if progress:
        progress(58, [], f"Consensus ensemble · {len(results)} recognizer")
    return _ensemble_chord_events(results), "ensemble:" + "+".join(results)

def extract_chords_progressive(
    path: Path, *, engine: str, progress: Callable[[int,list[Chord],str],None] | None = None,
    cancelled: Callable[[],bool] | None = None, chunk_seconds: int = 5, options: dict | None = None,
    bpm: float | None = None, beat_origin_ms: int = 0,
) -> list[Chord]:
    """Multi-stage chord extraction with selectable speed/accuracy profiles."""
    del chunk_seconds
    opts = _normalize_chord_options(options)
    if cancelled and cancelled():
        raise InterruptedError("Chord extraction cancelled")
    profile = engine.removeprefix("profile-") if engine.startswith("profile-") else ""
    if progress:
        progress(8, [], "Step 1 · preparazione motori e acceleratore")
    if profile:
        base_events, used = _extract_profile_base(path, profile, progress=progress, cancelled=cancelled)
        if progress:
            progress(60 if profile == "maximum" else 42, [], f"Recognizer completato · {used}")
    else:
        device = "CPU"
        if engine in {"madmom-deep-chroma", "madmom-cnn-crf"}:
            if progress:
                progress(-1, [], "Caricamento/download modello Madmom / backend AI")
            _proc, device = _madmom_processor(engine)
        if progress:
            progress(30, [], f"Step 2 · riconoscimento base · {engine} · {device}")
        base_events = extract_chords(path, engine=engine)
    if cancelled and cancelled():
        raise InterruptedError("Chord extraction cancelled")
    prepared = [_copy_chord_with_label(x, _limit_chord_vocabulary(x.chord, opts)) for x in base_events]
    if opts.get("harmonic_refinement"):
        if progress:
            progress(64, [], "Step 3 · chroma armonica ad alta risoluzione")
        events = _refine_extended_harmony(path, prepared, progress=progress, cancelled=cancelled, options=opts)
    else:
        events = prepared
        if progress:
            progress(72, [], "Refinement chroma disattivato · mantengo il recognizer")
    if cancelled and cancelled():
        raise InterruptedError("Chord extraction cancelled")
    cleaned = _postprocess_chord_events(events, opts, bpm=bpm, beat_origin_ms=beat_origin_ms)
    if progress:
        progress(90, [], f"Step finale · densità controllata · {len(cleaned)} cambi")
        progress(96, [], "Analisi armonica completata")
    return cleaned

def extract_chords(path: Path, *, interval_ms: int = 500, engine: str | None = None) -> list[Chord]:
    """Extract chord changes using the explicitly selected engine.

    AI engines never silently change to a different engine: callers can therefore
    report exactly which recognizer/model produced the project chord timeline.
    """
    engine=(engine or "mta-chromagram").strip() or "mta-chromagram"
    if engine.startswith("profile-"):
        profile = engine.removeprefix("profile-")
        events, _used = _extract_profile_base(path, profile)
        return events
    if engine == "btc-hcqt":
        from .chord_ml import extract_btc_hcqt
        return extract_btc_hcqt(path)
    if engine == "chordformer":
        from .chord_ml import extract_chordformer
        return extract_chordformer(path)
    if engine in {"madmom-deep-chroma", "madmom-cnn-crf"}:
        return _extract_chords_madmom(path, engine)
    if engine == "chordino":
        chordino=_extract_chords_chordino(path)
        if not chordino:
            from .chordino_runtime import chordino_status
            status = chordino_status()
            reason = status.get("reason") or "unknown"
            host = status.get("host") or "not found"
            diagnostic = str(status.get("diagnostic") or "").strip().replace("\n", " ")[-300:]
            detail = f" · {diagnostic}" if diagnostic else ""
            raise RuntimeError(f"Chordino / NNLS-Chroma unavailable: {reason}; host={host}{detail}")
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


def map_source_events_to_timeline(track: Track, events: list[LyricLine] | list[Chord] | list[Marker]) -> list[LyricLine] | list[Chord] | list[Marker]:
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
                        for syllable in word.get("syllables") or []:
                            syllable["start_ms"] = max(0, int(syllable["start_ms"]) + delta)
                            syllable["end_ms"] = max(syllable["start_ms"], int(syllable["end_ms"]) + delta)
                mapped.append(type(event)(**payload))
    mapped.sort(key=lambda item: item.time_ms)
    return mapped



def extract_markers(path: Path, *, progress: Callable[[int, list[Marker], str], None] | None = None, cancelled: Callable[[], bool] | None = None) -> list[Marker]:
    """Infer coarse musical section boundaries from spectral/energy novelty.

    This is intentionally conservative: it emits section markers, not a marker for
    every local audio change. Users can refine/rename them in the joint editor.
    """
    if cancelled and cancelled():
        raise InterruptedError("Marker extraction cancelled")
    if progress:
        progress(12, [], "Analisi struttura del brano")
    samples, sr = _pcm_mono(path)
    if samples.size < sr * 4:
        return [Marker(time_ms=0, label="Intro")]
    hop = max(1, int(sr * 1.0))
    win = max(hop, int(sr * 2.0))
    energies=[]; centroids=[]; times=[]
    for start in range(0, max(1, len(samples)-win+1), hop):
        if cancelled and cancelled():
            raise InterruptedError("Marker extraction cancelled")
        chunk=samples[start:start+win]
        if len(chunk)<win:
            chunk=np.pad(chunk,(0,win-len(chunk)))
        rms=float(np.sqrt(np.mean(np.square(chunk, dtype=np.float64))+1e-12))
        spec=np.abs(np.fft.rfft(chunk*np.hanning(len(chunk))))
        freqs=np.fft.rfftfreq(len(chunk),1.0/sr)
        centroid=float((spec*freqs).sum()/max(1e-9,spec.sum()))
        energies.append(rms);centroids.append(centroid);times.append(int(start/sr*1000))
    e=np.asarray(energies,dtype=np.float64);c=np.asarray(centroids,dtype=np.float64)
    def z(v):
        return (v-np.median(v))/(np.std(v)+1e-9)
    novelty=np.zeros_like(e)
    if len(e)>1:
        novelty[1:]=np.abs(np.diff(z(e)))+0.45*np.abs(np.diff(z(c)))
    duration_ms=int(len(samples)/sr*1000)
    min_gap_ms=8000
    max_sections=max(2,min(10,int(duration_ms/30000)+2))
    candidates=sorted(range(1,len(novelty)), key=lambda i: float(novelty[i]), reverse=True)
    chosen=[0]
    for idx in candidates:
        t=times[idx]
        if t<5000 or duration_ms-t<5000:
            continue
        if all(abs(t-times[j])>=min_gap_ms for j in chosen):
            chosen.append(idx)
        if len(chosen)>=max_sections:
            break
    chosen=sorted(chosen,key=lambda i:times[i])
    labels=[]
    cycle=["Verse", "Chorus", "Verse", "Chorus", "Bridge", "Chorus"]
    for pos,idx in enumerate(chosen):
        if pos==0: label="Intro"
        elif pos==len(chosen)-1 and duration_ms-times[idx] < 20000: label="Outro"
        else: label=cycle[(pos-1)%len(cycle)]
        labels.append(Marker(time_ms=max(0,times[idx]),label=label))
    if progress:
        progress(96, [], "Marker/sezioni estratti")
    return labels

def synchronized_plain_text(lyrics: list[LyricLine], chords: list[Chord] | None = None) -> str:
    chords = sorted((ch for ch in (chords or []) if not ch.excluded and not getattr(ch, "deleted", False)), key=lambda x: x.time_ms)
    lines: list[str] = []
    ci = 0
    active = ""
    for lyric in sorted((x for x in lyrics if not getattr(x, "disabled", False) and not getattr(x, "deleted", False)), key=lambda x: x.time_ms):
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
    ordered_chords = sorted((ch for ch in chords if not ch.excluded), key=lambda x: x.time_ms)
    ordered_lyrics = sorted((x for x in lyrics if not getattr(x, "disabled", False) and not getattr(x, "deleted", False)), key=lambda x: x.time_ms)
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


def _manual_chord_line_match(chord: Chord, lyric: LyricLine) -> bool:
    return bool(
        chord.manual_anchor
        and chord.anchor_line_time_ms is not None
        and int(chord.anchor_line_time_ms) == int(lyric.time_ms)
    )


def _manual_chord_word_index(chord: Chord, word_count: int) -> int | None:
    if not chord.manual_anchor or chord.anchor_word_index is None or word_count <= 0:
        return None
    return max(0, min(int(chord.anchor_word_index), word_count - 1))


def _pdf_fonts() -> dict[str, str]:
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    candidates = {
        "normal": [Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"), Path("C:/Windows/Fonts/arial.ttf")],
        "bold": [Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"), Path("C:/Windows/Fonts/arialbd.ttf")],
        "italic": [Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Oblique.ttf"), Path("C:/Windows/Fonts/ariali.ttf")],
    }
    names = {"normal": "Helvetica", "bold": "Helvetica-Bold", "italic": "Helvetica-Oblique"}
    for style, paths in candidates.items():
        for candidate in paths:
            if candidate.is_file():
                name = f"MTAUnicode-{style}"
                try:
                    pdfmetrics.registerFont(TTFont(name, str(candidate)))
                    names[style] = name
                    break
                except Exception as exc:
                    logger.debug("Unable to register PDF font %s: %s", candidate, exc)
    return names


def build_lyrics_pdf(
    out: Path, *, title: str, artist: str, lyrics: list[LyricLine], chords: list[Chord],
    chord_color: str = "#7B1FA2", key: str = "", bpm: float | None = None, time_signature: str = "4/4",
    rights_records: list[RightsRecord] | None = None, markers: list[Marker] | None = None,
    pdf_style: dict | None = None,
) -> Path:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.colors import HexColor, black
    from reportlab.pdfgen import canvas

    out.parent.mkdir(parents=True, exist_ok=True)
    fonts = _pdf_fonts()
    default_style = {
        "title": {"style": "bold", "size": 18, "color": "#111111"},
        "subtitle": {"style": "normal", "size": 11, "color": "#333333"},
        "bpm": {"style": "normal", "size": 11, "color": "#333333"},
        "lyrics": {"style": "normal", "size": 11, "color": "#111111"},
        "chords": {"style": "bold", "size": 9, "color": chord_color},
        "markers": {"style": "bold", "size": 12, "color": "#204A87"},
        "line_spacing": 8.0,
    }
    # Preserve direct chord_color compatibility for older callers/tests; project
    # typography may override it below.
    try:
        legacy_chord_fill = HexColor(chord_color)
    except Exception:
        legacy_chord_fill = HexColor("#7B1FA2")
    del legacy_chord_fill
    incoming = pdf_style or {}
    styles = {k: {**v, **(incoming.get(k) or {})} for k, v in default_style.items() if isinstance(v, dict)}
    try:
        line_spacing = max(0.0, min(48.0, float(incoming.get("line_spacing", default_style["line_spacing"]))))
    except (TypeError, ValueError):
        line_spacing = float(default_style["line_spacing"])
    if chord_color and chord_color != "#7B1FA2" and not (incoming.get("chords") or {}).get("color"):
        styles["chords"]["color"] = chord_color

    def st(kind: str) -> tuple[str, float, object]:
        cfg = styles[kind]
        style_name = str(cfg.get("style") or "normal").lower()
        if style_name not in fonts:
            style_name = "normal"
        try:
            color = HexColor(str(cfg.get("color") or "#111111"))
        except Exception:
            color = black
        return fonts[style_name], float(cfg.get("size") or 11), color

    c = canvas.Canvas(str(out), pagesize=A4, pageCompression=1)
    width, height = A4
    margin = 48
    usable_width = width - 2 * margin
    y = height - 54

    def safe(text: str) -> str:
        return str(text or "")

    def set_style(kind: str) -> tuple[str, float]:
        font, size, color = st(kind)
        c.setFont(font, size)
        c.setFillColor(color)
        return font, size

    def new_page() -> None:
        nonlocal y
        c.showPage()
        y = height - 54

    def ensure(space: float) -> None:
        if y - space < 56:
            new_page()

    def wrap_text(text: str, kind: str, max_width: float = usable_width) -> list[str]:
        font, size, _ = st(kind)
        words = safe(text).split()
        if not words:
            return [""]
        lines=[]; line=""
        for word in words:
            candidate=f"{line} {word}".strip()
            if line and c.stringWidth(candidate,font,size)>max_width:
                lines.append(line);line=word
            else:
                line=candidate
        if line: lines.append(line)
        return lines or [""]

    def estimated_words(lyric: LyricLine, line_end: int) -> list[dict]:
        lyric_style = st("lyrics")
        font,size,_ = lyric_style
        words = [w for w in (lyric.words or []) if str(w.text or "").strip()]
        if words:
            source=[{"text":str(w.text).strip(),"start_ms":int(w.start_ms),"end_ms":int(max(w.start_ms,w.end_ms)),"syllables":getattr(w,"syllables",[]) or []} for w in words]
        else:
            tokens=str(lyric.text or "").split()
            start=int(lyric.time_ms); end=max(start+1,int(lyric.end_ms or line_end or start+max(1200,len(tokens)*420)))
            span=end-start
            source=[]
            for i,token in enumerate(tokens):
                source.append({"text":token,"start_ms":round(start+span*i/max(1,len(tokens))),"end_ms":round(start+span*(i+1)/max(1,len(tokens))),"syllables":[]})
        entries=[];x=margin;space=c.stringWidth(" ",font,size)
        for item in source:
            text=safe(item["text"]); w=c.stringWidth(text,font,size)
            if entries and x+w>margin+usable_width:
                # This function models one visual row at a time; callers split by x reset.
                x=margin
            syll=[];sx=x
            raw_syll=item.get("syllables") or []
            for syl in raw_syll:
                sw=c.stringWidth(safe(getattr(syl,"text","")),font,size)
                syll.append({"start_ms":int(getattr(syl,"start_ms",item["start_ms"])),"end_ms":int(getattr(syl,"end_ms",item["end_ms"])),"x":sx,"width":sw})
                sx+=sw
            entries.append({**item,"x":x,"width":w,"syllables":syll})
            x+=w+space
        return entries

    def chord_x(chord: Chord, word_entries: list[dict], line_start: int, line_end: int) -> float:
        if not word_entries:
            rel=max(0,min(1,(int(chord.time_ms)-line_start)/max(1,line_end-line_start)))
            return margin+rel*usable_width
        anchor_kind = str(getattr(chord, "anchor_kind", "word") or "word")
        if chord.manual_anchor and anchor_kind == "start":
            return margin
        if chord.manual_anchor and anchor_kind == "end":
            return margin + usable_width
        manual_index = _manual_chord_word_index(chord, len(word_entries))
        if manual_index is not None:
            entry = word_entries[manual_index]
            syllable_index = getattr(chord, "anchor_syllable_index", None)
            syllables = entry.get("syllables") or []
            if syllable_index is not None and syllables:
                si = max(0, min(int(syllable_index), len(syllables) - 1))
                return syllables[si]["x"]
            char_offset = getattr(chord, "anchor_char_offset", None)
            if char_offset is not None:
                text = str(entry.get("text") or "")
                ci = max(0, min(int(char_offset), len(text)))
                if text:
                    return entry["x"] + c.stringWidth(safe(text[:ci]), *st("lyrics")[:2])
            return word_entries[manual_index]["x"]
        t=int(chord.time_ms)
        for i,w in enumerate(word_entries):
            if w["start_ms"] <= t <= max(w["start_ms"],w["end_ms"]):
                for syl in w.get("syllables") or []:
                    if syl["start_ms"] <= t <= syl["end_ms"]:
                        rel=(t-syl["start_ms"])/max(1,syl["end_ms"]-syl["start_ms"])
                        return syl["x"]+rel*max(3,syl["width"])
                rel=(t-w["start_ms"])/max(1,w["end_ms"]-w["start_ms"])
                return w["x"]+rel*max(4,w["width"])
            if i+1<len(word_entries) and w["end_ms"] < t < word_entries[i+1]["start_ms"]:
                rel=(t-w["end_ms"])/max(1,word_entries[i+1]["start_ms"]-w["end_ms"])
                return (w["x"]+w["width"])+rel*max(4,word_entries[i+1]["x"]-(w["x"]+w["width"]))
        # Do not snap an automatic chord that occurs before the first sung word
        # onto that word. Pre-lyric chords require an explicit line-start anchor.
        if t < word_entries[0]["start_ms"]:
            return float("nan")
        return word_entries[-1]["x"]+word_entries[-1]["width"]

    def marker_color(marker: Marker):
        try:
            return HexColor(str(getattr(marker, "color", "") or styles["markers"]["color"]))
        except Exception:
            return st("markers")[2]

    def draw_marker(marker: Marker) -> object:
        nonlocal y
        ensure(30)
        font,size,_ = st("markers")
        c.setFont(font, size)
        color = marker_color(marker)
        c.setFillColor(color)
        label=safe(marker.label).strip()
        if label and not label.endswith(":"):
            label += ":"
        c.drawString(margin,y,label)
        y -= max(18,size+8)
        return color

    c.setTitle(title or "Lyrics")
    if artist: c.setAuthor(artist)
    title_font,title_size=set_style("title")
    c.drawString(margin,y,safe(title or "Lyrics"));y-=title_size+10
    # Subtitle data kept separate from BPM so each can be styled independently.
    subtitle_parts=[]
    if artist: subtitle_parts.append(artist)
    if key: subtitle_parts.append(f"Key: {key}")
    if subtitle_parts:
        f,s=set_style("subtitle");c.drawString(margin,y,safe("  ·  ".join(subtitle_parts)));y-=s+8
    meta_parts=[]
    if bpm is not None and float(bpm)>0:
        meta_parts.append(f"BPM: {int(round(float(bpm)))}")
    if time_signature:
        meta_parts.append(f"Time signature: {time_signature}")
    if meta_parts:
        f,s=set_style("bpm");c.drawString(margin,y,"  ·  ".join(meta_parts));y-=s+8
    # Requested visual breathing room between title/metadata and the song body.
    y -= 22

    active_lyrics=[x for x in lyrics if not getattr(x,"disabled",False) and not getattr(x,"deleted",False)]
    # Keep disabled lyrics as timing boundaries even though they are not rendered.
    # Otherwise the previous visible lyric line expands across the disabled line
    # and can steal/lose chords that belong to a different time window.
    boundary_lyrics=sorted((x for x in lyrics if not getattr(x,"deleted",False)), key=lambda x:x.time_ms)
    boundary_times=[int(x.time_ms) for x in boundary_lyrics]
    active_chords=[x for x in chords if not getattr(x,"excluded",False) and not getattr(x,"deleted",False)]
    active_markers=[x for x in (markers or []) if not getattr(x,"disabled",False) and not getattr(x,"deleted",False)]
    ordered_lyrics=sorted(_estimated_word_and_syllable_timing(active_lyrics),key=lambda x:x.time_ms)
    ordered_chords=sorted(active_chords,key=lambda x:x.time_ms)
    ordered_markers=sorted(active_markers,key=lambda x:x.time_ms)
    marker_idx=0
    current_section_color = None

    for i,lyric in enumerate(ordered_lyrics):
        line_start=int(lyric.time_ms)
        next_boundary=next((t for t in boundary_times if t>line_start), None)
        line_end=int(next_boundary if next_boundary is not None else (lyric.end_ms or line_start+6000))
        while marker_idx<len(ordered_markers) and int(ordered_markers[marker_idx].time_ms)<=line_start:
            current_section_color = draw_marker(ordered_markers[marker_idx]);marker_idx+=1
        words=estimated_words(lyric,line_end)
        lyric_lines=wrap_text(lyric.text,"lyrics")
        line_chords=[ch for ch in ordered_chords if _manual_chord_line_match(ch, lyric) or (not ch.manual_anchor and line_start<=ch.time_ms<line_end)]
        # Never carry a previous automatic chord onto the next lyric line.
        # A chord before the first word must be explicitly anchored to line start.
        if words:
            first_word_start = int(words[0].get("start_ms", line_start))
            manual_first = any(
                ch.manual_anchor
                and str(getattr(ch, "anchor_kind", "word") or "word") == "word"
                and int(getattr(ch, "anchor_word_index", 0) or 0) == 0
                for ch in line_chords
            )
            line_chords = [
                ch for ch in line_chords
                if ch.manual_anchor or int(ch.time_ms) >= first_word_start
            ]
            if manual_first:
                line_chords = [
                    ch for ch in line_chords
                    if ch.manual_anchor
                    or not (first_word_start <= int(ch.time_ms) <= int(words[0].get("end_ms", first_word_start)))
                ]
        chord_font,chord_size,_ = st("chords")
        if line_chords:
            # ensure() may call showPage(), which resets ReportLab graphics state.
            # Perform the page break before applying the chord font/color so a
            # page beginning with chords uses the exact same style as any other row.
            ensure(chord_size+16)
            c.setFont(chord_font, chord_size)
            # Chords always use their own PDF style; marker/section colors never leak into them.
            c.setFillColor(st("chords")[2])
            positioned=[(chord_x(ch, words, line_start, line_end), ch) for ch in line_chords]
            positioned=[(x,ch) for x,ch in positioned if x == x]
            positioned.sort(key=lambda item: (item[0], int(getattr(item[1], "anchor_order", 0)), int(item[1].time_ms)))
            if positioned:
                prev_right=margin-8
                for x,ch in positioned:
                    label=safe(ch.chord)
                    tw=c.stringWidth(label,chord_font,chord_size)
                    x=max(prev_right+5,min(x,margin+usable_width-tw))
                    c.drawString(x,y,label);prev_right=x+tw
                y-=chord_size+7
        lyric_font,lyric_size,_ = st("lyrics")
        c.setFont(lyric_font, lyric_size)
        c.setFillColor(current_section_color or st("lyrics")[2])
        for part in lyric_lines:
            ensure(lyric_size+8)
            c.drawString(margin,y,safe(part));y-=lyric_size+6
        y-=line_spacing

    while marker_idx<len(ordered_markers):
        current_section_color = draw_marker(ordered_markers[marker_idx]);marker_idx+=1

    if rights_records:
        ensure(80);y-=8;c.setFillColor(black);c.setFont(fonts["bold"],10);c.drawString(margin,y,"Dati repertorio / Rights information");y-=16
        c.setFont(fonts["normal"],8)
        for record in rights_records:
            ensure(28)
            identifiers=", ".join(f"{k}: {v}" for k,v in record.identifiers.items())
            parts=[f"Provider: {record.society}" if record.society else "",f"UID: {record.uid}" if record.uid else "",f"Titolo: {record.title}" if record.title else "",f"Autori: {', '.join(record.authors)}" if record.authors else "",f"Identificativi: {identifiers}" if identifiers else ""]
            for part in wrap_text(" · ".join(x for x in parts if x),"subtitle"):
                c.drawString(margin,y,safe(part));y-=11
            y-=4
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
    ordered = sorted((x for x in lyrics if not getattr(x, "disabled", False) and not getattr(x, "deleted", False)), key=lambda x: x.time_ms)
    chord_rows = sorted((ch for ch in (chords or []) if not ch.excluded and not getattr(ch, "deleted", False)), key=lambda x: x.time_ms)
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
