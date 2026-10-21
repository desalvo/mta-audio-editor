"""Explicit native hardware capture. The device callback remains entirely C++."""
import atexit
import base64
import ctypes as C
import json
import threading

_LOCK=threading.RLock();_DEVICE=None;_LIB=None;_EXTERNAL=None


def lib():
    from .cpp_audio import runtime
    result=runtime().lib
    result.mta_capture_devices.argtypes=[C.c_void_p,C.c_uint32];result.mta_capture_devices.restype=C.c_int
    result.mta_capture_open.argtypes=[C.c_char_p,C.c_uint32,C.c_uint];result.mta_capture_open.restype=C.c_void_p
    result.mta_capture_read.argtypes=[C.c_void_p,C.c_void_p,C.c_uint32];result.mta_capture_read.restype=C.c_int
    result.mta_capture_close.argtypes=[C.c_void_p];result.mta_capture_close.restype=None
    return result


def ports():
    from .native_device_io import load,devices
    cfg=load()
    if cfg.backend=='portaudio':return [d['name'] for d in devices()['devices'] if d['inputs'] and (not cfg.host_api or d['host_api']==cfg.host_api)]
    buffer=C.create_string_buffer(65536)
    if lib().mta_capture_devices(buffer,len(buffer))<0:raise RuntimeError('Cannot enumerate audio inputs')
    return json.loads(buffer.value)


def start(name,rate,*,_test_null=False):
    global _DEVICE,_LIB,_EXTERNAL
    if not isinstance(name,str) or len(name)>1024 or rate not in (44100,48000,96000):raise ValueError('Invalid audio capture settings')
    with _LOCK:
        if _DEVICE or _EXTERNAL:raise ValueError('Audio capture is already running')
        if not _test_null:
            from .native_device_io import load,PortAudioCapture
            cfg=load()
            if cfg.backend=='portaudio':
                if name:cfg=cfg.model_copy(update={'input_name':name})
                from . import native_transport
                live=native_transport._DEVICE
                if live is not None and hasattr(live,'request'):
                    result=live.request('audio-capture-start',{'name':name,'rate':rate})
                    _EXTERNAL=WorkerCapture(live)
                    return result
                _EXTERNAL=PortAudioCapture(rate,cfg)
                return {'rate':rate,'channels':2}
        _LIB=lib();_DEVICE=_LIB.mta_capture_open(name.encode(),rate,int(_test_null))
        if not _DEVICE:raise RuntimeError('Cannot open audio input. Check the selected device and microphone permission.')
        return {'rate':rate,'channels':2}


class WorkerCapture:
    def __init__(self,session):self.session=session
    def read(self):return self.session.request('audio-capture-read')
    def close(self):
        if not self.session.closed:self.session.request('audio-capture-stop')


def read():
    with _LOCK:
        if _EXTERNAL:
            try:return _EXTERNAL.read()
            except RuntimeError:stop();raise
        if not _DEVICE:raise ValueError('Audio capture is not running')
        buffer=(C.c_float*(32768*2))();count=_LIB.mta_capture_read(_DEVICE,buffer,32768)
        if count<0:stop();raise RuntimeError('Audio capture overflow or device failure. Recording stopped to avoid missing samples.')
        return {'frames':count,'pcm':base64.b64encode(C.string_at(buffer,count*8)).decode()}


def stop():
    global _DEVICE,_EXTERNAL
    with _LOCK:
        if _EXTERNAL:
            device=_EXTERNAL;_EXTERNAL=None
            device.close()
        if _DEVICE:_LIB.mta_capture_close(_DEVICE);_DEVICE=None
    return {'ok':True}


atexit.register(stop)
