"""Offline latency and lookahead planning for VST3 IPC audio blocks.

Never use this Python planning object in a hard-realtime callback.
"""
from __future__ import annotations

from dataclasses import dataclass
import math


@dataclass(frozen=True)
class LatencyPlan:
    sample_rate: int
    block_frames: int
    plugin_latency_frames: int
    ipc_lookahead_blocks: int

    def __post_init__(self) -> None:
        if type(self.sample_rate) is not int or self.sample_rate not in (44100, 48000, 96000):
            raise ValueError('Invalid sample rate')
        if type(self.block_frames) is not int or not 1 <= self.block_frames <= 512:
            raise ValueError('Invalid processing block size')
        if type(self.plugin_latency_frames) is not int or not 0 <= self.plugin_latency_frames <= self.sample_rate * 10:
            raise ValueError('Invalid plugin latency')
        if type(self.ipc_lookahead_blocks) is not int or not 1 <= self.ipc_lookahead_blocks <= 256:
            raise ValueError('Invalid IPC lookahead')

    @property
    def ipc_latency_frames(self) -> int:
        return self.ipc_lookahead_blocks * self.block_frames

    @property
    def total_latency_frames(self) -> int:
        return self.plugin_latency_frames + self.ipc_latency_frames

    @property
    def total_latency_ms(self) -> float:
        return self.total_latency_frames * 1000.0 / self.sample_rate

    def compensation_frames(self, other: 'LatencyPlan') -> int:
        """Amount of extra dry delay for this path relative to another path.

        Positive result means this path should be delayed. The slower path is
        never advanced; time alignment uses a nonnegative delay only.
        """
        if self.sample_rate != other.sample_rate:
            raise ValueError('Incompatible sample rates')
        return max(0, other.total_latency_frames - self.total_latency_frames)


class PCMDelayLine:
    """Bounded offline reference delay, per interleaved PCM stream.

    This is a correctness reference for latency compensation, NOT a realtime
    callback implementation. The backing ring is allocated at construction.
    """

    def __init__(self, delay_frames: int, *, channels: int = 2):
        if type(channels) is not int or channels not in (1, 2):
            raise ValueError('Invalid channels')
        if type(delay_frames) is not int or not 0 <= delay_frames <= 960000:
            raise ValueError('Invalid delay')
        self.channels = channels
        self.delay_frames = delay_frames
        self._buf = [0.0] * (delay_frames * channels)
        self._pos = 0

    def process(self, interleaved: list[float] | tuple[float, ...]) -> tuple[float, ...]:
        if len(interleaved) % self.channels:
            raise ValueError('Invalid number of samples')
        if any(not isinstance(x, (int, float)) or isinstance(x, bool) or not math.isfinite(x) for x in interleaved):
            raise ValueError('Invalid PCM sample')
        if self.delay_frames == 0:
            return tuple(float(x) for x in interleaved)
        result = []
        for sample in interleaved:
            result.append(self._buf[self._pos])
            self._buf[self._pos] = float(sample)
            self._pos += 1
            if self._pos == len(self._buf):
                self._pos = 0
        return tuple(result)

    def reset(self) -> None:
        self._buf[:] = [0.0] * len(self._buf)
        self._pos = 0
