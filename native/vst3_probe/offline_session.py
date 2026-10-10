"""Bounded multi-request VST3 session: one activation and continuous transport.

Binary file protocol MTASPCM1, little-endian. This is offline, not streaming IPC,
and MUST NEVER run from an audio callback. It does not preserve a plug-in across
independent subprocess invocations; a single invocation handles up to 128 jobs.
"""
from __future__ import annotations

from array import array
import math
from pathlib import Path
import struct
import subprocess
import sys
from tempfile import TemporaryDirectory
from typing import Sequence

from .native_chain import MAX_FRAMES, NativeChainError
from .probe import resolve_module_binary
from app.vst3_host import validate_plugin_path

MAGIC = b'MTASPCM1'
MAX_REQUESTS = 128
RATES = (44100, 48000, 96000)


def _pack_requests(requests: Sequence[Sequence[float]], channels: int, sample_rate: int) -> bytes:
    if type(channels) is not int or channels not in (1, 2):
        raise ValueError('Channels must be 1 or 2')
    if type(sample_rate) is not int or sample_rate not in RATES:
        raise ValueError('Unsupported session sample rate')
    if isinstance(requests, (bytes, bytearray, str)) or not 1 <= len(requests) <= MAX_REQUESTS:
        raise ValueError('Expected 1..128 requests')
    data = bytearray(MAGIC + struct.pack('<III', channels, sample_rate, len(requests)))
    frames_total = 0
    for request in requests:
        if isinstance(request, (bytes, bytearray, str)) or not hasattr(request, '__len__'):
            raise ValueError('PCM request must be a finite sized sequence')
        if len(request) > (MAX_FRAMES - frames_total) * channels:
            raise ValueError('Session exceeds cumulative frame limit')
        samples = list(request)
        if not samples or len(samples) % channels:
            raise ValueError('Invalid interleaved request length')
        frames = len(samples) // channels
        frames_total += frames
        if frames_total > MAX_FRAMES:
            raise ValueError('Session exceeds cumulative frame limit')
        if any(isinstance(v, bool) or not isinstance(v, (int, float)) or
               not math.isfinite(v) or abs(v) > 16 for v in samples):
            raise ValueError('Invalid PCM samples')
        data += struct.pack('<I', frames)
        pcm = array('f', samples)
        if sys.byteorder != 'little':
            pcm.byteswap()
        data += pcm.tobytes()
    return bytes(data)


def _unpack_requests(payload: bytes, expected_frames: Sequence[int], channels: int, sample_rate: int) -> list[list[float]]:
    if len(payload) < 20 or payload[:8] != MAGIC:
        raise NativeChainError('Invalid VST3 session response header')
    returned_channels, returned_rate, count = struct.unpack_from('<III', payload, 8)
    if (returned_channels, returned_rate, count) != (channels, sample_rate, len(expected_frames)):
        raise NativeChainError('VST3 session response metadata mismatch')
    offset = 20
    result = []
    for frames in expected_frames:
        if len(payload) - offset < 4:
            raise NativeChainError('Truncated VST3 session frame header')
        returned_frames, = struct.unpack_from('<I', payload, offset)
        offset += 4
        size = frames * channels * 4
        if returned_frames != frames or len(payload) - offset < size:
            raise NativeChainError('Truncated or mismatched VST3 session PCM')
        pcm = array('f')
        pcm.frombytes(payload[offset:offset + size])
        if sys.byteorder != 'little':
            pcm.byteswap()
        if any(not math.isfinite(value) for value in pcm):
            raise NativeChainError('VST3 session returned NaN/Inf')
        result.append(list(pcm))
        offset += size
    if offset != len(payload):
        raise NativeChainError('Unexpected trailing VST3 session payload')
    return result


def render_native_session(requests: Sequence[Sequence[float]], plugin: tuple[str, str],
                          executable: str, *, channels: int = 1,
                          sample_rate: int = 48000, timeout: float = 30.0) -> list[list[float]]:
    """Process multiple PCM requests while retaining a single native VST3 instance.

    Requests must be flat interleaved float samples. The plug-in sees a continuous
    audio stream across request boundaries; no reset occurs between requests.
    """
    if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or not math.isfinite(timeout) or timeout <= 0:
        raise ValueError('Timeout must be positive and finite')
    payload = _pack_requests(requests, channels, sample_rate)
    if not isinstance(plugin, (tuple, list)) or len(plugin) != 2:
        raise ValueError('Expected plugin path and CID')
    plugin_path, cid = plugin
    if not isinstance(cid, str) or len(cid) != 32 or any(c not in '0123456789abcdefABCDEF' for c in cid):
        raise ValueError('Invalid VST3 CID')
    probe = Path(executable).resolve()
    if not probe.is_file():
        raise FileNotFoundError('VST3 probe executable not found')
    binary = resolve_module_binary(validate_plugin_path(plugin_path))
    expected = [len(request) // channels for request in requests]
    with TemporaryDirectory(prefix='mta-vst3-session-') as directory:
        source = Path(directory) / 'session.in'
        destination = Path(directory) / 'session.out'
        source.write_bytes(payload)
        try:
            proc = subprocess.run([str(probe), str(binary), '--render-session', cid.lower(),
                                   str(source), str(destination)], capture_output=True, text=True,
                                  timeout=min(timeout, 600))
        except subprocess.TimeoutExpired as exc:
            raise NativeChainError('VST3 session timed out') from exc
        if proc.returncode:
            raise NativeChainError(f'VST3 session failed: {proc.stderr[:250]}')
        maximum = len(payload)
        if not destination.is_file() or destination.stat().st_size > maximum:
            raise NativeChainError('VST3 session output missing or oversized')
        return _unpack_requests(destination.read_bytes(), expected, channels, sample_rate)


def render_native_session_chain(requests: Sequence[Sequence[float]],
                                plugins: Sequence[tuple[str, str]], executable: str,
                                *, channels: int = 1, sample_rate: int = 48000,
                                timeout: float = 30.0) -> list[list[float]]:
    """Offline serial inserts: state persists across jobs, not across insert processes.

    Each plugin is isolated in its own bounded subprocess. No realtime guarantees.
    """
    if not 1 <= len(plugins) <= 8:
        raise ValueError('Expected 1..8 session inserts')
    _pack_requests(requests, channels, sample_rate)
    current = [list(request) for request in requests]
    for plugin in plugins:
        current = render_native_session(current, plugin, executable, channels=channels,
                                        sample_rate=sample_rate, timeout=timeout)
    return current


def render_native_session_wav(source: str | Path, destination: str | Path,
                              plugins: Sequence[tuple[str, str]], executable: str,
                              *, block_frames: int = 16384, timeout: float = 30.0) -> Path:
    """Offline WAV rendering via state-continuous multi-request insert sessions.

    Unlike the regular WAV renderer, each insert receives several logically separate
    PCM requests without resetting plugin state between them. No realtime guarantees.
    Each independent render is bounded by MAX_FRAMES and MAX_REQUESTS.
    """
    import os
    import tempfile
    import wave
    from .native_chain import NativeWavError, _decode_pcm_wav, _encode_pcm_wav

    if type(block_frames) is not int or block_frames < 1 or block_frames > MAX_FRAMES:
        raise ValueError('Invalid block size')
    if not 1 <= len(plugins) <= 8:
        raise ValueError('Expected 1..8 inserts')
    if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or not math.isfinite(timeout) or timeout <= 0:
        raise ValueError('Invalid session timeout')
    source_path = Path(source).resolve(strict=True)
    destination_path = Path(destination).resolve()
    if source_path == destination_path or (destination_path.exists() and os.path.samefile(source_path, destination_path)):
        raise ValueError('Source and destination must be distinct files')
    with wave.open(str(source_path), 'rb') as reader:
        channels, width, rate, frames = (reader.getnchannels(), reader.getsampwidth(),
                                          reader.getframerate(), reader.getnframes())
        if (reader.getcomptype() != 'NONE' or channels not in (1, 2) or
                width not in (2, 3, 4) or rate not in RATES or not 1 <= frames <= MAX_FRAMES):
            raise NativeWavError('Unsupported or oversized WAV source')
        count = (frames + block_frames - 1) // block_frames
        if count > MAX_REQUESTS:
            raise ValueError('Session has too many blocks; increase block_frames')
        requests = []
        for index in range(count):
            frame_count = min(block_frames, frames - index * block_frames)
            raw = reader.readframes(frame_count)
            if len(raw) != frame_count * channels * width:
                raise NativeWavError('Truncated WAV input')
            requests.append(_decode_pcm_wav(raw, width))
    outputs = render_native_session_chain(requests, plugins, executable,
                                          channels=channels, sample_rate=rate, timeout=timeout)
    if len(outputs) != count or any(len(output) != len(request) for output, request in zip(outputs, requests)):
        raise NativeWavError('VST3 session returned mismatched blocks')
    if not destination_path.parent.is_dir():
        raise FileNotFoundError('Output directory does not exist')
    fd, temporary = tempfile.mkstemp(prefix='.mta-vst3-session-', suffix='.wav', dir=str(destination_path.parent))
    os.close(fd)
    try:
        with wave.open(temporary, 'wb') as writer:
            writer.setnchannels(channels)
            writer.setsampwidth(width)
            writer.setframerate(rate)
            for output in outputs:
                writer.writeframesraw(_encode_pcm_wav(output, width))
        os.replace(temporary, destination_path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return destination_path
