"""Explicit native hardware capture. The device callback remains entirely C++."""
import atexit
import base64
import ctypes as C
import json
import threading

_LOCK=threading.RLock();_DEVICE=None;_LIB=None


def lib():
    from .cpp_audio import runtime
    result=runtime().lib
    result.mta_capture_devices.argtypes=[C.c_void_p,C.c_uint32];result.mta_capture_devices.restype=C.c_int
    result.mta_capture_open.argtypes=[C.c_char_p,C.c_uint32,C.c_uint];result.mta_capture_open.restype=C.c_void_p
    result.mta_capture_read.argtypes=[C.c_void_p,C.c_void_p,C.c_uint32];result.mta_capture_read.restype=C.c_int
    result.mta_capture_close.argtypes=[C.c_void_p];result.mta_capture_close.restype=None
    return result


def ports():
    buffer=C.create_string_buffer(65536)
    if lib().mta_capture_devices(buffer,len(buffer))<0:raise RuntimeError('Cannot enumerate audio inputs')
    return json.loads(buffer.value)


def start(name,rate,*,_test_null=False):
    global _DEVICE,_LIB
    if not isinstance(name,str) or len(name)>1024 or rate not in (44100,48000,96000):raise ValueError('Invalid audio capture settings')
    with _LOCK:
        if _DEVICE:raise ValueError('Audio capture is already running')
        _LIB=lib();_DEVICE=_LIB.mta_capture_open(name.encode(),rate,int(_test_null))
        if not _DEVICE:raise RuntimeError('Cannot open audio input. Check the selected device and microphone permission.')
        return {'rate':rate,'channels':2}


def read():
    with _LOCK:
        if not _DEVICE:raise ValueError('Audio capture is not running')
        buffer=(C.c_float*(32768*2))();count=_LIB.mta_capture_read(_DEVICE,buffer,32768)
        if count<0:stop();raise RuntimeError('Audio capture overflow or device failure. Recording stopped to avoid missing samples.')
        return {'frames':count,'pcm':base64.b64encode(C.string_at(buffer,count*8)).decode()}


def stop():
    global _DEVICE
    with _LOCK:
        if _DEVICE:_LIB.mta_capture_close(_DEVICE);_DEVICE=None
    return {'ok':True}


atexit.register(stop)
