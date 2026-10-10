"""Experimental ordered block delivery for an asynchronous VST3 bridge.

Outside the realtime callback: Python locks, allocations and queue semantics are
not suitable for a hard-realtime audio thread. Do not enable native_host_ready.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Sequence

from .async_bridge import AsyncVST3Bridge


@dataclass(frozen=True)
class Delivery:
    sequence: int
    samples: tuple[float, ...]
    status: str


class OrderedBridgeAdapter:
    """Nonblocking audio-block coordinator for ordinary application threads.

    A scheduled block is output exactly once, in submission order. If processing
    misses its deadline, the original PCM is emitted (dry bypass), and any late
    processed output is discarded rather than shifted onto a later block.
    """

    def __init__(self, bridge: AsyncVST3Bridge, *, channels: int = 2,
                 max_pending: int = 32):
        if channels not in (1, 2) or type(channels) is not int:
            raise ValueError('channels must be mono or stereo')
        if type(max_pending) is not int or not 1 <= max_pending <= 256:
            raise ValueError('invalid max_pending')
        self.bridge = bridge
        self.channels = channels
        self.max_pending = max_pending
        self._scheduled: dict[int, tuple[float, ...]] = {}
        self._ready: dict[int, tuple[float, ...]] = {}
        self._next_output: int | None = None
        self._failure: str | None = None

    @property
    def fault(self) -> str | None:
        return self._failure or self.bridge.fault

    @property
    def outstanding(self) -> int:
        return len(self._scheduled)

    def submit(self, samples: Sequence[float]) -> int | None:
        if self.fault or len(self._scheduled) >= self.max_pending:
            return None
        if not samples or len(samples) % self.channels:
            raise ValueError('invalid audio block')
        if any(not isinstance(v, (int, float)) or isinstance(v, bool)
               or not math.isfinite(v) for v in samples):
            raise ValueError('invalid samples')
        block = tuple(float(v) for v in samples)
        sequence = self.bridge.submit(block)
        if sequence is None:
            return None
        if self._next_output is None:
            self._next_output = sequence
        self._scheduled[sequence] = block
        return sequence

    def collect(self) -> int:
        """Poll existing IPC results without waiting, discard stale responses."""
        count = 0
        while True:
            result = self.bridge.poll()
            if result is None:
                break
            count += 1
            if result.error:
                self._failure = result.error
            elif result.sequence in self._scheduled:
                original = self._scheduled[result.sequence]
                if len(result.samples) != len(original) or any(
                        not math.isfinite(v) for v in result.samples):
                    self._failure = 'Invalid processed PCM block'
                else:
                    self._ready[result.sequence] = tuple(result.samples)
        return count

    def deliver(self) -> Delivery | None:
        """Return next block immediately; bypass if output has not arrived."""
        self.collect()
        sequence = self._next_output
        if sequence is None or sequence not in self._scheduled:
            return None
        source = self._scheduled.pop(sequence)
        processed = self._ready.pop(sequence, None)
        status = 'processed' if processed is not None and not self.fault else 'bypass'
        self._next_output = min(self._scheduled) if self._scheduled else None
        return Delivery(sequence, processed if status == 'processed' else source, status)

    def close(self) -> bool:
        return self.bridge.close()
