from __future__ import annotations

import re
import subprocess
import tempfile
import uuid
import wave
from pathlib import Path

import numpy as np

from .models import Clip, Project, Track
from .plugins import chain_filter, effective_output_channels


def _run(cmd: list[str]) -> str:
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if proc.returncode:
        raise RuntimeError(proc.stderr.strip() or "audio command failed")
    return proc.stdout


def media_duration_ms(path: Path) -> int:
    out = _run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", str(path)]
    ).strip()
    try:
        return max(0, round(float(out) * 1000))
    except (TypeError, ValueError):
        return 0


def ensure_clips(track: Track) -> None:
    if not track.clips and track.duration_ms > 0:
        track.clips = [
            Clip(id=uuid.uuid4().hex[:10], source_start_ms=0, source_end_ms=track.duration_ms, timeline_start_ms=0)
        ]


def project_duration_ms(project: Project) -> int:
    end_ms = 0
    for track in project.tracks:
        ensure_clips(track)
        if track.clips:
            end_ms = max(
                end_ms,
                max((max(0, clip.timeline_start_ms + int(getattr(track, "delay_ms", 0) or 0)) + clip.duration_ms) for clip in track.clips),
            )
        else:
            end_ms = max(end_ms, track.duration_ms)
    return max(0, int(end_ms))


def generate_metronome_wav(project: Project, out: Path, beats_per_bar: int | None = None) -> int:
    """Generate a mono PCM click track honoring the project's time signature.

    Project BPM represents the audible metronome pulse rate. The time-signature
    numerator controls how pulses are grouped into bars and the denominator
    controls notation/accent grouping; changing 4/4 to 6/8 must not silently
    double the click rate. Compound /8 meters receive secondary accents every
    three subdivisions.
    """
    duration_ms = project_duration_ms(project)
    if duration_ms <= 0:
        raise ValueError("project duration is zero")
    sample_rate = 44100
    total_samples = max(1, round(duration_ms / 1000 * sample_rate))
    try:
        numerator_text, denominator_text = str(getattr(project, "time_signature", "4/4") or "4/4").split("/", 1)
        numerator, denominator = int(numerator_text), int(denominator_text)
    except (TypeError, ValueError):
        numerator, denominator = 4, 4
    beats_per_bar = max(1, int(beats_per_bar or numerator))
    # BPM is the audible pulse/subdivision rate. A meter change must never
    # multiply the playback speed merely because the denominator changes.
    beat_seconds = 60.0 / float(project.bpm)
    beat_samples = max(1, round(beat_seconds * sample_rate))
    click_len = min(max(1, round(0.045 * sample_rate)), beat_samples)
    silence_chunk = b"\x00\x00" * 8192

    def click_bytes(freq: float) -> bytes:
        t = np.arange(click_len, dtype=np.float64) / sample_rate
        env = np.exp(-t * 55.0)
        wave_data = np.sin(2 * np.pi * freq * t) * env
        peak = float(np.max(np.abs(wave_data))) if wave_data.size else 0.0
        if peak > 0.0:
            wave_data /= peak  # generated click is peak-normalized to exactly 0 dBFS
        return np.asarray(np.clip(wave_data, -1, 1) * 32767, dtype=np.int16).tobytes()

    accent = click_bytes(1320.0)
    secondary_accent = click_bytes(1100.0)
    regular = click_bytes(880.0)
    out.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(out), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(sample_rate)
        cursor = 0
        beat_index = 0
        next_beat = 0
        while cursor < total_samples:
            if next_beat >= total_samples:
                remaining = total_samples - cursor
                while remaining > 0:
                    count = min(8192, remaining)
                    handle.writeframesraw(silence_chunk[: count * 2])
                    cursor += count
                    remaining -= count
                break
            if next_beat > cursor:
                remaining = next_beat - cursor
                while remaining > 0:
                    count = min(8192, remaining)
                    handle.writeframesraw(silence_chunk[: count * 2])
                    cursor += count
                    remaining -= count
            pos_in_bar = beat_index % beats_per_bar
            if pos_in_bar == 0:
                click = accent
            elif denominator == 8 and numerator in {6, 9, 12} and pos_in_bar % 3 == 0:
                click = secondary_accent
            else:
                click = regular
            samples_to_write = min(click_len, total_samples - cursor)
            handle.writeframesraw(click[: samples_to_write * 2])
            cursor += samples_to_write
            beat_index += 1
            next_beat = beat_index * beat_samples
        handle.writeframes(b"")
    return duration_ms


def delete_range(track: Track, start_ms: int, end_ms: int, ripple: bool) -> None:
    if end_ms <= start_ms:
        raise ValueError("end must be after start")
    ensure_clips(track)
    cut = end_ms - start_ms
    out: list[Clip] = []
    for clip in track.clips:
        cs, ce = clip.timeline_start_ms, clip.timeline_start_ms + clip.duration_ms
        if ce <= start_ms:
            out.append(clip)
            continue
        if cs >= end_ms:
            if ripple:
                clip.timeline_start_ms -= cut
            out.append(clip)
            continue
        if cs < start_ms:
            left_len = start_ms - cs
            out.append(
                Clip(
                    id=uuid.uuid4().hex[:10],
                    source_start_ms=clip.source_start_ms,
                    source_end_ms=clip.source_start_ms + left_len,
                    timeline_start_ms=cs,
                )
            )
        if ce > end_ms:
            removed_from_clip = end_ms - cs
            out.append(
                Clip(
                    id=uuid.uuid4().hex[:10],
                    source_start_ms=clip.source_start_ms + removed_from_clip,
                    source_end_ms=clip.source_end_ms,
                    timeline_start_ms=start_ms if ripple else end_ms,
                )
            )
    track.clips = sorted((item for item in out if item.duration_ms > 0), key=lambda item: item.timeline_start_ms)


def shift_track(track: Track, delta_ms: int) -> None:
    ensure_clips(track)
    if delta_ms >= 0:
        for clip in track.clips:
            clip.timeline_start_ms += delta_ms
        return
    amount = -delta_ms
    new: list[Clip] = []
    for clip in track.clips:
        if clip.timeline_start_ms + clip.duration_ms <= amount:
            continue
        if clip.timeline_start_ms < amount:
            trim = amount - clip.timeline_start_ms
            clip.source_start_ms += trim
            clip.timeline_start_ms = 0
        else:
            clip.timeline_start_ms -= amount
        if clip.duration_ms > 0:
            new.append(clip)
    track.clips = new


def _shift_timed(items, start_ms: int, end_ms: int):
    cut = end_ms - start_ms
    out = []
    for item in items:
        if item.time_ms < start_ms:
            out.append(item)
        elif item.time_ms >= end_ms:
            item.time_ms -= cut
            out.append(item)
    return out


def delete_song_range(project: Project, start_ms: int, end_ms: int) -> None:
    for track in project.tracks:
        delete_range(track, start_ms, end_ms, True)
    project.markers = _shift_timed(project.markers, start_ms, end_ms)
    project.lyrics = _shift_timed(project.lyrics, start_ms, end_ms)
    project.chords = _shift_timed(project.chords, start_ms, end_ms)


def render_track(track: Track, source: Path, out: Path, apply_inserts: bool = True) -> None:
    """Render DAW clips for one track and apply its insert chain.

    Track fader/pan/mute/solo are intentionally not baked here; they are handled
    by the container exporter or final mix stage.
    """
    ensure_clips(track)
    if not track.clips:
        _run(
            [
                "ffmpeg",
                "-y",
                "-v",
                "error",
                "-f",
                "lavfi",
                "-i",
                "anullsrc=r=44100:cl=stereo",
                "-t",
                "0.05",
                "-c:a",
                "pcm_s16le",
                str(out),
            ]
        )
        return
    parts: list[str] = []
    labels: list[str] = []
    source_layout = "mono" if int(track.channels or 0) == 1 else "stereo"
    track_delay = int(getattr(track, "delay_ms", 0) or 0)
    for index, clip in enumerate(track.clips):
        source_start_ms = int(clip.source_start_ms)
        source_end_ms = int(clip.source_end_ms)
        timeline_start_ms = int(clip.timeline_start_ms) + track_delay
        # Negative track delays are non-destructive: audio that would begin before
        # project time zero is trimmed only in the rendered/playback view.
        if timeline_start_ms < 0:
            trim_ms = min(source_end_ms - source_start_ms, -timeline_start_ms)
            source_start_ms += trim_ms
            timeline_start_ms = 0
        if source_end_ms <= source_start_ms:
            continue
        start = source_start_ms / 1000
        end = source_end_ms / 1000
        delay = max(0, timeline_start_ms)
        parts.append(
            f"[0:a]atrim=start={start:.6f}:end={end:.6f},asetpts=PTS-STARTPTS,"
            f"adelay={delay}|{delay},aformat=channel_layouts={source_layout}[c{index}]"
        )
        labels.append(f"[c{index}]")
    if not labels:
        _run([
            "ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i",
            "anullsrc=r=44100:cl=stereo", "-t", "0.05", "-c:a", "pcm_s16le", str(out),
        ])
        return
    if len(labels) == 1:
        base = parts[0] + f";{labels[0]}anull[mix]"
    else:
        base = ";".join(parts) + ";" + "".join(labels) + f"amix=inputs={len(labels)}:duration=longest:normalize=0[mix]"
    inserts = chain_filter(track.inserts) if apply_inserts else ""
    output_channels = effective_output_channels(track.channels, track.inserts if apply_inserts else [])
    output_layout = "mono" if output_channels == 1 else "stereo"
    filters = base + (
        f";[mix]{inserts},aformat=channel_layouts={output_layout}[out]"
        if inserts
        else f";[mix]aformat=channel_layouts={output_layout}[out]"
    )
    _run(
        [
            "ffmpeg",
            "-y",
            "-v",
            "error",
            "-i",
            str(source),
            "-filter_complex",
            filters,
            "-map",
            "[out]",
            "-ar",
            "44100",
            "-c:a",
            "pcm_s24le",
            str(out),
        ]
    )


def render_mix(
    project: Project,
    audio_resolver,
    out: Path,
    fmt: str = "mp3",
    bitrate: str = "320k",
    *,
    sample_rate: int = 44100,
    wav_bit_depth: int = 24,
    flac_compression: int = 8,
    normalize_peak_db: float | None = None,
) -> Path:
    """Render stereo master for preview/WAV/MP3/FLAC export."""
    if not project.tracks:
        raise ValueError("project has no audio tracks")
    fmt = fmt.lower()
    if fmt not in {"wav", "mp3", "flac"}:
        raise ValueError("unsupported mix format")
    with tempfile.TemporaryDirectory() as td_raw:
        td = Path(td_raw)
        rendered: list[Path] = []
        for index, track in enumerate(project.tracks):
            path = td / f"track-{index:02d}.wav"
            render_track(track, audio_resolver(project.id, track.filename), path, apply_inserts=True)
            rendered.append(path)
        cmd = ["ffmpeg", "-y", "-v", "error"]
        for path in rendered:
            cmd += ["-i", str(path)]
        any_solo = any(track.solo for track in project.tracks)
        filters: list[str] = []
        labels: list[str] = []
        for index, track in enumerate(project.tracks):
            muted = track.mute or (any_solo and not track.solo)
            gain = -120.0 if muted else track.volume_db
            pan = min(1.0, max(-1.0, track.pan))
            label = f"t{index}"
            filters.append(
                f"[{index}:a]aformat=channel_layouts=stereo,volume={gain:.3f}dB,"
                f"stereotools=balance_out={pan:.4f}[{label}]"
            )
            labels.append(f"[{label}]")
        filters.append("".join(labels) + f"amix=inputs={len(labels)}:duration=longest:normalize=0[master0]")
        master_chain = chain_filter(project.master_inserts)
        tail = f"volume={project.master_volume_db:.3f}dB"
        if master_chain:
            tail += "," + master_chain
        tail += "," + project_time_pitch_filter(project)
        filters.append(f"[master0]{tail}[master]")
        sample_rate = 48000 if int(sample_rate) == 48000 else 44100
        cmd += ["-filter_complex", ";".join(filters), "-map", "[master]", "-ar", str(sample_rate)]

        def _codec_args(target: Path) -> list[str]:
            if fmt == "wav":
                codec = {16: "pcm_s16le", 24: "pcm_s24le", 32: "pcm_f32le"}.get(int(wav_bit_depth), "pcm_s24le")
                return ["-c:a", codec, str(target)]
            if fmt == "flac":
                level = max(0, min(12, int(flac_compression)))
                return ["-c:a", "flac", "-compression_level", str(level), str(target)]
            return ["-c:a", "libmp3lame", "-b:a", bitrate, str(target)]

        if normalize_peak_db is None:
            _run(cmd + _codec_args(out))
        else:
            # Peak-normalize only after the complete master chain has been rendered.
            # This avoids changing the relative balance between tracks and applies the
            # requested dBFS target consistently to WAV/MP3/FLAC.
            target_db = max(-30.0, min(0.0, float(normalize_peak_db)))
            master_wav = td / "master-before-normalize.wav"
            _run(cmd + ["-c:a", "pcm_f32le", str(master_wav)])
            probe = subprocess.run(
                ["ffmpeg", "-hide_banner", "-v", "info", "-i", str(master_wav), "-af", "volumedetect", "-f", "null", "-"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            if probe.returncode:
                raise RuntimeError(probe.stderr.strip() or "normalization analysis failed")
            match = re.search(r"max_volume:\s*(-?\d+(?:\.\d+)?)\s*dB", probe.stderr)
            gain_db = 0.0
            if match:
                gain_db = target_db - float(match.group(1))
            encode = ["ffmpeg", "-y", "-v", "error", "-i", str(master_wav)]
            if abs(gain_db) > 0.0001:
                encode += ["-af", f"volume={gain_db:.4f}dB"]
            encode += ["-ar", str(sample_rate)] + _codec_args(out)
            _run(encode)
    return out


def _envelope(path: Path, sample_rate: int = 4000, max_seconds: int = 1200):
    with tempfile.TemporaryDirectory() as td:
        wav_path = Path(td) / "x.wav"
        _run(
            [
                "ffmpeg",
                "-y",
                "-v",
                "error",
                "-i",
                str(path),
                "-ac",
                "1",
                "-ar",
                str(sample_rate),
                "-t",
                str(max_seconds),
                "-c:a",
                "pcm_s16le",
                str(wav_path),
            ]
        )
        with wave.open(str(wav_path), "rb") as handle:
            data = np.frombuffer(handle.readframes(handle.getnframes()), dtype=np.int16).astype(np.float32)
    if not len(data):
        return np.zeros(1, dtype=np.float32), 20
    frame = max(1, sample_rate // 20)
    count = len(data) // frame
    data = data[: count * frame].reshape(count, frame)
    env = np.sqrt(np.mean(data * data, axis=1) + 1e-6)
    env = np.diff(np.log1p(env), prepend=env[:1])
    env = (env - env.mean()) / (env.std() + 1e-6)
    return env.astype(np.float32), 20




def waveform_peaks(path: Path, points: int = 4096, progress=None) -> list[float]:
    """Return a normalized signed min/max envelope for persistent timeline drawing.

    Each logical waveform bin is stored as two consecutive floats: ``min, max``.
    Keeping both extrema preserves the real asymmetry and transients of the signal,
    unlike the legacy absolute-peak representation.  Older projects containing the
    legacy positive-only array remain readable by the frontend and are regenerated
    automatically because the waveform revision includes the envelope format version.
    """
    points = max(256, min(4096, int(points)))
    if progress:
        progress(5, "Preparazione waveform")
    with tempfile.TemporaryDirectory() as td:
        wav_path = Path(td) / "waveform.wav"
        _run(
            [
                "ffmpeg", "-y", "-v", "error", "-i", str(path),
                "-ac", "1", "-ar", "8000", "-c:a", "pcm_s16le", str(wav_path),
            ]
        )
        if progress:
            progress(45, "Calcolo envelope waveform")
        with wave.open(str(wav_path), "rb") as handle:
            data = np.frombuffer(handle.readframes(handle.getnframes()), dtype=np.int16).astype(np.float32)
    if not len(data):
        return [0.0] * (points * 2)
    peak = float(np.max(np.abs(data))) or 1.0
    edges = np.linspace(0, len(data), points + 1, dtype=np.int64)
    out: list[float] = []
    for i in range(points):
        a, b = int(edges[i]), int(edges[i + 1])
        if b > a:
            chunk = data[a:b]
            lo = float(np.min(chunk)) / peak
            hi = float(np.max(chunk)) / peak
        else:
            lo = hi = 0.0
        out.extend((round(max(-1.0, min(1.0, lo)), 5), round(max(-1.0, min(1.0, hi)), 5)))
    if progress:
        progress(95, "Waveform pronta")
    return out


def _atempo_chain(ratio: float) -> str:
    ratio = max(0.05, min(20.0, float(ratio)))
    parts: list[str] = []
    while ratio < 0.5:
        parts.append("atempo=0.5")
        ratio /= 0.5
    while ratio > 2.0:
        parts.append("atempo=2.0")
        ratio /= 2.0
    parts.append(f"atempo={ratio:.8f}")
    return ",".join(parts)


def project_time_pitch_filter(project: Project) -> str:
    """Build an FFmpeg filter that changes tempo and pitch independently."""
    base_bpm = project.base_bpm or project.bpm or 120.0
    tempo_ratio = max(0.25, min(4.0, float(project.bpm) / float(base_bpm)))
    semitones = max(-6.0, min(6.0, float(project.pitch_semitones)))
    pitch_ratio = 2.0 ** (semitones / 12.0)
    # asetrate changes tempo and pitch together; atempo compensates tempo to the
    # desired ratio while preserving the selected pitch shift.
    rate = 44100.0 * pitch_ratio
    tempo_after_rate = tempo_ratio / pitch_ratio
    return f"asetrate={rate:.6f},aresample=44100,{_atempo_chain(tempo_after_rate)}"


def _rhythm_onset_envelope(path: Path, progress=None) -> tuple[np.ndarray, float]:
    if progress:
        progress(5, "Preparazione audio per la stima BPM/tempo")
    with tempfile.TemporaryDirectory() as td:
        wav_path = Path(td) / "bpm.wav"
        _run([
            "ffmpeg", "-y", "-v", "error", "-i", str(path),
            "-ac", "1", "-ar", "4000", "-t", "240",
            "-c:a", "pcm_s16le", str(wav_path),
        ])
        if progress:
            progress(30, "Analisi dell'energia ritmica")
        with wave.open(str(wav_path), "rb") as handle:
            sr = handle.getframerate()
            data = np.frombuffer(handle.readframes(handle.getnframes()), dtype=np.int16).astype(np.float32)
    if len(data) < sr * 4:
        raise ValueError("audio too short for BPM estimation")
    data /= max(1.0, float(np.max(np.abs(data))))
    hop = max(1, sr // 100)
    n = len(data) // hop
    x = data[: n * hop].reshape(n, hop)
    rms = np.sqrt(np.mean(x * x, axis=1) + 1e-9)
    onset = np.maximum(0.0, np.diff(rms, prepend=rms[:1]))
    onset -= onset.mean()
    std = onset.std()
    if std > 1e-9:
        onset /= std
    return onset, 100.0


def _estimate_meter(onset: np.ndarray, hz: float, beat_lag: int, preferred_signature: str = "") -> str:
    """Estimate a conservative time signature from periodic accent structure.

    4/4 is deliberately favored unless another candidate has clearly stronger
    bar-level periodicity, matching the application's default assumption.
    """
    candidates = {"4/4": 4.0, "3/4": 3.0, "6/8": 6.0, "2/4": 2.0, "5/4": 5.0, "7/8": 7.0, "9/8": 9.0, "12/8": 12.0}
    corr = np.correlate(onset, onset, mode="full")[len(onset)-1:]
    base = max(1e-9, float(corr[beat_lag]) if beat_lag < len(corr) else 1.0)
    scores: dict[str, float] = {}
    for sig, beats in candidates.items():
        lag = int(round(beat_lag * beats))
        if lag <= 0 or lag >= len(corr):
            scores[sig] = -1.0
            continue
        # Bar periodicity plus a mild preference only when the caller explicitly
        # supplied a meter. Automatic analysis must not silently bias every track
        # toward 4/4.
        score = float(corr[lag]) / base
        if preferred_signature and sig == preferred_signature:
            score += 0.10
        if not preferred_signature and sig == "4/4":
            score += 0.015
        scores[sig] = score
    best = max(scores, key=scores.get)
    # Only leave 4/4/default if the alternative is meaningfully stronger.
    if preferred_signature in scores:
        preferred = preferred_signature
        if best != preferred and scores[best] < scores[preferred] + 0.08:
            return preferred
    return best


def estimate_bpm_and_signature(path: Path, progress=None, preferred_signature: str = "") -> tuple[float, str]:
    onset, hz = _rhythm_onset_envelope(path, progress)
    if progress:
        progress(55, "Ricerca della periodicità e del tempo musicale")
    min_bpm, max_bpm = 55.0, 200.0
    min_lag = max(1, int(hz * 60.0 / max_bpm))
    max_lag = max(min_lag + 1, int(hz * 60.0 / min_bpm))
    corr = np.correlate(onset, onset, mode="full")[len(onset)-1:]
    window = corr[min_lag:max_lag+1]
    if not len(window) or not np.isfinite(window).any():
        raise ValueError("unable to estimate BPM")
    lag = min_lag + int(np.nanargmax(window))
    bpm = 60.0 * hz / lag
    while bpm < 70:
        bpm *= 2
        lag = max(1, int(round(hz * 60.0 / bpm)))
    while bpm > 180:
        bpm /= 2
        lag = max(1, int(round(hz * 60.0 / bpm)))
    signature = _estimate_meter(onset, hz, lag, preferred_signature or "")
    if progress:
        progress(90, f"BPM stimati: {bpm:.1f} · tempo {signature}")
    return round(float(bpm), 1), signature


def estimate_bpm(path: Path, progress=None, preferred_signature: str = "4/4") -> float:
    return estimate_bpm_and_signature(path, progress, preferred_signature)[0]

def _xcorr_fft(a, b):
    count = len(a) + len(b) - 1
    size = 1 << (count - 1).bit_length()
    return np.fft.irfft(np.fft.rfft(a, size) * np.fft.rfft(b[::-1], size), size)[:count]



_CHORD_ROOTS = {
    "C": 0, "C#": 1, "DB": 1, "D": 2, "D#": 3, "EB": 3, "E": 4,
    "F": 5, "F#": 6, "GB": 6, "G": 7, "G#": 8, "AB": 8, "A": 9,
    "A#": 10, "BB": 10, "B": 11,
}

def _chord_midi_notes(symbol: str) -> list[int]:
    """Return a compact piano voicing for a common chord symbol.

    Unknown/unsupported decorations fall back to a major/minor triad when the
    root can be identified. Slash bass is honoured when present.
    """
    raw = str(symbol or "").strip().replace("♯", "#").replace("♭", "b")
    if not raw or raw.upper() in {"N", "NC", "N.C.", "NOCHORD"}:
        return []
    m = re.match(r"^([A-Ga-g])([#b]?)([^/]*)?(?:/([A-Ga-g])([#b]?))?$", raw)
    if not m:
        return []
    root_name = (m.group(1).upper() + (m.group(2) or "")).upper()
    root_pc = _CHORD_ROOTS.get(root_name)
    if root_pc is None:
        return []
    quality = (m.group(3) or "").lower().replace(" ", "")
    if "dim" in quality or "°" in quality:
        intervals = [0, 3, 6]
    elif "aug" in quality or "+" in quality:
        intervals = [0, 4, 8]
    elif "sus2" in quality:
        intervals = [0, 2, 7]
    elif "sus" in quality:
        intervals = [0, 5, 7]
    elif re.match(r"^(m|min)(?!aj)", quality):
        intervals = [0, 3, 7]
    else:
        intervals = [0, 4, 7]
    if "maj7" in quality or "ma7" in quality or "△7" in quality:
        intervals.append(11)
    elif "7" in quality:
        intervals.append(10)
    elif "6" in quality:
        intervals.append(9)
    if "9" in quality:
        intervals.append(14)
    # Middle-register voicing, deliberately conservative to avoid clipping.
    root_midi = 48 + root_pc  # C3..B3
    notes = [root_midi + i for i in intervals]
    bass = m.group(4)
    if bass:
        bass_name = (bass.upper() + (m.group(5) or "")).upper()
        bass_pc = _CHORD_ROOTS.get(bass_name)
        if bass_pc is not None:
            notes.insert(0, 36 + bass_pc)
    return sorted(dict.fromkeys(notes))


def generate_chords_piano_wav(project: Project, out: Path) -> int:
    """Render active project chords as a synchronized digital-piano guide track."""
    duration_ms = project_duration_ms(project)
    if duration_ms <= 0:
        raise ValueError("project duration is zero")
    events = sorted(
        [c for c in project.chords if not getattr(c, "excluded", False) and not getattr(c, "deleted", False)],
        key=lambda c: int(c.time_ms),
    )
    if not events:
        raise ValueError("project has no active chords")
    sample_rate = 44100
    total = max(1, round(duration_ms / 1000.0 * sample_rate))
    audio = np.zeros((total, 2), dtype=np.float64)
    for index, chord in enumerate(events):
        start_ms = max(0, int(chord.time_ms))
        if start_ms >= duration_ms:
            continue
        next_ms = int(events[index + 1].time_ms) if index + 1 < len(events) else duration_ms
        # Leave a tiny articulation gap while still following the chord list exactly.
        end_ms = min(duration_ms, max(start_ms + 120, next_ms))
        note_ms = max(90, end_ms - start_ms)
        start = round(start_ms / 1000.0 * sample_rate)
        frames = min(total - start, round(note_ms / 1000.0 * sample_rate))
        if frames <= 0:
            continue
        notes = _chord_midi_notes(chord.chord)
        if not notes:
            continue
        t = np.arange(frames, dtype=np.float64) / sample_rate
        # Fast piano attack, dual exponential decay and a short release at the next chord.
        attack = np.minimum(1.0, t / 0.008)
        env = attack * (0.72 * np.exp(-t * 1.35) + 0.28 * np.exp(-t * 0.24))
        release_len = min(frames, round(0.08 * sample_rate))
        if release_len > 1:
            env[-release_len:] *= np.linspace(1.0, 0.0, release_len)
        mono = np.zeros(frames, dtype=np.float64)
        for ni, midi in enumerate(notes):
            freq = 440.0 * (2.0 ** ((midi - 69) / 12.0))
            # Additive electric/digital-piano timbre, with progressively softer harmonics.
            phase = 0.13 * ni
            tone = (
                np.sin(2 * np.pi * freq * t + phase)
                + 0.34 * np.sin(2 * np.pi * freq * 2.0 * t + phase * 1.7)
                + 0.12 * np.sin(2 * np.pi * freq * 3.0 * t + phase * 2.1)
            )
            mono += tone / max(1.0, len(notes) ** 0.72)
        mono *= env * 0.21
        # Subtle stereo spread by voicing index; preserves mono compatibility.
        pan = -0.16 if index % 2 == 0 else 0.16
        left = mono * np.sqrt((1.0 - pan) * 0.5)
        right = mono * np.sqrt((1.0 + pan) * 0.5)
        audio[start:start + frames, 0] += left
        audio[start:start + frames, 1] += right
    peak = float(np.max(np.abs(audio))) if audio.size else 0.0
    if peak > 0.0:
        audio /= peak  # generated piano guide is peak-normalized to exactly 0 dBFS
    pcm = np.asarray(np.clip(audio, -1.0, 1.0) * 32767.0, dtype=np.int16)
    out.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(out), "wb") as handle:
        handle.setnchannels(2)
        handle.setsampwidth(2)
        handle.setframerate(sample_rate)
        handle.writeframes(pcm.tobytes())
    return duration_ms

def auto_align_ms(reference: Path, candidate: Path, max_shift_ms: int = 30000) -> int:
    a, hz = _envelope(reference)
    b, _ = _envelope(candidate)
    correlation = _xcorr_fft(a, b)
    lags = np.arange(-(len(b) - 1), len(a))
    max_frames = max(1, round(max_shift_ms / 1000 * hz))
    mask = np.abs(lags) <= max_frames
    if not mask.any():
        return 0
    lag = int(lags[mask][int(np.argmax(correlation[mask]))])
    return round(lag * 1000 / hz)



def render_track_export(
    track: Track,
    source: Path,
    out: Path,
    fmt: str = "wav",
    bitrate: str = "320k",
    *,
    project: Project | None = None,
    apply_inserts: bool = True,
) -> Path:
    """Render a single track as heard at track output, optionally with project tempo/pitch."""
    fmt = fmt.lower()
    if fmt not in {"wav", "mp3", "flac"}:
        raise ValueError("unsupported track export format")
    with tempfile.TemporaryDirectory() as td_raw:
        td = Path(td_raw)
        rendered = td / "track.wav"
        render_track(track, source, rendered, apply_inserts=apply_inserts)
        gain = -120.0 if track.mute else track.volume_db
        pan = min(1.0, max(-1.0, track.pan))
        filters = [f"volume={gain:.3f}dB", f"stereotools=balance_out={pan:.4f}"]
        if project is not None:
            filters.append(project_time_pitch_filter(project))
        cmd = ["ffmpeg", "-y", "-v", "error", "-i", str(rendered), "-af", ",".join(filters), "-ar", "44100"]
        if fmt == "wav":
            cmd += ["-c:a", "pcm_s24le", str(out)]
        elif fmt == "flac":
            cmd += ["-c:a", "flac", "-compression_level", "8", str(out)]
        else:
            cmd += ["-c:a", "libmp3lame", "-b:a", bitrate, str(out)]
        _run(cmd)
    return out
