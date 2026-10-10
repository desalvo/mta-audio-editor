"""Experimental bounded asynchronous bridge to a persistent VST3 IPC worker.

The bridge never performs plugin I/O on the producer/consumer calling thread.
It is NOT a certified realtime callback integration: Python queue operations,
allocations and scheduling do not provide hard realtime guarantees.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
import queue
import threading
from typing import Callable, Sequence

from .native_chain import NativeChainError
from .stream_worker import NativeVST3Worker, MAX_BLOCK_FRAMES


@dataclass(frozen=True)
class PCMResult:
    sequence: int
    samples: tuple[float, ...]
    error: str | None = None


class AsyncVST3Bridge:
    """Bounded producer/consumer bridge; a single daemon thread owns the VST3 worker.

    Use only from ordinary application threads. Failure terminates processing;
    callers should recreate the bridge explicitly, never retry stale audio.
    """

    def __init__(self, worker_factory: Callable[[], NativeVST3Worker], *,
                 channels: int = 2, capacity: int = 8):
        if not callable(worker_factory):
            raise ValueError('Worker factory must be callable')
        if type(channels) is not int or channels not in (1, 2):
            raise ValueError('Channels must be mono or stereo')
        if type(capacity) is not int or not 1 <= capacity <= 256:
            raise ValueError('Invalid bridge capacity')
        self.channels = channels
        self._input: queue.Queue = queue.Queue(maxsize=capacity)
        self._output: queue.Queue = queue.Queue(maxsize=capacity)
        self._shutdown = threading.Event()
        self._done = threading.Event()
        self._fault: str | None = None
        self._sequence = 0
        self._worker_factory = worker_factory
        self._thread = threading.Thread(target=self._run, daemon=True, name='mta-vst3-ipc')
        self._thread.start()

    @property
    def fault(self) -> str | None:
        return self._fault

    @property
    def stopped(self) -> bool:
        return self._done.is_set()

    def submit(self, samples: Sequence[float]) -> int | None:
        """Nonwaiting enqueue; None means backpressure or closed/faulted bridge."""
        if self._shutdown.is_set() or self._done.is_set() or self._fault is not None:
            return None
        if not isinstance(samples, (tuple, list)) or not samples or len(samples) % self.channels:
            raise ValueError('Invalid PCM block')
        if len(samples) // self.channels > MAX_BLOCK_FRAMES:
            raise ValueError('PCM block exceeds 512 frames')
        if any(type(v) not in (int, float) or not math.isfinite(v) or abs(v) > 16 for v in samples):
            raise ValueError('Invalid PCM samples')
        frozen = tuple(float(v) for v in samples)
        try:
            self._input.put_nowait((self._sequence, frozen))
        except queue.Full:
            return None
        result = self._sequence
        self._sequence += 1
        return result

    def poll(self) -> PCMResult | None:
        """Fetch one finished block without awaiting IPC. None means no result yet."""
        try:
            return self._output.get_nowait()
        except queue.Empty:
            return None

    def _run(self) -> None:
        try:
            with self._worker_factory() as worker:
                while not self._shutdown.is_set():
                    try:
                        sequence, samples = self._input.get(timeout=0.05)
                    except queue.Empty:
                        continue
                    try:
                        output = tuple(worker.process(samples))
                        if len(output) != len(samples) or any(not math.isfinite(x) for x in output):
                            raise NativeChainError('Invalid VST3 asynchronous block output')
                        result = PCMResult(sequence, output)
                    except Exception as exc:
                        self._fault = f'{type(exc).__name__}: {exc}'
                        result = PCMResult(sequence, (), self._fault)
                        self._shutdown.set()
                    # Bounded queue: never block the IPC thread if consumer is late.
                    try:
                        self._output.put_nowait(result)
                    except queue.Full:
                        self._fault = 'VST3 result queue overflow'
                        self._shutdown.set()
        except Exception as exc:
            self._fault = f'{type(exc).__name__}: {exc}'
        finally:
            self._done.set()

    def close(self, timeout: float = 2.0) -> bool:
        if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or not math.isfinite(timeout) or timeout < 0:
            raise ValueError('Invalid shutdown timeout')
        self._shutdown.set()
        self._thread.join(timeout=timeout)
        return not self._thread.is_alive()

    def __enter__(self) -> AsyncVST3Bridge:
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()
