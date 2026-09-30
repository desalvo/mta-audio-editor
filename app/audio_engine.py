from __future__ import annotations

import subprocess
import tempfile
import uuid
import wave
from pathlib import Path

import numpy as np

from .models import Clip, Project, Track
from .plugins import chain_filter


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
    for index, clip in enumerate(track.clips):
        start = clip.source_start_ms / 1000
        end = clip.source_end_ms / 1000
        delay = max(0, clip.timeline_start_ms)
        parts.append(
            f"[0:a]atrim=start={start:.6f}:end={end:.6f},asetpts=PTS-STARTPTS,"
            f"adelay={delay}|{delay},aformat=channel_layouts=stereo[c{index}]"
        )
        labels.append(f"[c{index}]")
    if len(labels) == 1:
        base = parts[0] + f";{labels[0]}anull[mix]"
    else:
        base = ";".join(parts) + ";" + "".join(labels) + f"amix=inputs={len(labels)}:duration=longest:normalize=0[mix]"
    inserts = chain_filter(track.inserts) if apply_inserts else ""
    filters = base + (f";[mix]{inserts}[out]" if inserts else ";[mix]anull[out]")
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


def render_mix(project: Project, audio_resolver, out: Path, fmt: str = "mp3", bitrate: str = "320k") -> Path:
    """Render stereo master for preview/WAV/MP3 export."""
    if not project.tracks:
        raise ValueError("project has no audio tracks")
    fmt = fmt.lower()
    if fmt not in {"wav", "mp3"}:
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
        filters.append(f"[master0]{tail}[master]")
        cmd += ["-filter_complex", ";".join(filters), "-map", "[master]", "-ar", "44100"]
        if fmt == "wav":
            cmd += ["-c:a", "pcm_s24le", str(out)]
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
