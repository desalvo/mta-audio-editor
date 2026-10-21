"""Native MIDI I/O. Callbacks only enqueue; plugin DSP never runs in a callback."""
import bisect
from collections import deque
import math
import logging
import threading
import time


def validate_messages(messages,*,sysex=False):
    if not isinstance(messages,list) or len(messages)>512:raise ValueError('Expected at most 512 MIDI messages')
    result=[];size=0
    for msg in messages:
        if sysex and isinstance(msg,list) and 2<=len(msg)<=65536 and msg[0]==0xf0 and msg[-1]==0xf7 and all(type(v) is int and 0<=v<=127 for v in msg[1:-1]):
            size+=len(msg)
            if size>131072:raise ValueError('MIDI SysEx batch too large')
            result.append(list(msg));continue
        if not isinstance(msg,list) or len(msg) not in (2,3) or any(type(v) is not int for v in msg):raise ValueError('Invalid MIDI message')
        kind=msg[0]&0xF0
        if not 0x80<=msg[0]<=0xEF or len(msg)!=(2 if kind in (0xC0,0xD0) else 3) or any(not 0<=v<=127 for v in msg[1:]):raise ValueError('Only MIDI channel voice messages are accepted')
        result.append(list(msg))
    return result


def ports():
    import rtmidi
    inp=rtmidi.MidiIn();out=rtmidi.MidiOut()
    try:return {'inputs':inp.get_ports(),'outputs':out.get_ports(),'backend':'rtmidi','available':True}
    finally:inp.delete();out.delete()


def _open(device,name):
    names=device.get_ports()
    if not isinstance(name,str) or not name or len(name)>512 or names.count(name)!=1:raise ValueError('MIDI port is missing, ambiguous or disconnected')
    device.open_port(names.index(name),'MTA Audio Editor')


class Input:
    def __init__(self,name,*,sysex=False):
        import rtmidi
        self.sysex=sysex;self.port=rtmidi.MidiIn();self.name=name;self.lock=threading.Lock();self.pending=deque();self.captured=deque(maxlen=4096);self.dropped=0;self.pending_bytes=0;self.capture_bytes=0;self.closed=False
        try:_open(self.port,name);self.port.ignore_types(sysex=not sysex,timing=True,active_sense=True);self.port.set_callback(self._receive)
        except BaseException:self.close();raise

    def _receive(self,event,_):
        try:messages=validate_messages([list(event[0])],sysex=self.sysex)
        except ValueError:return
        stamp=time.monotonic()*1000
        with self.lock:
            if self.closed:return
            if len(self.pending)>=2048 or self.pending_bytes+len(messages[0])>1024*1024:
                self.pending.clear();self.pending.extend([[0xB0|ch,120,0] for ch in range(16)]);self.pending_bytes=48;self.dropped+=1
            self.pending.extend(messages);self.pending_bytes+=len(messages[0])
            while self.captured and (len(self.captured)>=4096 or self.capture_bytes+len(messages[0])>1024*1024):
                self.capture_bytes-=len(self.captured.popleft()['data']);self.dropped+=1
            self.capture_bytes+=len(messages[0])
            self.captured.append({'data':messages[0],'time_ms':stamp})

    def drain(self):
        with self.lock:
            result=[];size=0
            while self.pending and len(result)<512 and size+len(self.pending[0])<=131072:
                msg=self.pending.popleft();result.append(msg);size+=len(msg)
            self.pending_bytes-=size;return result

    def capture(self):
        with self.lock:out=list(self.captured);self.captured.clear();self.capture_bytes=0
        return {'events':out,'now_ms':time.monotonic()*1000,'dropped':self.dropped,'connected':self.name in self.port.get_ports()}

    def close(self):
        if getattr(self,'closed',True):return
        self.closed=True
        try:self.port.cancel_callback();self.port.close_port()
        finally:self.port.delete()


class Output:
    def __init__(self,name):
        import rtmidi
        self.port=rtmidi.MidiOut();self.name=name;self.closed=False;self.checked=0
        try:_open(self.port,name)
        except BaseException:self.close();raise

    def send(self,data):
        if time.monotonic()-self.checked>.25:
            if self.name not in self.port.get_ports():raise ValueError('MIDI output disconnected')
            self.checked=time.monotonic()
        self.port.send_message(data)

    def panic(self,channels=range(16)):
        for ch in channels:
            for cc in (64,120,123):self.send([0xB0|ch,cc,0])

    def close(self):
        if self.closed:return
        self.closed=True
        try:
            try:self.panic()
            finally:self.port.close_port()
        finally:self.port.delete()


class SharedOutput:
    """One OS port per application, including drivers with exclusive opens."""
    pool={};lock=threading.RLock()
    def __init__(self,name):
        self.name=name;self.closed=False
        with self.lock:
            if name not in self.pool:self.pool[name]=[Output(name),0]
            self.pool[name][1]+=1
    def send(self,data):
        with self.lock:
            if self.closed:raise ValueError('MIDI output closed')
            self.pool[self.name][0].send(data)
    def panic(self,channels=range(16)):
        with self.lock:self.pool[self.name][0].panic(channels)
    def close(self):
        with self.lock:
            if self.closed:return
            self.closed=True;value=self.pool.get(self.name)
            if value:
                try:value[0].panic()
                finally:
                    value[1]-=1
                    if value[1]<=0:
                        self.pool.pop(self.name,None);value[0].close()


class Sequencer:
    """A worker-side 1 ms scheduler follows the actual C++ output device clock.

    No browser polling or producer-ahead frame count is used for native output.
    """
    def __init__(self,project,options,status):
        from .midi import events
        from .vst3_tempo_map import TempoMap
        from .vst3_transport import settings
        self.tempo_map=TempoMap(settings(project))
        self.project=project;self.status=status;self.stop_event=threading.Event();self.routes={};self.error='';self.thread=None
        self.ratio=max(.25,min(4,project.bpm/(project.base_bpm or project.bpm)))
        try:
            for track in project.tracks:
                if track.mute or (any(t.solo for t in project.tracks) and not track.solo):continue
                name=options.get('ump_outputs',{}).get(track.id) or options.get('outputs',{}).get(track.id)
                ump=bool(options.get('ump_outputs',{}).get(track.id))
                if track.kind!='midi' or track.midi_route not in ('hardware','both') or not name:continue
                route=self.routes.setdefault(name,{'events':[],'port':None,'clock':bool(options.get('clock',False)),'ump':ump})
                route['events'].extend((at,msg) for at,msg in events(track,ump=False) if msg[0]!=0xf0 or options.get('sysex'))
                if ump:
                    from .midi_ump import timeline_events
                    route['events'].extend((at,{'ump':words}) for at,words in timeline_events(track))
            for name,route in self.routes.items():
                from .midi_ump import Output as UmpOutput
                route['port']=UmpOutput(name) if route['ump'] else SharedOutput(name);route['events'].sort(key=lambda x:x[0]);route['times']=[x[0] for x in route['events']]
            if self.routes:
                self.thread=threading.Thread(target=self._run,name='mta-midi-output',daemon=True);self.thread.start()
        except BaseException:self.close();raise

    def _run(self):
        from .midi import chase
        previous=None;was=False;last=time.monotonic()
        try:
            while not self.stop_event.wait(.001):
                state=self.status();playing=bool(state.get('playing'));now=time.monotonic()
                position=float(state.get('position',0))*1000/float(state.get('sample_rate',self.project.sample_rate))*self.ratio
                jumped=previous is not None and abs(position-previous-(now-last)*1000*self.ratio*(1 if was else 0))>60
                if playing and (not was or jumped):
                    ppq=self.tempo_map.position(position)[3]
                    for route in self.routes.values():
                        route['port'].panic();route['index']=bisect.bisect_left(route['times'],position)
                        for msg in chase([(at,msg) for at,msg in route['events'] if isinstance(msg,list)],position):route['port'].send(msg)
                        if route['ump']:
                            from .midi_ump import chase as ump_chase
                            for words in ump_chase([(at,msg['ump']) for at,msg in route['events'] if isinstance(msg,dict)],position):route['port'].send({'ump':words})
                        route['tick']=math.ceil(max(0,ppq)*24)
                        if route['clock']:
                            if position<1:route['port'].send([0xFA])
                            else:
                                spp=min(16383,round(max(0,ppq)*4));route['port'].send([0xF2,spp&127,(spp>>7)&127]);route['port'].send([0xFB])
                if not playing and was:
                    for route in self.routes.values():
                        route['port'].panic()
                        if route['clock']:route['port'].send([0xFC])
                if playing:
                    ppq=self.tempo_map.position(position)[3]
                    for route in self.routes.values():
                        index=route.get('index',0)
                        while index<len(route['events']) and route['times'][index]<=position:
                            route['port'].send(route['events'][index][1]);index+=1
                        route['index']=index
                        if route['clock']:
                            due=max(0,ppq)*24
                            while route['tick']<=due:route['port'].send([0xF8]);route['tick']+=1
                previous=position;was=playing;last=now
        except Exception as exc:
            self.error=str(exc)
            for route in self.routes.values():
                try:route['port'].panic()
                except Exception:logging.getLogger(__name__).debug('MIDI cleanup failed',exc_info=True)

    def close(self):
        self.stop_event.set()
        if self.thread:self.thread.join(timeout=1)
        for route in self.routes.values():
            if route['port']:
                try:route['port'].close()
                except Exception:logging.getLogger(__name__).debug('MIDI cleanup failed',exc_info=True)
