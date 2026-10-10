"""Opt-in fixed-length offline serial VST3 insert chain via isolated subprocesses.

Requires the Steinberg-SDK-enabled native probe. No realtime use, no project writes.
The r32 transport supports mono float32, exactly 65536 frames at 48 kHz.
"""
from __future__ import annotations

from array import array
import json
import math
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
from typing import Sequence

from .probe import resolve_module_binary
from app.vst3_host import validate_plugin_path

FRAMES = 128 * 512
MAX_INSERTS = 8


class NativeChainError(RuntimeError):
    """A plugin failure invalidates the entire render."""


def render_native_chain(audio: Sequence[float], plugins: Sequence[tuple[str, str]],
                        executable: str, *, timeout: float = 15.0) -> list[float]:
    """Run each VST3 module in a separate bounded process, passing PCM by file.

    This diagnostic API intentionally rejects MIDI and stereo rather than silently
    dropping or misrouting events/channels. No latency correction is claimed.
    """
    if len(audio) != FRAMES or not 1 <= len(plugins) <= MAX_INSERTS:
        raise ValueError('Expected exactly 65536 mono frames and 1..8 VST3 inserts')
    if any(not isinstance(value, (int, float)) or not math.isfinite(value) or abs(value) > 16 for value in audio):
        raise ValueError('Invalid PCM samples')
    probe = Path(executable).resolve()
    if not probe.is_file():
        raise FileNotFoundError('Native VST3 probe executable is missing')
    current = array('f', audio)
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
                                       str(input_path), str(output_path)],
                                      capture_output=True, text=True, timeout=max(0.5, min(timeout, 120)))
                if proc.returncode:
                    raise NativeChainError(f'VST3 insert {index} failed: {proc.stderr[:250]}')
                if not output_path.is_file() or output_path.stat().st_size != FRAMES * 4:
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
    return list(current)
