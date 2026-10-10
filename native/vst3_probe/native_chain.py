"""Opt-in bounded offline serial VST3 insert chain via isolated subprocesses.

Requires the Steinberg-SDK-enabled native probe. No realtime use, no project writes.
The r33 transport supports mono/stereo interleaved float32, 1..1048576 frames at 48 kHz.
"""
from __future__ import annotations

from array import array
import os
import struct
import wave
import math
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
from typing import Sequence

from .probe import resolve_module_binary
from app.vst3_host import validate_plugin_path

MAX_FRAMES = 1048576
MAX_INSERTS = 8


class NativeChainError(RuntimeError):
    """A plugin failure invalidates the entire render."""


def render_native_chain(audio: Sequence[float], plugins: Sequence[tuple[str, str]],
                        executable: str, *, timeout: float = 15.0) -> list[float]:
    """Run each VST3 module in a separate bounded process, passing PCM by file.

    Channels may be 1 (flat float samples) or 2 (sequence of stereo frames).
    This diagnostic API rejects MIDI and does not claim latency compensation.
    """
    if not 1 <= len(audio) <= MAX_FRAMES or not 1 <= len(plugins) <= MAX_INSERTS:
        raise ValueError('Expected 1..1048576 frames and 1..8 VST3 inserts')
    channels = 2 if isinstance(audio[0], (tuple, list)) else 1
    if channels == 2:
        if any(not isinstance(frame, (tuple, list)) or len(frame) != 2 for frame in audio):
            raise ValueError('Expected stereo frames of two float samples')
        pcm = [sample for frame in audio for sample in frame]
    else:
        pcm = audio
    if any(isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or abs(value) > 16 for value in pcm):
        raise ValueError('Invalid PCM samples')
    probe = Path(executable).resolve()
    if not probe.is_file():
        raise FileNotFoundError('Native VST3 probe executable is missing')
    current = array('f', pcm)
    if sys.byteorder != 'little':
        current.byteswap()
    with TemporaryDirectory(prefix='mta-vst3-offline-') as root:
        folder = Path(root)
        for index, (path, cid) in enumerate(plugins):
            if not isinstance(cid, str) or len(cid) != 32 or any(c not in '0123456789abcdefABCDEF' for c in cid):
                raise ValueError('Invalid VST3 class CID')
            binary = resolve_module_binary(validate_plugin_path(path))
            input_path = folder / f'in-{index}.f32le'
            output_path = folder / f'out-{index}.f32le'
            input_path.write_bytes(current.tobytes())
            try:
                proc = subprocess.run([str(probe), str(binary), '--render-pcm', cid.lower(),
                                       str(input_path), str(output_path), str(channels)],
                                      capture_output=True, text=True, timeout=max(0.5, min(timeout, 120)))
                if proc.returncode:
                    raise NativeChainError(f'VST3 insert {index} failed: {proc.stderr[:250]}')
                if not output_path.is_file() or output_path.stat().st_size != len(pcm) * 4:
                    raise NativeChainError(f'VST3 insert {index} returned invalid PCM size')
                next_buffer = array('f')
                next_buffer.frombytes(output_path.read_bytes())
                if sys.byteorder != 'little':
                    next_buffer.byteswap()
                if any(not math.isfinite(value) for value in next_buffer):
                    raise NativeChainError(f'VST3 insert {index} returned NaN/Inf')
                current = next_buffer
            except subprocess.TimeoutExpired as exc:
                raise NativeChainError(f'VST3 insert {index} timed out') from exc
    if channels == 2:
        return [(current[i], current[i + 1]) for i in range(0, len(current), 2)]
    return list(current)


class NativeWavError(NativeChainError):
    """Unsupported WAV input or failed isolated native WAV export."""


def render_native_wav(source: str | Path, destination: str | Path,
                      plugins: Sequence[tuple[str, str]], executable: str,
                      *, timeout: float = 15.0) -> Path:
    """Offline WAV->VST3->WAV via the isolated PCM chain.

    Intentional constraints: 48 kHz, mono/stereo, 16-bit PCM WAV, <=MAX_FRAMES.
    Files larger than the bounded input limit are rejected without partial output.
    Output is written to a temporary file in the destination directory and
    atomically published only after every insert succeeds.
    """
    source_path = Path(source).resolve(strict=True)
    destination_path = Path(destination).resolve()
    if source_path == destination_path:
        raise ValueError('Source and destination must differ')
    with wave.open(str(source_path), 'rb') as wav:
        channels = wav.getnchannels()
        frames = wav.getnframes()
        if wav.getcomptype() != 'NONE' or wav.getsampwidth() != 2 or wav.getframerate() != 48000 or channels not in (1, 2):
            raise NativeWavError('Only 48 kHz mono/stereo uncompressed 16-bit PCM WAV is supported')
        if not 1 <= frames <= MAX_FRAMES:
            raise NativeWavError('WAV length exceeds the bounded native VST3 limit')
        pcm = wav.readframes(frames)
        if len(pcm) != frames * channels * 2:
            raise NativeWavError('Truncated WAV input')
        decoded = struct.unpack('<' + 'h' * (frames * channels), pcm)
        values = [sample / 32768.0 for sample in decoded]
        audio = list(zip(values[::2], values[1::2])) if channels == 2 else values
    rendered = render_native_chain(audio, plugins, executable, timeout=timeout)
    flat = [sample for frame in rendered for sample in frame] if channels == 2 else rendered
    # Clamp to signed PCM16 after native processing; malformed output is already
    # rejected by render_native_chain, but avoid struct.pack overflow.
    output = struct.pack('<' + 'h' * len(flat), *(max(-32768, min(32767, round(sample * 32768))) for sample in flat))
    import tempfile
    fd, temp_name = tempfile.mkstemp(prefix='.mta-vst3-', suffix='.wav', dir=str(destination_path.parent))
    os.close(fd)
    try:
        with wave.open(temp_name, 'wb') as wav:
            wav.setnchannels(channels)
            wav.setsampwidth(2)
            wav.setframerate(48000)
            wav.writeframes(output)
        os.replace(temp_name, destination_path)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)
    return destination_path
