"""r121: C ABI smoke test of the isolated native PCM scheduler."""
import ctypes
from pathlib import Path
import shutil
import subprocess
import time

import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_native_runtime_c_abi(tmp_path):
    compiler = shutil.which("g++") or shutil.which("clang++")
    if not compiler:
        pytest.skip("C++20 compiler unavailable")
    binary = tmp_path / "libmta_rt.so"
    proc = subprocess.run(
        [compiler, "-std=c++20", "-Wall", "-Wextra", "-Werror", "-pthread", "-fPIC", "-shared",
         "-I", str(ROOT / "native/audio_core"),
         str(ROOT / "native/audio_core/vst3_runtime_api.cpp"), "-o", str(binary)],
        capture_output=True, text=True, timeout=40,
    )
    assert proc.returncode == 0, proc.stderr
    lib = ctypes.CDLL(str(binary))
    lib.mta_vst3_rt_ready.restype = ctypes.c_int
    assert lib.mta_vst3_rt_ready() == 0
    lib.mta_vst3_rt_create.argtypes = [ctypes.c_uint32] * 5
    lib.mta_vst3_rt_create.restype = ctypes.c_void_p
    lib.mta_vst3_rt_destroy.argtypes = [ctypes.c_void_p]
    lib.mta_vst3_rt_stop.argtypes = [ctypes.c_void_p]
    lib.mta_vst3_rt_state.argtypes = [ctypes.c_void_p]
    lib.mta_vst3_rt_state.restype = ctypes.c_int
    pcm_ptr = ctypes.POINTER(ctypes.c_float)
    callback_type = ctypes.CFUNCTYPE(ctypes.c_int, pcm_ptr, pcm_ptr,
                                      ctypes.c_uint32, ctypes.c_uint32, ctypes.c_void_p)
    lib.mta_vst3_rt_start.argtypes = [ctypes.c_void_p, callback_type, ctypes.c_void_p]
    lib.mta_vst3_rt_start.restype = ctypes.c_int
    lib.mta_vst3_rt_process.argtypes = [ctypes.c_void_p, pcm_ptr, pcm_ptr,
                                        ctypes.c_uint32, ctypes.c_uint32]
    lib.mta_vst3_rt_process.restype = ctypes.c_int

    assert not lib.mta_vst3_rt_create(513, 2, 48000, 16, 4)
    assert not lib.mta_vst3_rt_create(32, 3, 48000, 16, 4)
    assert not lib.mta_vst3_rt_create(32, 2, 32000, 16, 4)
    handle = lib.mta_vst3_rt_create(32, 2, 48000, 16, 4)
    assert handle
    invocations = []

    @callback_type
    def half_gain(source, destination, frames, channels, _user):
        invocations.append(frames)
        for i in range(frames * channels):
            destination[i] = source[i] * 0.5
        return 0

    try:
        assert lib.mta_vst3_rt_start(handle, half_gain, None) == 0
        assert lib.mta_vst3_rt_start(handle, half_gain, None) == -2
        inp = (ctypes.c_float * 64)(*([0.8] * 64))
        out = (ctypes.c_float * 64)()
        assert lib.mta_vst3_rt_process(handle, inp, out, 31, 2) == -2
        for _ in range(120):
            assert lib.mta_vst3_rt_process(handle, inp, out, 32, 2) == 0
            time.sleep(0.0005)
        assert invocations
        assert lib.mta_vst3_rt_state(handle) == 1
        lib.mta_vst3_rt_stop(handle)
        assert lib.mta_vst3_rt_state(handle) == 0
        assert lib.mta_vst3_rt_start(handle, half_gain, None) == -2
    finally:
        lib.mta_vst3_rt_destroy(handle)


def test_native_runtime_readiness_off():
    source = (ROOT / "native/audio_core/vst3_runtime_api.cpp").read_text()
    assert "mta_vst3_rt_ready() noexcept { return 0; }" in source
    assert "vst3_runtime_api.cpp" in (ROOT / "native/audio_core/CMakeLists.txt").read_text()
