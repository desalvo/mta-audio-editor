"""Compile the real C++ audio FIFO and check its ABI across buffer wraparound."""
import ctypes
from pathlib import Path
import subprocess
import sys
import pytest

ROOT=Path(__file__).resolve().parents[1]

@pytest.fixture(scope="module")
def library(tmp_path_factory):
    if sys.platform == 'win32':
        pytest.skip('C++ build is tested by Windows CI')
    build=tmp_path_factory.mktemp('spsc')
    output=build/('libaudio.dylib' if sys.platform=='darwin' else 'libaudio.so')
    subprocess.run(['c++','-std=c++20','-O2','-fPIC','-shared',str(ROOT/'native/audio_core/audio_core.cpp'),'-o',str(output)],check=True,capture_output=True)
    lib=ctypes.CDLL(str(output))
    lib.mta_spsc_create.argtypes=[ctypes.c_size_t];lib.mta_spsc_create.restype=ctypes.c_void_p
    lib.mta_spsc_destroy.argtypes=[ctypes.c_void_p]
    lib.mta_spsc_available.argtypes=[ctypes.c_void_p];lib.mta_spsc_available.restype=ctypes.c_size_t
    lib.mta_spsc_write.argtypes=[ctypes.c_void_p,ctypes.POINTER(ctypes.c_float),ctypes.c_size_t];lib.mta_spsc_write.restype=ctypes.c_size_t
    lib.mta_spsc_read.argtypes=[ctypes.c_void_p,ctypes.POINTER(ctypes.c_float),ctypes.c_size_t];lib.mta_spsc_read.restype=ctypes.c_size_t
    return lib

def test_spsc_wrap_and_atomic_full_block(library):
    l=library; h=l.mta_spsc_create(4)
    try:
        a=(ctypes.c_float*3)(1,2,3);out=(ctypes.c_float*4)()
        assert l.mta_spsc_write(h,a,3)==3
        assert l.mta_spsc_write(h,a,3)==0
        assert l.mta_spsc_available(h)==3
        assert l.mta_spsc_read(h,out,2)==2
        assert list(out)[:2]==[1,2]
        assert l.mta_spsc_write(h,a,3)==3
        assert l.mta_spsc_read(h,out,4)==4
        assert list(out)==[3,1,2,3]
        assert l.mta_spsc_available(h)==0
    finally:l.mta_spsc_destroy(h)

def test_spsc_rejects_nonfinite_input(library):
    l=library;h=l.mta_spsc_create(3)
    try:
        arr=(ctypes.c_float*2)(1,float('nan'))
        assert l.mta_spsc_write(h,arr,2)==0
        assert l.mta_spsc_available(h)==0
    finally:l.mta_spsc_destroy(h)
