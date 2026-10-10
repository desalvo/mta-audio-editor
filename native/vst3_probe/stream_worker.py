"""Experimental interactive IPC VST3 worker (offline thread only).

MTAPCM2 framing: uint32le frame count followed by float32 interleaved samples.
In --stream-events mode only, 0xffffffff/0xfffffffe read/write processor state
and 0xfffffffd/0xfffffffc read/write controller state; payload is limited to 1 MiB.
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
from dataclasses import dataclass

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
    if any(not math.isfinite(value) or abs(value) > 16 for value in pcm):
        raise NativeChainError('Streaming worker returned invalid or out-of-range PCM')
    return list(pcm)



@dataclass(frozen=True)
class MidiEvent:
    kind: str  # "on" or "off"
    channel: int
    pitch: int
    offset: int
    velocity: float
    note_id: int = 0


@dataclass(frozen=True)
class ParameterPoint:
    parameter_id: int
    offset: int
    value: float


def _encode_events(midi: Sequence[MidiEvent], params: Sequence[ParameterPoint], frames: int) -> bytes:
    if len(midi) > 32 or len(params) > 32:
        raise ValueError('Maximum 32 MIDI events and 32 parameter points per block')
    payload = bytearray(struct.pack('<II', len(midi), len(params)))
    for event in midi:
        if not isinstance(event, MidiEvent) or event.kind not in ('on', 'off') or any(
            type(n) is not int for n in (event.channel, event.pitch, event.offset, event.note_id)
        ) or not (0 <= event.channel <= 15 and 0 <= event.pitch <= 127 and
                  0 <= event.offset < frames and 0 <= event.note_id <= 65535) or (
            isinstance(event.velocity, bool) or not isinstance(event.velocity, (int, float)) or
            not math.isfinite(event.velocity) or not 0 <= event.velocity <= 1
        ):
            raise ValueError('Invalid MIDI event')
        payload += struct.pack('<BBBBHHf', 1 if event.kind == 'on' else 2,
                               event.channel, event.pitch, 0, event.offset,
                               event.note_id, event.velocity)
    for point in params:
        if not isinstance(point, ParameterPoint) or any(
            type(n) is not int for n in (point.parameter_id, point.offset)
        ) or not (0 <= point.parameter_id <= 0xffffffff and 0 <= point.offset < frames) or (
            isinstance(point.value, bool) or not isinstance(point.value, (int, float)) or
            not math.isfinite(point.value) or not 0 <= point.value <= 1
        ):
            raise ValueError('Invalid parameter point')
        payload += struct.pack('<IHHf', point.parameter_id, point.offset, 0, point.value)
    return bytes(payload)


@dataclass(frozen=True)
class EventBlock:
    """One PCM quantum and its sample-aligned VST3 events (offline only)."""

    pcm: Sequence[float]
    midi: Sequence[MidiEvent] = ()
    parameters: Sequence[ParameterPoint] = ()


def prepare_event_batch(blocks: Sequence[EventBlock], channels: int) -> tuple[bytes, ...]:
    """Validate the ENTIRE bounded batch before performing any VST3 IPC.

    This guarantees invalid later blocks cannot cause a partially processed
    batch. Runtime/plug-in failures can still leave earlier blocks processed.
    Never use this helper on the realtime callback thread.
    """
    if not isinstance(blocks, (tuple, list)) or not 1 <= len(blocks) <= 128:
        raise ValueError('Event batch must contain 1..128 blocks')
    if type(channels) is not int or channels not in (1, 2):
        raise ValueError('Event batch requires mono or stereo')
    result = []
    total_frames = 0
    for block in blocks:
        if not isinstance(block, EventBlock):
            raise ValueError('Expected EventBlock')
        pcm = _encode_block(block.pcm, channels)
        frames = len(block.pcm) // channels
        total_frames += frames
        if total_frames > 65536:
            raise ValueError('Event batch exceeds 65536 frames')
        events = _encode_events(block.midi, block.parameters, frames)
        result.append(pcm[:4] + events + pcm[4:])
    return tuple(result)


class NativeVST3Worker:
    """One persistent subprocess per plugin, with timeout-controlled IPC thread."""

    def __init__(self, plugin: tuple[str, str], executable: str,
                 *, channels: int = 2, sample_rate: int = 48000, timeout: float = 10.0, events_enabled: bool = False):
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
        self.events_enabled = bool(events_enabled)
        self._lock = threading.Lock()
        self._closed = False
        self._proc = subprocess.Popen([str(probe), str(binary), '--stream-events' if self.events_enabled else '--stream-pcm', cid.lower(),
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

    def snapshot_controller_state(self) -> bytes:
        """Capture optional VST3 edit-controller state (not component state)."""
        if not self.events_enabled:
            raise ValueError('VST3 controller snapshots require events_enabled=True')
        with self._lock:
            if self._closed or self._proc.poll() is not None:
                raise NativeChainError('VST3 IPC worker is closed')
            try:
                header = self._exchange(struct.pack('<I', 0xfffffffd), 4)
                size, = struct.unpack('<I', header)
                if size == 0xffffffff:
                    raise NotImplementedError('VST3 controller does not provide getState')
                if size > 1024 * 1024:
                    raise NativeChainError('VST3 controller state exceeds limit')
                return self._exchange(b'', size) if size else b''
            except (NativeChainError, OSError, BrokenPipeError):
                self.close(force=True)
                raise

    def restore_controller_state(self, state: bytes) -> None:
        """Restore edit-controller state at a non-realtime session boundary."""
        if not self.events_enabled:
            raise ValueError('VST3 controller restore requires events_enabled=True')
        if not isinstance(state, bytes) or len(state) > 1024 * 1024:
            raise ValueError('Invalid VST3 controller state blob')
        with self._lock:
            if self._closed or self._proc.poll() is not None:
                raise NativeChainError('VST3 IPC worker is closed')
            try:
                header = struct.pack('<II', 0xfffffffc, len(state)) + state
                ack = self._exchange(header, 4)
                if struct.unpack('<I', ack)[0] != 0:
                    raise NotImplementedError('VST3 controller does not support setState')
            except (NativeChainError, OSError, BrokenPipeError):
                self.close(force=True)
                raise

    def snapshot_state(self) -> bytes:
        """Obtain up to 1 MiB of VST3 processor state on the worker thread.

        State snapshots are for the SAME plug-in version/class; they must never
        be deserialized from untrusted files without independent validation.
        """
        if not self.events_enabled:
            raise ValueError('VST3 snapshots require events_enabled=True')
        with self._lock:
            if self._closed or self._proc.poll() is not None:
                raise NativeChainError('VST3 IPC worker is closed')
            try:
                # This command has a variable-length reply; the header is read
                # first under the same bounded IPC watchdog.
                header = self._exchange(struct.pack('<I', 0xffffffff), 4)
                size, = struct.unpack('<I', header)
                if size == 0xffffffff or size > 1024 * 1024:
                    raise NativeChainError('VST3 state snapshot rejected')
                if not size:
                    return b''
                # Read remaining state bytes without sending another frame.
                return self._exchange(b'', size)
            except (NativeChainError, OSError, BrokenPipeError):
                self.close(force=True)
                raise

    def restore_state(self, state: bytes) -> None:
        """Restore processor state at a safe session boundary (not realtime)."""
        if not self.events_enabled:
            raise ValueError('VST3 state restore requires events_enabled=True')
        if not isinstance(state, bytes) or len(state) > 1024 * 1024:
            raise ValueError('Invalid VST3 state blob')
        with self._lock:
            if self._closed or self._proc.poll() is not None:
                raise NativeChainError('VST3 IPC worker is closed')
            try:
                ack = self._exchange(struct.pack('<II', 0xfffffffe, len(state)) + state, 4)
                code, = struct.unpack('<I', ack)
                if code != 0:
                    raise NativeChainError('VST3 state restore rejected')
            except (NativeChainError, OSError, BrokenPipeError):
                self.close(force=True)
                raise

    def process_event_batch(self, blocks: Sequence[EventBlock]) -> list[list[float]]:
        """Validate all blocks first, then send in order over one persistent IPC.

        The worker stays stateful across blocks. Call only on a control/worker
        thread; this method intentionally does not claim atomic DSP rollback.
        """
        if not self.events_enabled:
            raise ValueError('Event batches require events_enabled=True')
        payloads = prepare_event_batch(blocks, self.channels)
        with self._lock:
            if self._closed or self._proc.poll() is not None:
                raise NativeChainError('VST3 IPC worker is closed')
            outputs = []
            for payload in payloads:
                frames, = struct.unpack_from('<I', payload)
                try:
                    response = self._exchange(payload, 4 + frames * self.channels * 4)
                    outputs.append(_decode_block(response, frames, self.channels))
                except NativeChainError:
                    self.close(force=True)
                    raise
            return outputs

    def process(self, samples: Sequence[float]) -> list[float]:
        return self.process_with_events(samples)

    def process_with_events(self, samples: Sequence[float],
                            midi: Sequence[MidiEvent] = (),
                            parameters: Sequence[ParameterPoint] = ()) -> list[float]:
        pcm = _encode_block(samples, self.channels)
        frames = len(samples) // self.channels
        if not self.events_enabled and (midi or parameters):
            raise ValueError('Event transport requires events_enabled=True')
        payload = (pcm[:4] + _encode_events(midi, parameters, frames) + pcm[4:]
                   if self.events_enabled else pcm)
        with self._lock:
            if self._closed or self._proc.poll() is not None:
                raise NativeChainError('VST3 IPC worker is closed')
            try:
                result = self._exchange(payload, len(pcm))
                return _decode_block(result, frames, self.channels)
            except (NativeChainError, OSError, BrokenPipeError):
                # A failed exchange can leave the subprocess mid-frame; it must
                # never be used for the next audio quantum or session restore.
                self.close(force=True)
                raise

    def close(self, *, force: bool = False) -> None:
        # An in-flight timeout may call close(force=True) while another thread
        # is performing the blocked read. Never wait for _lock here: killing
        # the child is what releases the reader and avoids self-deadlock.
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
