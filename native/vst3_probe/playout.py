"""Bounded playout policy for a VST3 IPC bridge (non-realtime prototype).

The caller advances one tick per audio block. A configurable lookahead lets
asynchronous output arrive before the deadline; on miss, original dry audio
is returned at exactly the original sequence position. This uses Python
collections and is NEVER called from a native audio callback.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Sequence
import math

from .async_bridge import AsyncVST3Bridge


@dataclass(frozen=True)
class PlayoutBlock:
    sequence: int
    samples: tuple[float, ...]
    status: str


@dataclass(frozen=True)
class PlayoutStats:
    submitted: int
    processed: int
    bypassed: int
    rejected: int
    discarded_late: int
    faulted: bool


class PlayoutCoordinator:
    """Tick-driven scheduling with bounded lookahead and deterministic dry fallback.

    This component does not provide hard realtime guarantees and does not
    automatically reconnect/replay requests after worker failure.
    """

    def __init__(self, bridge: AsyncVST3Bridge, *, channels: int = 2,
                 lookahead_blocks: int = 3, max_pending: int = 32):
        if type(channels) is not int or channels not in (1, 2):
            raise ValueError('invalid channel count')
        if type(lookahead_blocks) is not int or not 1 <= lookahead_blocks <= 32:
            raise ValueError('invalid lookahead')
        if type(max_pending) is not int or not lookahead_blocks <= max_pending <= 256:
            raise ValueError('invalid capacity')
        self.bridge = bridge
        self.channels = channels
        self.lookahead_blocks = lookahead_blocks
        self.max_pending = max_pending
        self._tick = 0
        self._pending: dict[int, tuple[int, tuple[float, ...]]] = {}
        self._ready: dict[int, tuple[float, ...]] = {}
        self._submitted = self._processed = self._bypassed = 0
        self._rejected = self._discarded = 0
        self._fault = False

    def submit(self, samples: Sequence[float]) -> int | None:
        if not isinstance(samples, (tuple, list)) or not samples or len(samples) % self.channels:
            raise ValueError('invalid PCM frame')
        if len(samples) // self.channels > 512 or any(
                type(x) not in (int, float) or not math.isfinite(x) or abs(x) > 16
                for x in samples):
            raise ValueError('invalid PCM samples')
        if self._fault or self.bridge.fault or len(self._pending) >= self.max_pending:
            self._rejected += 1
            return None
        sequence = self.bridge.submit(samples)
        if sequence is None:
            self._rejected += 1
            return None
        self._pending[sequence] = (self._tick + self.lookahead_blocks, tuple(float(x) for x in samples))
        self._submitted += 1
        return sequence

    def advance(self) -> list[PlayoutBlock]:
        """Advance one block period and emit all blocks whose deadline has passed."""
        self._tick += 1
        while True:
            result = self.bridge.poll()
            if result is None:
                break
            if result.sequence not in self._pending:
                self._discarded += 1
                continue
            if result.error or len(result.samples) != len(self._pending[result.sequence][1]) or any(
                    not math.isfinite(x) for x in result.samples):
                self._fault = True
                continue
            self._ready[result.sequence] = tuple(result.samples)
        if self.bridge.fault:
            self._fault = True
        due = sorted(seq for seq, (deadline, _) in self._pending.items() if deadline <= self._tick)
        emitted = []
        for seq in due:
            _, dry = self._pending.pop(seq)
            wet = self._ready.pop(seq, None)
            if wet is not None and not self._fault:
                self._processed += 1
                emitted.append(PlayoutBlock(seq, wet, 'processed'))
            else:
                self._bypassed += 1
                emitted.append(PlayoutBlock(seq, dry, 'bypass'))
        return emitted

    def flush_dry(self) -> list[PlayoutBlock]:
        """Force dry fallback for all pending frames at seek/stop/project close."""
        emitted = [PlayoutBlock(seq, dry, 'bypass') for seq, (_, dry) in sorted(self._pending.items())]
        self._bypassed += len(emitted)
        self._pending.clear()
        self._ready.clear()
        return emitted

    @property
    def stats(self) -> PlayoutStats:
        return PlayoutStats(self._submitted, self._processed, self._bypassed,
                            self._rejected, self._discarded, self._fault or bool(self.bridge.fault))

    def close(self) -> bool:
        self.flush_dry()
        return self.bridge.close()
