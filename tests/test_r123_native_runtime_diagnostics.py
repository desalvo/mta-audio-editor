"""r123: C ABI diagnostics available only after the worker has stopped."""
import ctypes
from pathlib import Path
import shutil
import subprocess
import time

import pytest

ROOT = Path(__file__).resolve().parents[1]


class Stats(ctypes.Structure):
    _fields_ = [(name, ctypes.c_uint64) for name in
                ("idle_polls", "iterations", "failures", "completions")]


def test_native_diagnostics_lifecycle(tmp_path):
    compiler = shutil.which("g++") or shutil.which("clang++")
    if not compiler:
        pytest.skip("C++ compiler unavailable")
    library = tmp_path / "libvst3_rt.so"
    subprocess.run([compiler, "-std=c++20", "-Wall", "-Wextra", "-Werror",
                    "-pthread", "-fPIC", "-shared",
                    str(ROOT / "native/audio_core/vst3_runtime_api.cpp"),
                    "-o", str(library)], check=True, timeout=45)
    dll = ctypes.CDLL(str(library))
    dll.mta_vst3_rt_abi_version.restype = ctypes.c_uint32
    assert dll.mta_vst3_rt_abi_version() >= 1
    dll.mta_vst3_rt_create.argtypes = [ctypes.c_uint32] * 5
    dll.mta_vst3_rt_create.restype = ctypes.c_void_p
    dll.mta_vst3_rt_stopped_stats.argtypes = [ctypes.c_void_p, ctypes.POINTER(Stats)]
    dll.mta_vst3_rt_stopped_stats.restype = ctypes.c_int
    dll.mta_vst3_rt_stop.argtypes = [ctypes.c_void_p]
    dll.mta_vst3_rt_destroy.argtypes = [ctypes.c_void_p]
    float_ptr = ctypes.POINTER(ctypes.c_float)
    processor_type = ctypes.CFUNCTYPE(ctypes.c_int, float_ptr, float_ptr,
                                      ctypes.c_uint32, ctypes.c_uint32, ctypes.c_void_p)
    dll.mta_vst3_rt_start.argtypes = [ctypes.c_void_p, processor_type, ctypes.c_void_p]
    dll.mta_vst3_rt_start.restype = ctypes.c_int
    dll.mta_vst3_rt_process.argtypes = [ctypes.c_void_p, float_ptr, float_ptr,
                                        ctypes.c_uint32, ctypes.c_uint32]
    dll.mta_vst3_rt_process.restype = ctypes.c_int
    stats = Stats()
    assert dll.mta_vst3_rt_stopped_stats(None, ctypes.byref(stats)) == -1
    handle = dll.mta_vst3_rt_create(32, 1, 48000, 16, 4)
    assert handle
    @processor_type
    def copy_audio(source, target, frames, channels, _context):
        for i in range(frames * channels):
            target[i] = source[i]
        return 0
    try:
        assert dll.mta_vst3_rt_start(handle, copy_audio, None) == 0
        assert dll.mta_vst3_rt_stopped_stats(handle, ctypes.byref(stats)) == -2
        source = (ctypes.c_float * 32)(*([0.2] * 32))
        target = (ctypes.c_float * 32)()
        for _ in range(40):
            assert dll.mta_vst3_rt_process(handle, source, target, 32, 1) == 0
            time.sleep(0.001)
        dll.mta_vst3_rt_stop(handle)
        assert dll.mta_vst3_rt_stopped_stats(handle, ctypes.byref(stats)) == 0
        assert stats.iterations > 0
        assert stats.completions > 0
        assert stats.failures == 0
    finally:
        dll.mta_vst3_rt_destroy(handle)
