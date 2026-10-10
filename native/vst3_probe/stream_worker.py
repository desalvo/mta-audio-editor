"""Experimental interactive IPC VST3 worker (offline thread only).

MTAPCM2 framing: uint32le frame count followed by float32 interleaved samples.
One subprocess owns one plugin until closed. Sending frame count zero ends the stream.
The API is strictly forbidden inside a realtime audio callback.
"""
from __future__ import annotations

from array import array
from pathlib import Path
import math
import os
import queue
import struct
import subprocess
import sys
import tempfile
import threading
import wave
from typing import Sequence

from .native_chain import NativeChainError, NativeWavError, _decode_pcm_wav, _encode_pcm_wav
from .probe import resolve_module_binary
from app.vst3_host import validate_plugin_path

MAX_BLOCK_FRAMES = 512
RATES = (44100, 48000, 96000)


def _encode_block(samples: Sequence[float], channels: int) -> bytes:
    if type(channels) is not int or channels not in (1, 2):
        raise ValueError('Streaming channels must be 1 or 2')
    if not isinstance(samples, (list, tuple, array)) or not samples or len(samples) % channels:
        raise ValueError('Invalid interleaved streaming PCM')
    frames = len(samples) // channels
    if frames > MAX_BLOCK_FRAMES:
        raise ValueError('Streaming request exceeds 512 frames')
    if any(isinstance(v, bool) or not isinstance(v, (float, int)) or
           not math.isfinite(v) or abs(v) > 16 for v in samples):
        raise ValueError('Invalid float PCM sample')
    data = array('f', samples)
    if sys.byteorder != 'little':
        data.byteswap()
    return struct.pack('<I', frames) + data.tobytes()


def _decode_block(response: bytes, expected_frames: int, channels: int) -> list[float]:
    if len(response) != 4 + expected_frames * channels * 4:
        raise NativeChainError('Invalid streaming worker response length')
    actual, = struct.unpack_from('<I', response)
    if actual != expected_frames:
        raise NativeChainError('Streaming worker returned mismatched frame count')
    pcm = array('f')
    pcm.frombytes(response[4:])
    if sys.byteorder != 'little':
        pcm.byteswap()
    if any(not math.isfinite(value) for value in pcm):
        raise NativeChainError('Streaming worker returned NaN/Inf')
    return list(pcm)


class NativeVST3Worker:
    """One persistent subprocess per plugin, with timeout-controlled IPC thread."""

    def __init__(self, plugin: tuple[str, str], executable: str,
                 *, channels: int = 2, sample_rate: int = 48000, timeout: float = 10.0):
        if type(channels) is not int or channels not in (1, 2):
            raise ValueError('Channels must be 1 or 2')
        if type(sample_rate) is not int or sample_rate not in RATES:
            raise ValueError('Unsupported sample rate')
        if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or not math.isfinite(timeout) or timeout <= 0:
            raise ValueError('Timeout must be positive and finite')
        if not isinstance(plugin, (tuple, list)) or len(plugin) != 2:
            raise ValueError('Expected plugin path and class CID')
        plugin_path, cid = plugin
        if not isinstance(cid, str) or len(cid) != 32 or any(c not in '0123456789abcdefABCDEF' for c in cid):
            raise ValueError('Invalid VST3 CID')
        binary = resolve_module_binary(validate_plugin_path(plugin_path))
        probe = Path(executable).resolve(strict=True)
        if not probe.is_file():
            raise ValueError('Invalid VST3 probe')
        self.channels = channels
        self.sample_rate = sample_rate
        self.timeout = min(float(timeout), 600.0)
        self._lock = threading.Lock()
        self._closed = False
        self._proc = subprocess.Popen([str(probe), str(binary), '--stream-pcm', cid.lower(),
                                       str(channels), str(sample_rate)],
                                      stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                      stderr=subprocess.DEVNULL, bufsize=0)

    def _exchange(self, payload: bytes, reply_size: int) -> bytes:
        def read_exact(count: int) -> bytes:
            chunks = []
            while count:
                chunk = self._proc.stdout.read(count)
                if not chunk:
                    raise NativeChainError('VST3 worker exited before completing the response')
                chunks.append(chunk)
                count -= len(chunk)
            return b''.join(chunks)

        def perform(result: queue.Queue) -> None:
            try:
                self._proc.stdin.write(payload)
                self._proc.stdin.flush()
                result.put((read_exact(reply_size), None))
            except (BrokenPipeError, OSError, NativeChainError) as exc:
                result.put((None, exc))
        result: queue.Queue = queue.Queue(maxsize=1)
        worker = threading.Thread(target=perform, args=(result,), daemon=True)
        worker.start()
        try:
            output, error = result.get(timeout=self.timeout)
        except queue.Empty as exc:
            self.close(force=True)
            raise NativeChainError('VST3 IPC worker timed out') from exc
        if error is not None:
            self.close(force=True)
            raise NativeChainError('VST3 IPC worker terminated unexpectedly') from error
        return output

    def process(self, samples: Sequence[float]) -> list[float]:
        payload = _encode_block(samples, self.channels)
        frames = len(samples) // self.channels
        with self._lock:
            if self._closed or self._proc.poll() is not None:
                raise NativeChainError('VST3 IPC worker is closed')
            result = self._exchange(payload, len(payload))
            try:
                return _decode_block(result, frames, self.channels)
            except NativeChainError:
                self.close(force=True)
                raise

    def close(self, *, force: bool = False) -> None:
        if self._closed:
            return
        self._closed = True
        if self._proc.poll() is None:
            if not force:
                try:
                    self._proc.stdin.write(struct.pack('<I', 0))
                    self._proc.stdin.flush()
                    self._proc.wait(timeout=min(2.0, self.timeout))
                except (BrokenPipeError, OSError, subprocess.TimeoutExpired):
                    force = True
            if force and self._proc.poll() is None:
                self._proc.kill()
        try:
            self._proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            self._proc.kill()
            self._proc.wait(timeout=2)
        for pipe in (self._proc.stdin, self._proc.stdout):
            if pipe is not None:
                pipe.close()

    def __enter__(self) -> NativeVST3Worker:
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close(force=exc_type is not None)


def render_stream_wav(source: str | Path, destination: str | Path,
                      plugins: Sequence[tuple[str, str]], executable: str,
                      *, timeout: float = 10.0, max_total_frames: int = 100_000_000) -> Path:
    """Sequential bounded-buffer WAV export over persistent worker IPC.

    This is deliberately synchronous OFFLINE rendering, not DAW realtime hosting.
    All plugin instances remain alive throughout the file render; each is isolated
    in its own worker process. The source is read in 512-frame chunks.
    """
    if not isinstance(plugins, (tuple, list)) or not 1 <= len(plugins) <= 8:
        raise ValueError('Expected 1..8 VST3 plugins')
    if type(max_total_frames) is not int or not 1 <= max_total_frames <= 100_000_000:
        raise ValueError('Invalid render frame budget')
    source_path = Path(source).resolve(strict=True)
    target = Path(destination).resolve()
    if source_path == target or (target.exists() and os.path.samefile(source_path, target)):
        raise ValueError('Source and destination must not refer to the same file')
    with wave.open(str(source_path), 'rb') as reader:
        channels, width, rate, frames = (reader.getnchannels(), reader.getsampwidth(),
                                          reader.getframerate(), reader.getnframes())
        if reader.getcomptype() != 'NONE' or channels not in (1, 2) or width not in (2, 3, 4) or rate not in RATES:
            raise NativeWavError('Expected 44.1/48/96 kHz PCM16/24/32 mono/stereo WAV')
        if not 1 <= frames <= max_total_frames:
            raise NativeWavError('Streaming WAV frame count is outside bounded limit')
        import contextlib
        fd, temp_name = tempfile.mkstemp(prefix='.mta-vst3-stream-', suffix='.wav', dir=str(target.parent))
        os.close(fd)
        try:
            with contextlib.ExitStack() as stack:
                workers = [stack.enter_context(NativeVST3Worker(plugin, executable,
                             channels=channels, sample_rate=rate, timeout=timeout)) for plugin in plugins]
                with wave.open(temp_name, 'wb') as writer:
                    writer.setnchannels(channels)
                    writer.setsampwidth(width)
                    writer.setframerate(rate)
                    pending = frames
                    while pending:
                        block_frames = min(MAX_BLOCK_FRAMES, pending)
                        pcm = reader.readframes(block_frames)
                        if len(pcm) != block_frames * channels * width:
                            raise NativeWavError('Truncated streaming WAV input')
                        block = _decode_pcm_wav(pcm, width)
                        for worker in workers:
                            block = worker.process(block)
                        writer.writeframesraw(_encode_pcm_wav(block, width))
                        pending -= block_frames
            os.replace(temp_name, target)
        finally:
            if os.path.exists(temp_name):
                os.unlink(temp_name)
    return target
