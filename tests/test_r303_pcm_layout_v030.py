"""0.3.0-r1: PCM layout conversion and version transition safeguards."""
from pathlib import Path
import ctypes
import subprocess
import shutil
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def test_native_pcm_layout_roundtrip():
    compiler = shutil.which('c++')
    if compiler is None:
        return
    with tempfile.TemporaryDirectory() as directory:
        binary = Path(directory) / 'libmta_pcm_test.so'
        subprocess.run([compiler, '-std=c++20', '-shared', '-fPIC', '-O2',
                        str(ROOT/'native/audio_core/audio_core.cpp'), '-o', str(binary)], check=True)
        core = ctypes.CDLL(str(binary))
        data = (ctypes.c_float*6)(1, 2, 3, 4, 5, 6)
        left = (ctypes.c_float*3)()
        right = (ctypes.c_float*3)()
        channels = (ctypes.POINTER(ctypes.c_float)*2)(left, right)
        core.mta_pcm_deinterleave.argtypes = [ctypes.POINTER(ctypes.c_float), ctypes.POINTER(ctypes.POINTER(ctypes.c_float)), ctypes.c_size_t, ctypes.c_uint]
        core.mta_pcm_interleave.argtypes = [ctypes.POINTER(ctypes.POINTER(ctypes.c_float)), ctypes.POINTER(ctypes.c_float), ctypes.c_size_t, ctypes.c_uint]
        assert core.mta_pcm_deinterleave(data, channels, 3, 2) == 0
        assert list(left) == [1, 3, 5]
        assert list(right) == [2, 4, 6]
        output = (ctypes.c_float*6)()
        assert core.mta_pcm_interleave(channels, output, 3, 2) == 0
        assert list(output) == list(data)


def test_early_version_030_r1_consistent():
    assert (ROOT/'VERSION').read_text().strip() == '0.3.0'
    assert (ROOT/'REVISION').read_text().strip() == '1'
    assert (ROOT/'RELEASE_CHANNEL').read_text().strip() == 'early'
    assert 'versionCode = 30001' in (ROOT/'mobile/android/app/build.gradle.kts').read_text()
    assert '<string>30001</string>' in (ROOT/'mobile/ios/MTAEditorMobile/Info.plist').read_text()
