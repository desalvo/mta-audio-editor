"""Sample-domain host timing, shared by instruments, effects and offline renders."""
from contextvars import ContextVar
from functools import wraps
import math

_RENDER=ContextVar('mta_vst_transport',default=None)
_PROJECT=ContextVar('mta_vst_project',default=None)

def render_project():return _PROJECT.get()


def runtime_available():
    try:
        from pedalboard import VST3Plugin
        return all(hasattr(VST3Plugin,k) for k in ('_mta_set_transport','_mta_set_musical_position','_mta_process_sidechain'))
    except ImportError:return False


def settings(project):
    return {key:getattr(project,key) for key in ('bpm','base_bpm','time_signature','metronome_bpm','metronome_time_signature','vst_host_sync','vst_loop_enabled','vst_loop_start_ms','vst_loop_end_ms','metronome_mode','metronome_zone_bpms','metronome_zone_signatures','metronome_manual_zone_bpms','metronome_manual_zone_signatures','metronome_grid_origin_ms','metronome_shift_ms','musical_origin_ms','metronome_start_ms','metronome_pre_roll_bars')} | {'markers':[m.model_dump() for m in project.markers],'adaptive_tempo_map':[p.model_dump() for p in project.adaptive_tempo_map]}


def render_settings():return _RENDER.get()


def project_scope(function):
    @wraps(function)
    def wrapped(project,*args,**kwargs):
        data=kwargs.pop('host_transport',None)
        token=_RENDER.set(data if data is not None else settings(project));project_token=_PROJECT.set(project)
        try:return function(project,*args,**kwargs)
        finally:_RENDER.reset(token);_PROJECT.reset(project_token)
    return wrapped


def track_scope(function):
    @wraps(function)
    def wrapped(*args,**kwargs):
        project=kwargs.pop('host_project',None)
        project_token=_PROJECT.set(project) if project is not None else None
        data=kwargs.pop('host_transport',None)
        if project is not None:data=settings(project)
        if data is None:return function(*args,**kwargs)
        token=_RENDER.set(data)
        try:return function(*args,**kwargs)
        finally:
            _RENDER.reset(token)
            if project_token is not None:_PROJECT.reset(project_token)
    return wrapped


class HostClock:
    def __init__(self,project=None,rate=44100):
        self.data=settings(project) if project is not None else (_RENDER.get() or {})
        self.rate=rate;self.playing=True;self.external=None;self._map_data=None;self._map=None

    def context(self,frame):
        data=self.data
        playing=self.playing
        if self.external:
            anchor,origin,playing=self.external
            frame=anchor+(max(0,frame-origin) if playing else 0)
        bpm,n,d,_,_=self.musical(frame)
        loop=bool(data.get('vst_loop_enabled',False));start=self._map.position(float(data.get('vst_loop_start_ms',0)))[3];end=self._map.position(float(data.get('vst_loop_end_ms',0)))[3]
        if not loop:start=end=0.0
        return (bpm,n,d,max(0,int(frame)),self.rate,playing,loop,start,end)

    def apply(self,plugin,frame):
        if not self.data.get('vst_host_sync',True):return False
        method=getattr(plugin,'_mta_set_transport',None)
        if method is None:return False
        context=self.context(frame);method(*context)
        musical=getattr(plugin,'_mta_set_musical_position',None)
        if musical is not None:
            _,_,_,ppq,bar=self.musical(context[3]);musical(ppq,bar)
        elif self.data.get('metronome_mode','fixed')!='fixed':raise RuntimeError('Update the compiled VST host for tempo maps')
        return True

    def musical(self,frame):
        from .vst3_tempo_map import TempoMap
        if self._map_data is not self.data:self._map=TempoMap(self.data);self._map_data=self.data
        return self._map.position(frame*1000/self.rate)

    def segments(self,frame,count):
        self.musical(frame)
        if self.external:
            anchor,origin,playing=self.external
            if not playing:return iter([(frame,frame+count)])
            effective=anchor+max(0,frame-origin)
            boundaries=[frame+(b-effective) for b in self._map.boundaries(effective,count,self.rate)]
        else:boundaries=self._map.boundaries(frame,count,self.rate)
        return zip(boundaries,boundaries[1:])

    def override(self,sample,playing,stream_frame):
        if type(sample) not in (int,float) or not math.isfinite(sample) or sample<0 or sample>86400*self.rate or type(playing) is not bool:raise ValueError('Invalid host transport position')
        self.external=(int(sample),int(stream_frame),playing)
