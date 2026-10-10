"""Native C++ constant-power panning regression tests."""
import ctypes
import math
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_compiled_pan_mixer(tmp_path):
    compiler = shutil.which('c++') or shutil.which('g++')
    if compiler is None:
        pytest.skip('C++ compiler unavailable')
    src = ROOT / 'native/audio_core/audio_core.cpp'
    out = tmp_path / 'libmta_pcm_pan.so'
    subprocess.run([compiler, '-std=c++20', '-shared', '-fPIC', '-O2', str(src), '-o', str(out)], check=True)
    fn = ctypes.CDLL(str(out)).mta_pcm_mix_mono_stereo
    fn.argtypes = [ctypes.POINTER(ctypes.c_float), ctypes.POINTER(ctypes.c_float), ctypes.c_size_t, ctypes.c_float, ctypes.c_float]
    fn.restype = ctypes.c_int
    mono = (ctypes.c_float * 2)(1.0, -1.0)
    for pan, left, right in [(-1.0, 1.0, 0.0), (0.0, math.sqrt(.5), math.sqrt(.5)), (1.0, 0.0, 1.0)]:
        stereo = (ctypes.c_float * 4)()
        assert fn(stereo, mono, 2, 1, pan) == 0
        assert list(stereo) == pytest.approx([left, right, -left, -right], abs=2e-7)
    stereo = (ctypes.c_float * 4)(3, 4, 5, 6)
    bad = (ctypes.c_float * 2)(1, float('nan'))
    assert fn(stereo, bad, 2, 1, 0) == -2
    assert list(stereo) == [3, 4, 5, 6]
    assert fn(stereo, mono, 2, 1, 2) == -1
    assert list(stereo) == [3, 4, 5, 6]
