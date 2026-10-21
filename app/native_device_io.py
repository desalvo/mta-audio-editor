"""Explicit PortAudio/ASIO output; PortAudio invokes a compiled C++ callback.

The sounddevice library-author API (_StreamBase) is pinned to 0.5.5. Its raw
callback and userdata are native pointers, never Python functions. No ASIO SDK
or driver is downloaded by this module.
"""
import ctypes as C
import math
import os
import threading
from typing import Literal
from pydantic import BaseModel,ConfigDict,Field,model_validator

KEY='mta.native.audio_io.v1'
_LOCK=threading.RLock()


class Settings(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True)
    backend:Literal['miniaudio','portaudio']='miniaudio'
    host_api:str=Field(default='',max_length=100)
    output_name:str=Field(default='',max_length=512)
    output_channels:int=Field(default=2,ge=1,le=64)
    output_matrix:list[list[float]]=Field(default_factory=lambda:[[1.,0.],[0.,1.]],max_length=64)
    input_name:str=Field(default='',max_length=512)
    input_channels:int=Field(default=2,ge=1,le=64)
    input_matrix:list[list[float]]=Field(default_factory=lambda:[[1.,0.],[0.,1.]],max_length=2)
    blocksize:int=Field(default=512,ge=64,le=4096)
    latency:float=Field(default=.04,ge=.005,le=1,allow_inf_nan=False)

    @model_validator(mode='after')
    def matrix(self):
        if len(self.output_matrix)!=self.output_channels or any(len(row)!=2 for row in self.output_matrix):raise ValueError('Output matrix must have one row per physical output and two columns (master L/R)')
        if len(self.input_matrix)!=2 or any(len(row)!=self.input_channels for row in self.input_matrix):raise ValueError('Input matrix must have two rows and one column per physical input')
        if any(not math.isfinite(x) or abs(x)>4 for matrix in (self.output_matrix,self.input_matrix) for row in matrix for x in row):raise ValueError('Routing gains must be finite between -4 and +4')
        if self.blocksize&(self.blocksize-1):raise ValueError('Buffer size must be a power of two')
        if self.backend=='miniaudio' and (self.output_name or self.host_api or self.output_channels!=2 or self.output_matrix!=[[1.,0.],[0.,1.]] or self.input_name or self.input_channels!=2 or self.input_matrix!=[[1.,0.],[0.,1.]]):raise ValueError('Choose PortAudio for explicit device/channel routing')
        return self


def guard():
    if os.getenv('MTA_NATIVE_SINGLE_USER','').lower()!='true':raise ValueError('Hardware audio configuration is available only in the native application')


def load():
    guard()
    from .user_preferences import load as preferences
    value=preferences({'id':0})['values'].get(KEY)
    return Settings.model_validate_json(value) if value else Settings()


def sounddevice():
    # ASIO-capable PortAudio is selected before the first module import.
    import importlib.util
    import sys
    if sys.platform=='win32':
        spec=importlib.util.find_spec('_sounddevice_data')
        folders=list(spec.submodule_search_locations or []) if spec else []
        if any(list((__import__('pathlib').Path(folder)/'portaudio-binaries').glob('*-asio.dll')) for folder in folders):
            os.environ.setdefault('SD_ENABLE_ASIO','1')
    import sounddevice as sd
    if sd.__version__!='0.5.5':raise RuntimeError('Native device backend requires sounddevice 0.5.5')
    return sd


def driver_errors():
    import sys
    sd=sys.modules.get('sounddevice')
    return (ImportError,OSError,ValueError,RuntimeError)+((sd.PortAudioError,) if sd and hasattr(sd,'PortAudioError') else ())


def devices():
    guard();sd=sounddevice();apis=sd.query_hostapis();items=[]
    for index,device in enumerate(sd.query_devices()):
        if not device['max_input_channels'] and not device['max_output_channels']:continue
        items.append({'index':index,'name':device['name'],'host_api':apis[device['hostapi']]['name'],
            'inputs':min(64,device['max_input_channels']),'outputs':min(64,device['max_output_channels']),
            'default_sample_rate':device['default_samplerate']})
    return {'devices':items,'host_apis':[a['name'] for a in apis],'asio_available':any('ASIO' in a['name'].upper() and a['devices'] for a in apis)}


def resolve(cfg,direction='output'):
    sd=sounddevice();api=sd.query_hostapis();name=getattr(cfg,direction+'_name')
    if not name and not cfg.host_api:
        index=sd.default.device[1 if direction=='output' else 0]
        if index<0:raise ValueError('No default '+direction+' device is available')
    else:
        matches=[i for i,d in enumerate(sd.query_devices()) if d['max_'+direction+'_channels'] and
            (not name or d['name']==name) and (not cfg.host_api or api[d['hostapi']]['name']==cfg.host_api)]
        if len(matches)!=1:raise ValueError('Selected '+direction+' device is missing or ambiguous; select it again in Audio I/O settings')
        index=matches[0]
    info=sd.query_devices(index);count=getattr(cfg,direction+'_channels')
    if count>info['max_'+direction+'_channels']:raise ValueError('Selected device has fewer '+direction+' channels than the routing matrix')
    host=dict(api[info['hostapi']])
    if 'type' not in host:host['type']=int(sd._lib.Pa_GetHostApiInfo(info['hostapi']).type)
    return int(index),info,host


def save(body):
    guard();cfg=Settings.model_validate(body)
    if cfg.backend=='portaudio':
        resolve(cfg)
        if cfg.input_name:resolve(cfg,'input')
    from .user_preferences import patch
    patch({'id':0},{KEY:cfg.model_dump_json()})
    return cfg.model_dump()


class PortAudioDevice:
    """The producer remains Python/C++ DSP; the hardware callback is pure C++."""
    def __init__(self,rate,total,settings=None):
        from .cpp_audio import runtime
        from .native_transport import bind_stream
        self.handle=None;self.stream=None;self.capture=None;self.lib=runtime().lib;bind_stream(self.lib)
        self.cfg=settings or load();sd=sounddevice();index,info,host=resolve(self.cfg)
        self.lib.mta_transport_open_external.argtypes=[C.c_uint32,C.c_uint64,C.c_uint32,C.POINTER(C.c_float)]
        self.lib.mta_transport_open_external.restype=C.c_void_p
        self.lib.mta_transport_external_callback.argtypes=[];self.lib.mta_transport_external_callback.restype=C.c_void_p
        self.lib.mta_transport_external_attached.argtypes=[C.c_void_p];self.lib.mta_transport_external_attached.restype=C.c_int
        matrix=(C.c_float*(self.cfg.output_channels*2))(*[x for row in self.cfg.output_matrix for x in row])
        self.handle=self.lib.mta_transport_open_external(rate,total,self.cfg.output_channels,matrix)
        if not self.handle:raise RuntimeError('Cannot create C++ external output ring')
        try:
            # ASIO opens exactly the configured physical channels (0-based).
            extra=sd.AsioSettings(channel_selectors=list(range(self.cfg.output_channels))) if host['type']==3 else None
            self.stream=sd._StreamBase(kind='output',samplerate=rate,blocksize=self.cfg.blocksize,device=index,
                channels=self.cfg.output_channels,dtype='float32',latency=self.cfg.latency,extra_settings=extra,
                callback=sd._ffi.cast('PaStreamCallback*',self.lib.mta_transport_external_callback()),
                userdata=sd._ffi.cast('void*',self.handle),wrap_callback=None)
            self.lib.mta_transport_external_attached(self.handle)
            self.device_name=info['name'];self.host_api=host['name']
        except BaseException:self.close();raise

    def status(self):
        from .native_transport import Device
        result=Device.status(self)
        if not self.stream or (result['playing'] and not self.stream.active):result.update(failed=True,error='Selected PortAudio device stopped unexpectedly')
        latency=self.stream.latency if self.stream else None
        if isinstance(latency,tuple):latency=latency[1]
        return {**result,'device_backend':'portaudio','output_device':self.device_name,'host_api':self.host_api,
            'output_channels':self.cfg.output_channels,'output_latency_seconds':latency}

    def control(self,action,value=0):
        from .native_transport import Device
        with _LOCK:
            resume=action=='seek' and bool(self.status()['playing'])
            if action in ('pause','seek') and not self.capture and self.stream and self.stream.active:self.stream.abort(ignore_errors=False)
            result=Device.control(self,action,value)
            if action=='play' or resume:
                if not self.stream:raise RuntimeError('Selected output device is closed; prepare playback again')
                try:
                    if not self.stream.active:self.stream.start()
                except BaseException:self.lib.mta_transport_pause(self.handle);raise
                result=self.status()
            return result

    def push(self,pcm):
        from .native_transport import StreamDevice
        return StreamDevice.push(self,pcm)

    def buffered(self):return self.lib.mta_transport_buffered(self.handle)

    def finish(self):
        if self.lib.mta_transport_finish(self.handle):raise RuntimeError('Cannot finish external output')

    def capture_start(self,name,rate):
        if self.capture:raise ValueError('Capture already active')
        if rate!=self.status()['rate']:raise ValueError('Playback and capture sample rates must match')
        cfg=self.cfg.model_copy(update={'input_name':name or self.cfg.input_name})
        sd=sounddevice();input_index,_,input_host=resolve(cfg,'input');output_index,_,host=resolve(cfg)
        if input_host['type']!=host['type'] or (host['type']==3 and input_index!=output_index):
            raise ValueError('Duplex playback/capture requires the same host API and, for ASIO, the same device')
        self.lib.mta_capture_open_external.argtypes=[C.c_uint32,C.POINTER(C.c_float)];self.lib.mta_capture_open_external.restype=C.c_void_p
        self.lib.mta_capture_read.argtypes=[C.c_void_p,C.c_void_p,C.c_uint32];self.lib.mta_capture_read.restype=C.c_int
        self.lib.mta_capture_close.argtypes=[C.c_void_p]
        self.lib.mta_transport_capture_attach.argtypes=[C.c_void_p,C.c_void_p];self.lib.mta_transport_capture_attach.restype=C.c_int
        matrix=(C.c_float*(cfg.input_channels*2))(*[x for row in cfg.input_matrix for x in row])
        capture=self.lib.mta_capture_open_external(cfg.input_channels,matrix)
        if not capture:raise RuntimeError('Cannot create duplex capture ring')
        was=bool(self.status()['playing']);self.control('pause');self.stream.close();self.stream=None
        try:
            if self.lib.mta_transport_capture_attach(self.handle,capture):raise RuntimeError('Cannot attach capture ring')
            extra=(sd.AsioSettings(channel_selectors=list(range(cfg.input_channels))),sd.AsioSettings(channel_selectors=list(range(cfg.output_channels)))) if host['type']==3 else None
            self.stream=sd._StreamBase(kind='duplex',samplerate=rate,blocksize=cfg.blocksize,device=(input_index,output_index),
                channels=(cfg.input_channels,cfg.output_channels),dtype='float32',latency=cfg.latency,extra_settings=extra,
                callback=sd._ffi.cast('PaStreamCallback*',self.lib.mta_transport_external_callback()),
                userdata=sd._ffi.cast('void*',self.handle),wrap_callback=None)
            self.capture=capture
            if was:self.lib.mta_transport_play(self.handle)
            self.stream.start()
            return {'rate':rate,'channels':2,'duplex':True,'position_ms':self.status()['position_ms']}
        except BaseException:
            if self.stream:self.stream.close();self.stream=None
            self.lib.mta_transport_pause(self.handle);self.lib.mta_transport_capture_attach(self.handle,None)
            self.lib.mta_capture_close(capture);self.capture=None
            raise

    def capture_read(self):
        import base64
        if not self.capture:raise ValueError('Duplex capture is not active')
        data=(C.c_float*65536)();count=self.lib.mta_capture_read(self.capture,data,32768)
        if count<0:raise RuntimeError('Duplex capture overflow; stop and save the recorded portion')
        return {'frames':count,'pcm':base64.b64encode(C.string_at(data,count*8)).decode()}

    def capture_stop(self):
        if not self.capture:return {'ok':True}
        # Close the microphone stream at Stop; do not keep silent capture open.
        was=bool(self.status()['playing']);self.control('pause');self.stream.close();self.stream=None
        self.lib.mta_transport_capture_attach(self.handle,None);self.lib.mta_capture_close(self.capture);self.capture=None
        sd=sounddevice();index,_,host=resolve(self.cfg)
        extra=sd.AsioSettings(channel_selectors=list(range(self.cfg.output_channels))) if host['type']==3 else None
        self.stream=sd._StreamBase(kind='output',samplerate=self.status()['rate'],blocksize=self.cfg.blocksize,device=index,
            channels=self.cfg.output_channels,dtype='float32',latency=self.cfg.latency,extra_settings=extra,
            callback=sd._ffi.cast('PaStreamCallback*',self.lib.mta_transport_external_callback()),
            userdata=sd._ffi.cast('void*',self.handle),wrap_callback=None)
        if was:self.control('play')
        return {'ok':True}

    def close(self):
        if self.stream:
            self.stream.close();self.stream=None
        if self.capture:
            self.lib.mta_capture_close(self.capture);self.capture=None
        if self.handle:self.lib.mta_transport_close(self.handle);self.handle=None


def output(rate,total,*,test_null=False):
    from .native_transport import StreamDevice
    if test_null:return StreamDevice(rate,total,_test_null=True)
    cfg=load()
    return PortAudioDevice(rate,total,cfg) if cfg.backend=='portaudio' else StreamDevice(rate,total)


class PortAudioCapture:
    def __init__(self,rate,cfg):
        from .native_capture import lib
        self.lib=lib();self.handle=None;self.stream=None
        sd=sounddevice();index,_,host=resolve(cfg,'input')
        self.lib.mta_capture_open_external.argtypes=[C.c_uint32,C.POINTER(C.c_float)];self.lib.mta_capture_open_external.restype=C.c_void_p
        self.lib.mta_capture_external_callback.argtypes=[];self.lib.mta_capture_external_callback.restype=C.c_void_p
        matrix=(C.c_float*(cfg.input_channels*2))(*[x for row in cfg.input_matrix for x in row])
        self.handle=self.lib.mta_capture_open_external(cfg.input_channels,matrix)
        if not self.handle:raise RuntimeError('Cannot create C++ capture ring')
        try:
            extra=sd.AsioSettings(channel_selectors=list(range(cfg.input_channels))) if host['type']==3 else None
            self.stream=sd._StreamBase(kind='input',samplerate=rate,blocksize=cfg.blocksize,device=index,channels=cfg.input_channels,
                dtype='float32',latency=cfg.latency,extra_settings=extra,
                callback=sd._ffi.cast('PaStreamCallback*',self.lib.mta_capture_external_callback()),
                userdata=sd._ffi.cast('void*',self.handle),wrap_callback=None)
            self.stream.start()
        except BaseException:self.close();raise

    def read(self):
        import base64
        if not self.stream.active:raise RuntimeError('Selected input device stopped; capture was not replaced by another device')
        buffer=(C.c_float*65536)();count=self.lib.mta_capture_read(self.handle,buffer,32768)
        if count<0:raise RuntimeError('Capture overflow/device failure; recording stopped to avoid missing samples')
        return {'frames':count,'pcm':base64.b64encode(C.string_at(buffer,count*8)).decode()}

    def close(self):
        if self.stream:self.stream.close();self.stream=None
        if self.handle:self.lib.mta_capture_close(self.handle);self.handle=None


def register_routes(app,actor):
    from fastapi import HTTPException,Request
    def check(request):
        actor(request)
        try:guard()
        except ValueError as exc:raise HTTPException(404,str(exc)) from exc

    @app.get('/api/native/audio-io')
    def configuration(request:Request):
        check(request)
        result={'settings':load().model_dump(),'devices':[],'host_apis':[],'asio_available':False,'error':''}
        try:result.update(devices())
        except driver_errors() as exc:result['error']=str(exc)
        return result

    @app.put('/api/native/audio-io')
    def configure(body:dict,request:Request):
        check(request)
        from .native_transport import stop
        from .native_capture import stop as stop_capture
        try:
            cfg=Settings.model_validate(body)
            if cfg.backend=='portaudio':
                resolve(cfg)
                if cfg.input_name:resolve(cfg,'input')
            stop_capture();stop()
            return {'settings':save(cfg.model_dump())}
        except driver_errors() as exc:raise HTTPException(422,str(exc)) from exc
