"""Experimental native-queue / VST3 IPC integration harness.

This is intentionally NOT called by the DAW realtime audio callback. The C ABI
is consumed on a test/control thread; Python only runs on the worker thread.
"""
from __future__ import annotations

import ctypes
from pathlib import Path
import math
from typing import Sequence

from .stream_worker import NativeVST3Worker


class NativeRTTestHarness:
    """Connect the C++ SPSC scheduler to a real isolated Steinberg VST3 worker."""

    def __init__(self, library: str, plugin: tuple[str, str], probe: str,
                 *, frames: int = 256, channels: int = 2, rate: int = 48000,
                 lookahead: int = 4):
        if type(frames) is not int or not 1 <= frames <= 512:
            raise ValueError("Native quantum outside 1..512 frames")
        if type(channels) is not int or channels not in (1, 2):
            raise ValueError("Expected mono or stereo")
        if type(rate) is not int or rate not in (44100, 48000, 96000):
            raise ValueError("Unsupported sample rate")
        if type(lookahead) is not int or not 1 <= lookahead <= 16:
            raise ValueError("Invalid lookahead")
        self.lib = ctypes.CDLL(str(Path(library).resolve(strict=True)))
        p_float = ctypes.POINTER(ctypes.c_float)
        self._proc_type = ctypes.CFUNCTYPE(ctypes.c_int, p_float, p_float,
                                          ctypes.c_uint32, ctypes.c_uint32, ctypes.c_void_p)
        self.lib.mta_vst3_rt_create.argtypes = [ctypes.c_uint32] * 5
        self.lib.mta_vst3_rt_create.restype = ctypes.c_void_p
        self.lib.mta_vst3_rt_start.argtypes = [ctypes.c_void_p, self._proc_type, ctypes.c_void_p]
        self.lib.mta_vst3_rt_start.restype = ctypes.c_int
        self.lib.mta_vst3_rt_process.argtypes = [ctypes.c_void_p, p_float, p_float,
                                                 ctypes.c_uint32, ctypes.c_uint32]
        self.lib.mta_vst3_rt_process.restype = ctypes.c_int
        self.lib.mta_vst3_rt_stop.argtypes = [ctypes.c_void_p]
        self.lib.mta_vst3_rt_destroy.argtypes = [ctypes.c_void_p]
        self.frames = frames
        self.channels = channels
        self._handle = None
        self._worker = None
        self._processor = None
        try:
            self._worker = NativeVST3Worker(plugin, probe, channels=channels, sample_rate=rate)
            self._handle = self.lib.mta_vst3_rt_create(frames, channels, rate, 32, lookahead)
            if not self._handle:
                raise RuntimeError("Native playout runtime rejected configuration")

            @self._proc_type
            def processor(pcm_in, pcm_out, block_frames, block_channels, _user):
                try:
                    samples = [pcm_in[i] for i in range(block_frames * block_channels)]
                    result = self._worker.process(samples)
                    if len(result) != len(samples) or any(not math.isfinite(v) for v in result):
                        return -1
                    for i, value in enumerate(result):
                        pcm_out[i] = value
                    return 0
                except Exception:
                    return -1

            self._processor = processor  # hold callback alive until worker has joined
            if self.lib.mta_vst3_rt_start(self._handle, self._processor, None):
                raise RuntimeError("Could not start native playout worker thread")
        except Exception:
            self.close()
            raise

    def process(self, samples: Sequence[float]) -> list[float]:
        """Test driver only: never invoke from an actual audio callback."""
        if self._handle is None:
            raise RuntimeError("Native playout harness is closed")
        if len(samples) != self.frames * self.channels or any(not math.isfinite(v) for v in samples):
            raise ValueError("PCM buffer must match negotiated quantum and contain finite values")
        buffer_type = ctypes.c_float * len(samples)
        source = buffer_type(*samples)
        destination = buffer_type()
        status = self.lib.mta_vst3_rt_process(self._handle, source, destination,
                                               self.frames, self.channels)
        if status:
            raise RuntimeError(f"Native playout rejected audio block: {status}")
        return list(destination)

    def close(self) -> None:
        if self._handle:
            # Join C worker BEFORE releasing Python processor or IPC worker.
            self.lib.mta_vst3_rt_stop(self._handle)
            self.lib.mta_vst3_rt_destroy(self._handle)
            self._handle = None
        if self._worker:
            self._worker.close(force=True)
            self._worker = None
        self._processor = None

    def __enter__(self) -> NativeRTTestHarness:
        return self

    def __exit__(self, *_args) -> None:
        self.close()
