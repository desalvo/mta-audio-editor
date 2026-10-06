from __future__ import annotations

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


def generate_metronome_wav(project: Project, out: Path, beats_per_bar: int = 4) -> int:
    """Generate a mono PCM click track for the full current project duration."""
    duration_ms = project_duration_ms(project)
    if duration_ms <= 0:
        raise ValueError("project duration is zero")
    sample_rate = 44100
    total_samples = max(1, round(duration_ms / 1000 * sample_rate))
    beat_samples = max(1, round(60.0 / float(project.bpm) * sample_rate))
    click_len = min(max(1, round(0.045 * sample_rate)), beat_samples)
    silence_chunk = b"\x00\x00" * 8192

    def click_bytes(freq: float) -> bytes:
        t = np.arange(click_len, dtype=np.float64) / sample_rate
        env = np.exp(-t * 55.0)
        wave_data = np.sin(2 * np.pi * freq * t) * env * 0.82
        return np.asarray(np.clip(wave_data, -1, 1) * 32767, dtype=np.int16).tobytes()

    accent = click_bytes(1320.0)
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
            click = accent if beat_index % max(1, beats_per_bar) == 0 else regular
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
        if fmt == "wav":
            codec = {16: "pcm_s16le", 24: "pcm_s24le", 32: "pcm_f32le"}.get(int(wav_bit_depth), "pcm_s24le")
            cmd += ["-c:a", codec, str(out)]
        elif fmt == "flac":
            level = max(0, min(12, int(flac_compression)))
            cmd += ["-c:a", "flac", "-compression_level", str(level), str(out)]
        else:
            cmd += ["-c:a", "libmp3lame", "-b:a", bitrate, str(out)]
        _run(cmd)
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




def waveform_peaks(path: Path, points: int = 1024, progress=None) -> list[float]:
    """Return normalized mono peak amplitudes suitable for persistent timeline drawing."""
    points = max(64, min(2048, int(points)))
    if progress:
        progress(5, "Preparazione waveform")
    with tempfile.TemporaryDirectory() as td:
        wav_path = Path(td) / "waveform.wav"
        _run(
            [
                "ffmpeg", "-y", "-v", "error", "-i", str(path),
                "-ac", "1", "-ar", "4000", "-c:a", "pcm_s16le", str(wav_path),
            ]
        )
        if progress:
            progress(45, "Calcolo dei picchi")
        with wave.open(str(wav_path), "rb") as handle:
            data = np.frombuffer(handle.readframes(handle.getnframes()), dtype=np.int16).astype(np.float32)
    if not len(data):
        return [0.0] * points
    data = np.abs(data)
    peak = float(np.max(data)) or 1.0
    edges = np.linspace(0, len(data), points + 1, dtype=np.int64)
    out: list[float] = []
    for i in range(points):
        a, b = int(edges[i]), int(edges[i + 1])
        value = float(np.max(data[a:b])) if b > a else 0.0
        out.append(round(min(1.0, value / peak), 5))
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


def _estimate_meter(onset: np.ndarray, hz: float, beat_lag: int, preferred_signature: str = "4/4") -> str:
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
        # Bar periodicity plus a mild preference for the requested/default meter.
        score = float(corr[lag]) / base
        if sig == preferred_signature:
            score += 0.10
        if sig == "4/4":
            score += 0.06
        scores[sig] = score
    best = max(scores, key=scores.get)
    # Only leave 4/4/default if the alternative is meaningfully stronger.
    preferred = preferred_signature if preferred_signature in scores else "4/4"
    if best != preferred and scores[best] < scores[preferred] + 0.08:
        return preferred
    return best


def estimate_bpm_and_signature(path: Path, progress=None, preferred_signature: str = "4/4") -> tuple[float, str]:
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
    signature = _estimate_meter(onset, hz, lag, preferred_signature or "4/4")
    if progress:
        progress(90, f"BPM stimati: {bpm:.1f} · tempo {signature}")
    return round(float(bpm), 1), signature


def estimate_bpm(path: Path, progress=None, preferred_signature: str = "4/4") -> float:
    return estimate_bpm_and_signature(path, progress, preferred_signature)[0]

def _xcorr_fft(a, b):
    count = len(a) + len(b) - 1
    size = 1 << (count - 1).bit_length()
    return np.fft.irfft(np.fft.rfft(a, size) * np.fft.rfft(b[::-1], size), size)[:count]


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
