"""Discard model padding events and bound notes to the actual source audio."""
import math


def bound_interval(start, end, duration):
    if not all(math.isfinite(value) for value in (start,end,duration)) or duration<=0:
        raise ValueError('Transcription produced a non-finite timeline')
    if end<=start:
        return None
    start=max(0.,start)
    end=min(duration,end)
    return (start,end) if end>start else None
