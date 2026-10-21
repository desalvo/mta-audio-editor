"""Native device transport. Every control operation is serialized off the callback."""
import atexit
import ctypes as ct
import math
import os
from pathlib import Path
import tempfile
import threading
from .cpp_audio import runtime


class State(ct.Structure):
    _fields_=[('position',ct.c_uint64),('total',ct.c_uint64),('underruns',ct.c_uint64),('rate',ct.c_uint32),('playing',ct.c_uint32),('ended',ct.c_uint32),('failed',ct.c_uint32),('physical',ct.c_uint32),('peak_left',ct.c_float),('peak_right',ct.c_float)]


class Device:
    def __init__(self,path,*,_test_null=False):
        self.handle=None;self.lib=runtime().lib
        self.lib.mta_transport_abi.restype=ct.c_uint
        if self.lib.mta_transport_abi()!=1:raise RuntimeError('Unsupported native device ABI')
        self.lib.mta_transport_open.argtypes=[ct.c_char_p,ct.c_uint];self.lib.mta_transport_open.restype=ct.c_void_p
        for name in ('play','pause'):
            fn=getattr(self.lib,'mta_transport_'+name);fn.argtypes=[ct.c_void_p];fn.restype=ct.c_int
        self.lib.mta_transport_seek.argtypes=[ct.c_void_p,ct.c_uint64];self.lib.mta_transport_seek.restype=ct.c_int
        self.lib.mta_transport_gain.argtypes=[ct.c_void_p,ct.c_float];self.lib.mta_transport_gain.restype=ct.c_int
        self.lib.mta_transport_status.argtypes=[ct.c_void_p,ct.POINTER(State)];self.lib.mta_transport_status.restype=ct.c_int
        self.lib.mta_transport_close.argtypes=[ct.c_void_p];self.lib.mta_transport_close.restype=None
        self.handle=self.lib.mta_transport_open(str(Path(path).resolve()).encode('utf-8'),int(_test_null))
        if not self.handle:raise RuntimeError('Unable to open the native output device or prepared audio. Check the default system audio device or select Current engine in Settings.')

    def status(self):
        if not self.handle:raise RuntimeError('Native device is closed')
        s=State()
        if self.lib.mta_transport_status(self.handle,ct.byref(s)):raise RuntimeError('Native device status failed')
        return {**{name:getattr(s,name) for name,_ in State._fields_},'position_ms':s.position*1000/s.rate,'duration_ms':s.total*1000/s.rate,'physical':bool(s.physical)}

    def control(self,action,value=0):
        if not self.handle:raise RuntimeError('Native device is closed')
        if action in ('play','pause'):result=getattr(self.lib,'mta_transport_'+action)(self.handle)
        elif action=='seek':
            if type(value) not in (int,float) or not math.isfinite(value) or value<0:raise ValueError('Invalid native seek')
            s=self.status();frame=min(s['total'],round(value*s['rate']/1000));result=self.lib.mta_transport_seek(self.handle,frame)
        elif action=='gain':
            if type(value) not in (int,float) or not math.isfinite(value) or not 0<=value<=128:raise ValueError('Invalid native gain')
            result=self.lib.mta_transport_gain(self.handle,value)
        else:raise ValueError('Invalid native transport command')
        if result:raise RuntimeError('Native transport '+action+' failed ('+str(result)+')')
        return self.status()

    def close(self):
        if self.handle:self.lib.mta_transport_close(self.handle);self.handle=None

    def __enter__(self):return self

    def __exit__(self,*args):self.close()

def bind_stream(lib):
    lib.mta_transport_open_stream.argtypes=[ct.c_uint32,ct.c_uint64,ct.c_uint]
    lib.mta_transport_open_stream.restype=ct.c_void_p
    for name in ('play','pause'):
        fn=getattr(lib,'mta_transport_'+name);fn.argtypes=[ct.c_void_p];fn.restype=ct.c_int
    lib.mta_transport_seek.argtypes=[ct.c_void_p,ct.c_uint64];lib.mta_transport_seek.restype=ct.c_int
    lib.mta_transport_gain.argtypes=[ct.c_void_p,ct.c_float];lib.mta_transport_gain.restype=ct.c_int
    lib.mta_transport_status.argtypes=[ct.c_void_p,ct.POINTER(State)];lib.mta_transport_status.restype=ct.c_int
    lib.mta_transport_close.argtypes=[ct.c_void_p];lib.mta_transport_close.restype=None
    lib.mta_transport_push.argtypes=[ct.c_void_p,ct.POINTER(ct.c_float),ct.c_uint];lib.mta_transport_push.restype=ct.c_int
    lib.mta_transport_buffered.argtypes=[ct.c_void_p];lib.mta_transport_buffered.restype=ct.c_uint64
    lib.mta_transport_finish.argtypes=[ct.c_void_p];lib.mta_transport_finish.restype=ct.c_int


class StreamDevice(Device):
    """Only the producer calls push; device callback stays entirely in C++."""
    def __init__(self,rate,total,*,_test_null=False):
        self.handle=None;self.lib=runtime().lib
        bind_stream(self.lib)
        self.handle=self.lib.mta_transport_open_stream(rate,total,int(_test_null))
        if not self.handle:raise RuntimeError('Native live output device is unavailable')

    def push(self,pcm):
        import numpy as np
        if pcm.dtype!=np.float32 or pcm.ndim!=2 or pcm.shape[1]!=2 or not pcm.flags.c_contiguous or not 1<=len(pcm)<=4096:raise ValueError('Invalid live PCM')
        result=self.lib.mta_transport_push(self.handle,pcm.ctypes.data_as(ct.POINTER(ct.c_float)),len(pcm))
        if result<0:raise RuntimeError('Live plugin returned invalid PCM')
        return result==0

    def buffered(self):return self.lib.mta_transport_buffered(self.handle)

    def finish(self):
        if self.lib.mta_transport_finish(self.handle):raise RuntimeError('Cannot finish live output')


_LOCK=threading.RLock();_DEVICE=None;_SCRATCH=None;_PROJECT=None;_CANCEL_EPOCH=0
_PREPARATION={"stage":"idle","done":0,"total":0,"track":""}


def _guard():
    from .audio_backend import requested
    if os.getenv('MTA_NATIVE_SINGLE_USER','').lower()!='true' or requested()!='cpp':raise ValueError('Native device transport requires the selected C++ engine in a native application')


def stop():
    global _DEVICE,_SCRATCH,_PROJECT,_CANCEL_EPOCH
    _CANCEL_EPOCH+=1
    with _LOCK:
        states=[];project_id=_PROJECT
        if _DEVICE:
            try:
                if hasattr(_DEVICE,'states'):states=_DEVICE.states()
                if states and _PROJECT:
                    from .storage import load_project,save_project
                    project=load_project(_PROJECT)
                    for item in states:
                        route=next((t for t in project.tracks if t.id==item['route']),None)
                        inserts=route.inserts if route else project.master_inserts if item['route']=='master' else []
                        insert=next((i for i in inserts if i.id==item['insert']),None)
                        if route and item['insert']=='instrument':insert=route.instrument
                        if insert and insert.params.get('path')==item['params'].get('path'):insert.params=item['params']
                    save_project(project,_skip_flac_conversion=True)
            except Exception:
                import logging
                logging.getLogger(__name__).exception('Could not save live VST3 state before stopping')
            finally:_DEVICE.close();_DEVICE=None
        if _SCRATCH:_SCRATCH.cleanup();_SCRATCH=None
        _PROJECT=None
    return {'ok':True,'active':False,'project_id':project_id,'states':states}


def prepare_play(pid,cursor_ms=0,*,start_playing=True,midi_options=None):
    global _DEVICE,_SCRATCH,_PROJECT,_PREPARATION
    _PREPARATION={"stage":"loading","done":0,"total":0,"track":""}
    _guard()
    if type(start_playing) is not bool:raise ValueError('Invalid native playback state')
    if type(cursor_ms) not in (int,float) or not math.isfinite(cursor_ms) or cursor_ms<0:raise ValueError('Invalid native seek')
    from .storage import load_project,audio_path
    from .main import validate_project_files
    from .audio_engine import render_mix
    with _LOCK:
        project=load_project(pid);validate_project_files(project)
        if pid==_PROJECT and hasattr(_DEVICE,'update'):
            updated=_DEVICE.update(project)
            if not updated.get('requires_prepare'):
                if not start_playing:_DEVICE.control('pause')
                _DEVICE.control('seek',cursor_ms)
                if start_playing:_DEVICE.control('play')
                return {'ok':True,'active':True,'project_id':pid,**_DEVICE.status()}
        stop();epoch=_CANCEL_EPOCH;scratch=tempfile.TemporaryDirectory(prefix='mta-native-device-')
        try:
            from .vst3_live import available
            from .native_device_io import load as device_settings
            if available() or (os.getenv('MTA_NATIVE_SINGLE_USER','').lower()=='true' and device_settings().backend=='portaudio') or any(t.kind=='midi' for t in project.tracks) or any(i.enabled and i.plugin=='vst3' for items in [project.master_inserts,*[t.inserts for t in project.tracks]] for i in items):
                from .vst3_live import Session
                from .live_sources import prepare
                def progress(done,total,track):
                    global _PREPARATION
                    _PREPARATION={'stage':'sources','done':done,'total':total,'track':track}
                    if epoch!=_CANCEL_EPOCH:raise RuntimeError('Native playback preparation cancelled')
                sources=[audio_path(project.id,t.filename) for t in project.tracks]
                paths,raw_sources=prepare(project,sources,scratch.name,progress)
                _PREPARATION={'stage':'graph','done':len(paths),'total':len(paths),'track':''}
                device=Session(project,paths,cursor_ms,cancelled=lambda:epoch!=_CANCEL_EPOCH,paused=not start_playing,raw_sources=raw_sources,**({'midi_options':midi_options} if midi_options else {}))
                _PREPARATION={'stage':'ready','done':len(paths),'total':len(paths),'track':''}
                _DEVICE=device;_SCRATCH=scratch;_PROJECT=pid
                return {'ok':True,'active':True,'project_id':pid,**device.status()}
            target=Path(scratch.name)/'prepared.wav' 
            _PREPARATION={'stage':'mix','done':0,'total':len(project.tracks),'track':''}
            render_mix(project,audio_path,target,fmt='wav',sample_rate=int(project.sample_rate),wav_bit_depth=32)
            if epoch!=_CANCEL_EPOCH:raise RuntimeError('Native playback preparation cancelled')
            device=Device(target)
            try:
                device.control('seek',cursor_ms)
                if start_playing:device.control('play')
            except BaseException:device.close();raise
            _DEVICE=device;_SCRATCH=scratch;_PROJECT=pid
            return {'ok':True,'active':True,'project_id':pid,**device.status()}
        except BaseException:scratch.cleanup();raise


def control(action,value=0):
    if action=='stop':return stop()
    _guard()
    with _LOCK:
        if not _DEVICE:return {'ok':True,'active':False}
        data=_DEVICE.status() if action=='status' else _DEVICE.control(action,value)
        return {'ok':True,'active':True,'project_id':_PROJECT,**data}


atexit.register(stop)


def snapshot():
    if not _LOCK.acquire(blocking=False):return {'active':False,'preparing':True,'physical':False}
    try:return {'active':True,**_DEVICE.status()} if _DEVICE else {'active':False,'preparing':False,'physical':False}
    finally:_LOCK.release()


def live_update(pid,mixer=None):
    from .storage import load_project
    with _LOCK:
        if pid!=_PROJECT or not hasattr(_DEVICE,'update'):return {'requires_prepare':True}
        if mixer is not None:
            from .live_mixer import apply
            return _DEVICE.update(apply(_DEVICE.project,mixer))
        return _DEVICE.update(load_project(pid))


def live_editor(pid,route,insert):
    with _LOCK:
        if pid!=_PROJECT or not hasattr(_DEVICE,'editor'):
            from .audio_backend import requested
            if requested()!='cpp':return None
            prepare_play(pid,0,start_playing=False)
            if not hasattr(_DEVICE,'editor'):return None
        result=_DEVICE.editor(route,insert);result['editor_id']='live:'+result['editor_id'];return result


def live_editor_poll(token):
    with _LOCK:
        if not hasattr(_DEVICE,'editor_poll'):raise RuntimeError('The live VST3 session has ended')
        return _DEVICE.editor_poll(token)


def preparation_status():
    return dict(_PREPARATION)
