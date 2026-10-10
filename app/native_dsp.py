"""Optional C++ audio metering backend; graceful Python fallback for web/mobile.

The ABI is deliberately minimal and does not load third-party plug-ins or mutate audio.
"""
from __future__ import annotations
import ctypes
import math
import os
from pathlib import Path
from typing import Iterable


def _candidate_paths() -> list[Path]:
    configured = os.getenv('MTA_AUDIO_CORE_PATH', '').strip()
    suffix = '.dll' if os.name == 'nt' else ('.dylib' if __import__('sys').platform == 'darwin' else '.so')
    root = Path(__file__).resolve().parents[1]
    import sys
    frozen = Path(getattr(sys, '_MEIPASS', root))
    return ([Path(configured)] if configured else []) + [frozen / 'bin' / f'libmta_audio_core{suffix}', root / 'native' / 'audio_core' / f'libmta_audio_core{suffix}']


def _load():
    for path in _candidate_paths():
        if not path.is_file():
            continue
        try:
            lib = ctypes.CDLL(str(path))
            lib.mta_audio_core_abi.restype = ctypes.c_uint
            if lib.mta_audio_core_abi() != 1:
                continue
            lib.mta_pcm_meter.argtypes = [ctypes.POINTER(ctypes.c_float), ctypes.c_size_t,
                                            ctypes.c_uint, ctypes.POINTER(ctypes.c_float), ctypes.POINTER(ctypes.c_float)]
            lib.mta_pcm_meter.restype = ctypes.c_int
            return lib
        except (OSError, AttributeError):
            continue
    return None


_CORE = _load()


def available() -> bool:
    return _CORE is not None


def pcm_meter(samples: Iterable[float], channels: int = 1) -> tuple[float, float]:
    values = tuple(float(x) for x in samples)
    if not 1 <= channels <= 64 or not values or len(values) % channels:
        raise ValueError('PCM length/channels invalid')
    if any(not math.isfinite(x) for x in values):
        raise ValueError('PCM samples must be finite')
    if _CORE is not None:
        data = (ctypes.c_float * len(values))(*values)
        peak, rms = ctypes.c_float(), ctypes.c_float()
        if _CORE.mta_pcm_meter(data, len(values) // channels, channels,
                               ctypes.byref(peak), ctypes.byref(rms)) == 0:
            return float(peak.value), float(rms.value)
    return max(abs(x) for x in values), math.sqrt(sum(x*x for x in values)/len(values))


def pcm_gain(samples: Iterable[float], gain: float, channels: int = 1) -> list[float]:
    """Optional compiled PCM gain, with equivalent portable fallback.

    Processing is strictly opt-in: existing audio paths are unchanged.
    """
    values = [float(x) for x in samples]
    gain = float(gain)
    if not 1 <= channels <= 64 or not values or len(values) % channels:
        raise ValueError('PCM length/channels invalid')
    if not math.isfinite(gain) or not 0 <= gain <= 128:
        raise ValueError('PCM gain invalid')
    if any(not math.isfinite(x) or not math.isfinite(x * gain) for x in values):
        raise ValueError('PCM samples must be finite')
    if _CORE is not None and hasattr(_CORE, 'mta_pcm_gain'):
        fn = _CORE.mta_pcm_gain
        fn.argtypes = [ctypes.POINTER(ctypes.c_float), ctypes.c_size_t, ctypes.c_uint, ctypes.c_float]
        fn.restype = ctypes.c_int
        data = (ctypes.c_float * len(values))(*values)
        if fn(data, len(values)//channels, channels, gain) == 0:
            return list(data)
    return [x * gain for x in values]


def pcm_accumulate(destination: Iterable[float], source: Iterable[float],
                   gain: float = 1.0, channels: int = 1) -> list[float]:
    """Mix equal-length interleaved PCM vectors (optional compiled backend).

    Exposed for opt-in audio engine experiments; existing mixing is unchanged.
    """
    target = [float(v) for v in destination]
    values = [float(v) for v in source]
    gain = float(gain)
    if not 1 <= channels <= 64 or not target or len(target) != len(values) or len(target) % channels:
        raise ValueError('PCM buffer layout invalid')
    if not math.isfinite(gain) or abs(gain) > 128:
        raise ValueError('PCM mix gain invalid')
    if any(not math.isfinite(a) or not math.isfinite(b) or not math.isfinite(a + b * gain)
           for a, b in zip(target, values)):
        raise ValueError('PCM mix samples must be finite')
    if _CORE is not None and hasattr(_CORE, 'mta_pcm_accumulate'):
        fn = _CORE.mta_pcm_accumulate
        fn.argtypes = [ctypes.POINTER(ctypes.c_float), ctypes.POINTER(ctypes.c_float),
                       ctypes.c_size_t, ctypes.c_uint, ctypes.c_float]
        fn.restype = ctypes.c_int
        out = (ctypes.c_float * len(target))(*target)
        inp = (ctypes.c_float * len(values))(*values)
        if fn(out, inp, len(target) // channels, channels, gain) == 0:
            return list(out)
    return [a + b * gain for a, b in zip(target, values)]
