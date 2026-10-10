"""Bounded, deterministic offline audio graph helpers for VST3 integration.

These helpers are NOT a realtime audio-thread implementation. Plugin callbacks
remain in an isolated process; this module performs host-side offline alignment.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Sequence

MAX_CHANNELS = 64
MAX_FRAMES = 10_000_000
MAX_LATENCY = 480_000  # 10 seconds at 48 kHz; an explicit host safety limit
MAX_TAIL = 2_880_000   # 60 seconds at 48 kHz


@dataclass(frozen=True)
class PluginTiming:
    latency_samples: int
    tail_samples: int

    def __post_init__(self) -> None:
        for key, limit in (("latency_samples", MAX_LATENCY), ("tail_samples", MAX_TAIL)):
            value = getattr(self, key)
            if type(value) is not int or not 0 <= value <= limit:
                raise ValueError(f"{key} must be an integer in 0..{limit}")


def _validate_audio(audio: Sequence[Sequence[float]]) -> int:
    if not 1 <= len(audio) <= MAX_CHANNELS:
        raise ValueError("Invalid channel count")
    frames = len(audio[0])
    if not 0 <= frames <= MAX_FRAMES or any(len(channel) != frames for channel in audio):
        raise ValueError("All channels must have the same bounded frame count")
    if any(not math.isfinite(sample) for channel in audio for sample in channel):
        raise ValueError("Audio contains a non-finite sample")
    return frames


def compensate_latency(audio: Sequence[Sequence[float]], latency_samples: int,
                       *, target_frames: int | None = None) -> list[list[float]]:
    """Remove plugin-reported initial delay, padding the end with silence.

    For a chain, call this only after a block stream including latency flush
    has been rendered. This is not correct for independent unflushed blocks.
    """
    frames = _validate_audio(audio)
    PluginTiming(latency_samples, 0)
    if target_frames is None:
        target_frames = max(0, frames - latency_samples)
    if type(target_frames) is not int or not 0 <= target_frames <= MAX_FRAMES:
        raise ValueError("Invalid target frame count")
    return [list(channel[latency_samples:latency_samples + target_frames]) +
            [0.0] * max(0, target_frames - max(0, len(channel) - latency_samples))
            for channel in audio]


def align_parallel_stems(stems: Sequence[Sequence[Sequence[float]]],
                         timings: Sequence[PluginTiming]) -> list[list[list[float]]]:
    """Align parallel processed stems on the common (largest) latency.

    No stem is advanced beyond its initial sample; each is padded up to the
    highest reported latency, preserving its actual plugin output unchanged.
    Use compensate_latency on the final mixed signal after rendering the flush.
    """
    if not stems or len(stems) != len(timings) or len(stems) > 128:
        raise ValueError("Stems and timings must have matching nonzero bounded lengths")
    frames = [_validate_audio(stem) for stem in stems]
    if len(set(frames)) != 1:
        raise ValueError("Parallel stems need the same frame count")
    common = max(timing.latency_samples for timing in timings)
    if frames[0] + common > MAX_FRAMES:
        raise ValueError("Aligned signal exceeds the frame limit")
    return [[[0.0] * (common - timing.latency_samples) + list(channel) +
             [0.0] * timing.latency_samples
             for channel in stem] for stem, timing in zip(stems, timings)]


def mix_aligned(stems: Sequence[Sequence[Sequence[float]]]) -> list[list[float]]:
    """Sum stems using stable floating point summation, never silently clip."""
    if not stems:
        raise ValueError("Missing stems")
    frames = [_validate_audio(stem) for stem in stems]
    if len(set(frames)) != 1 or len({len(stem) for stem in stems}) != 1:
        raise ValueError("Incompatible stems")
    return [[math.fsum(stem[ch][i] for stem in stems) for i in range(frames[0])]
            for ch in range(len(stems[0]))]


def pending_tail_frames(timings: Sequence[PluginTiming]) -> int:
    """Bounded sequential chain tail budget: sum of declared plugin tails."""
    if len(timings) > 128:
        raise ValueError("Excessive plugin chain")
    return min(MAX_TAIL, sum(t.tail_samples for t in timings))

@dataclass(frozen=True)
class ScheduledEvent:
    """A sample-timed MIDI note or normalized VST3 parameter change."""
    sample: int
    kind: str
    channel: int = 0
    key: int = 60
    velocity: float = 1.0
    parameter_id: int = 0
    value: float = 0.0

    def __post_init__(self) -> None:
        if type(self.sample) is not int or not 0 <= self.sample < MAX_FRAMES:
            raise ValueError("Invalid absolute event sample")
        if self.kind not in ('note_on', 'note_off', 'parameter'):
            raise ValueError("Unsupported event kind")
        if type(self.channel) is not int or not 0 <= self.channel <= 15:
            raise ValueError("Invalid MIDI channel")
        if type(self.key) is not int or not 0 <= self.key <= 127:
            raise ValueError("Invalid MIDI key")
        if not math.isfinite(self.velocity) or not 0 <= self.velocity <= 1:
            raise ValueError("Invalid velocity")
        if type(self.parameter_id) is not int or not 0 <= self.parameter_id < 2**32:
            raise ValueError("Invalid parameter ID")
        if not math.isfinite(self.value) or not 0 <= self.value <= 1:
            raise ValueError("Invalid normalized parameter value")


def events_for_blocks(events: Sequence[ScheduledEvent], *, block_size: int,
                      frames: int) -> list[list[tuple[int, ScheduledEvent]]]:
    """Prepare bounded sample-offset event batches before offline processing.

    An event at exactly the next block boundary belongs to the next block.
    Sorting is stable, so parameter ordering at the same sample is preserved.
    This preparation intentionally happens outside any audio callback.
    """
    if type(block_size) is not int or not 1 <= block_size <= 8192:
        raise ValueError("Invalid block size")
    if type(frames) is not int or not 0 <= frames <= MAX_FRAMES:
        raise ValueError("Invalid render length")
    if len(events) > 100_000:
        raise ValueError("Too many scheduled events")
    count = (frames + block_size - 1) // block_size
    batches: list[list[tuple[int, ScheduledEvent]]] = [[] for _ in range(count)]
    for event in sorted(events, key=lambda item: item.sample):
        if event.sample >= frames:
            raise ValueError("Event outside render range")
        block, offset = divmod(event.sample, block_size)
        batches[block].append((offset, event))
    return batches


# Offline insert-graph executor (not the application realtime callback).
from collections.abc import Callable

MAX_INSERTS = 32
MAX_BLOCKS = 65536


@dataclass(frozen=True)
class OfflineInsert:
    """An externally hosted plugin's declared timing and offline block callback.

    A production adapter must run untrusted callbacks in a supervised subprocess.
    This API intentionally does not load arbitrary shared libraries into Python.
    """
    name: str
    timing: PluginTiming
    process: Callable[[list[list[float]], list[tuple[int, ScheduledEvent]]], Sequence[Sequence[float]]]

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not 1 <= len(self.name) <= 128:
            raise ValueError("Invalid insert name")
        if not callable(self.process):
            raise ValueError("Insert processor must be callable")


@dataclass(frozen=True)
class OfflineRenderResult:
    audio: list[list[float]]
    latency_samples: int
    tail_samples: int
    blocks_processed: int
    events_dispatched: int


class OfflineRenderError(RuntimeError):
    """A failed insert invalidates the entire render; no partial audio escapes."""


def render_insert_chain(audio: Sequence[Sequence[float]], inserts: Sequence[OfflineInsert],
                        *, block_size: int = 512, events: Sequence[ScheduledEvent] = (),
                        include_tail: bool = False) -> OfflineRenderResult:
    """Process bounded offline audio, dispatching sample-offset events to the first insert.

    Each insert receives all blocks, including upstream flush. Declared latency
    is removed *only after* every insert has rendered its extra flush frames.
    Insert callbacks must produce exactly the input block's channel/frame shape.
    No plugin is allowed to return partial output on failure.
    """
    frames = _validate_audio(audio)
    if not 1 <= block_size <= 8192 or type(block_size) is not int:
        raise ValueError("Invalid block size")
    if not inserts or len(inserts) > MAX_INSERTS:
        raise ValueError("Insert chain must contain 1..32 processors")
    if any(not isinstance(insert, OfflineInsert) for insert in inserts):
        raise ValueError("Invalid insert")
    total_latency = sum(insert.timing.latency_samples for insert in inserts)
    total_tail = pending_tail_frames([insert.timing for insert in inserts]) if include_tail else 0
    flush = total_latency + total_tail
    if frames + flush > MAX_FRAMES or (frames + flush + block_size - 1) // block_size > MAX_BLOCKS:
        raise ValueError("Render exceeds resource limits")
    batches = events_for_blocks(events, block_size=block_size, frames=frames)
    processed = [list(channel) + [0.0] * flush for channel in audio]
    processed_blocks = 0
    dispatched = 0
    for index, insert in enumerate(inserts):
        result = [[] for _ in processed]
        for start in range(0, frames + flush, block_size):
            end = min(start + block_size, frames + flush)
            block = [channel[start:end] for channel in processed]
            batch = batches[start // block_size] if index == 0 and start < frames else []
            try:
                output = insert.process(block, batch)
                if isinstance(output, (str, bytes)) or len(output) != len(block):
                    raise ValueError("Unexpected channel count")
                if any(len(channel) != end - start for channel in output):
                    raise ValueError("Unexpected frame count")
                if any(not math.isfinite(sample) for channel in output for sample in channel):
                    raise ValueError("Non-finite plugin output")
                for target, channel in zip(result, output):
                    target.extend(channel)
            except Exception as exc:
                raise OfflineRenderError(f"Insert {index} ({insert.name}) failed at frame {start}") from exc
            processed_blocks += 1
            dispatched += len(batch)
        processed = result
    length = frames + total_tail if include_tail else frames
    output = compensate_latency(processed, total_latency, target_frames=length)
    return OfflineRenderResult(output, total_latency, total_tail, processed_blocks, dispatched)
