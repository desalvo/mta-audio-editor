"""MIDI 2 UMP validation, full-resolution VST3 events and optional native I/O.

The browser Web MIDI API exposes MIDI 1 only. UMP devices use libremidi in the
native app. Raw words are retained; VST3 receives translated note expressions.
"""
from collections import deque
import threading
import time

_LENGTHS=(1,1,1,2,2,4,1,1,2,2,2,3,3,4,4,4)


def packet(words):
    if not isinstance(words,list) or not words or any(type(w) is not int or not 0<=w<=0xffffffff for w in words) or len(words)!=_LENGTHS[words[0]>>28]:raise ValueError('Invalid UMP packet word count or value')
    return list(words)


def vst_message(words):
    words=packet(words);kind=words[0]>>28
    if kind==2:
        status=(words[0]>>16)&255;data=[status,(words[0]>>8)&127]
        if status&0xf0 not in (0xc0,0xd0):data.append(words[0]&127)
        from .midi_devices import validate_messages
        return bytes(validate_messages([data])[0])
    if kind!=4:raise ValueError('This UMP message type has no VST3 note-expression mapping')
    status=(words[0]>>20)&15
    if status not in (0,1,6,8,9,10,11,13,14):
        raise ValueError('This MIDI 2 controller is not supported by the VST3 event mapping; raw UMP remains exportable')
    # Private in-process bridge to our checked JUCE event-list extension. Data
    # bytes are 7-bit clean and retain every bit of the original 32-bit words.
    return bytes([0xf0,0x7d,ord('M'),ord('T'),ord('A'),2]+[(w>>(7*i))&127 for w in words for i in range(5)]+[0xf7])


def mpe_setup(zone,members,bend):
    if zone=='off':return []
    channel=0 if zone=='lower' else 15
    data=[[0xb0|channel,101,0],[0xb0|channel,100,6],[0xb0|channel,6,members],[0xb0|channel,101,127],[0xb0|channel,100,127]]
    for ch in (range(1,members+1) if zone=='lower' else range(15-members,15)):
        data.extend([[0xb0|ch,101,0],[0xb0|ch,100,0],[0xb0|ch,6,bend],[0xb0|ch,38,0],[0xb0|ch,101,127],[0xb0|ch,100,127]])
    return data


def apis():
    import pylibremidi as lm
    return [a for a in lm.available_ump_apis() if 'DUMMY' not in str(a)]


def identity(api,direction,port):
    import hashlib,json
    value=[str(getattr(port,k,'')) for k in ('client','port','manufacturer','device_name','port_name','display_name')]
    return str(api)+'|'+direction+'|'+hashlib.sha256(json.dumps(value).encode()).hexdigest()[:32]


def ports():
    try:
        import pylibremidi as lm
        rows=[]
        for api in apis():
            observer=lm.Observer(lm.ObserverConfiguration(),api)
            for direction,values in [('input',observer.get_input_ports()),('output',observer.get_output_ports())]:
                rows.extend({'id':identity(api,direction,p),'name':p.display_name,'direction':direction,'api':str(api)} for i,p in enumerate(values))
        return {'available':bool(apis()),'ports':rows,'backend':'libremidi-ump','native_ump':True}
    except (ImportError,RuntimeError,OSError) as exc:return {'available':False,'ports':[],'native_ump':False,'error':str(exc)}


class Device:
    def __init__(self,identity,direction):
        import pylibremidi as lm
        if not isinstance(identity,str) or len(identity)>512:raise ValueError('Invalid UMP device')
        api_name,kind,index=identity.split('|')
        if kind!=direction:raise ValueError('Wrong UMP device direction')
        api=next((a for a in apis() if str(a)==api_name),None)
        if api is None:raise ValueError('Native UMP backend is unavailable')
        self.lock=threading.Lock();self.events=deque(maxlen=4096);self.dropped=0
        self.observer=lm.Observer(lm.ObserverConfiguration(),api)
        values=self.observer.get_input_ports() if direction=='input' else self.observer.get_output_ports()
        matches=[p for p in values if globals()['identity'](api,direction,p)==identity]
        if len(matches)!=1:raise ValueError('UMP device disconnected or ambiguous')
        if direction=='input':
            config=lm.UmpInputConfiguration();config.on_message=self.receive
            self.device=lm.MidiIn(config,api)
        else:self.device=lm.MidiOut(lm.OutputConfiguration(),api)
        error=self.device.open_port(matches[0])
        if error:raise RuntimeError(str(error))

    def receive(self,value):
        data=list(value.data);words=packet(data[:_LENGTHS[data[0]>>28]])
        with self.lock:
            if len(self.events)==self.events.maxlen:self.dropped+=1
            self.events.append({'words':words,'time_ms':time.monotonic()*1000})

    def read(self):
        self.device.poll()
        with self.lock:result=list(self.events);self.events.clear()
        return {'events':result,'dropped':self.dropped,'now_ms':time.monotonic()*1000}

    def send(self,words):
        result=self.device.send_ump(packet(words))
        if result:raise RuntimeError(str(result))

    def close(self):self.device.close_port()


_LOCK=threading.RLock();_INPUT=None;_OUTPUTS={}


def input_start(identity):
    global _INPUT
    with _LOCK:
        if _INPUT:_INPUT.close()
        _INPUT=None;_INPUT=Device(identity,'input');return {'ok':True}


def input_read():
    with _LOCK:
        if not _INPUT:raise ValueError('No UMP input is open')
        return _INPUT.read()


def output_send(identity,words):
    with _LOCK:
        if identity not in _OUTPUTS:
            if len(_OUTPUTS)>=4:raise ValueError('At most four UMP outputs can be open')
            _OUTPUTS[identity]=Output(identity)
        _OUTPUTS[identity].send({'ump':words})
    return {'ok':True}


def close():
    global _INPUT
    with _LOCK:
        if _INPUT:_INPUT.close();_INPUT=None
        for out in _OUTPUTS.values():out.close()
        _OUTPUTS.clear()
    return {'ok':True}


import atexit
atexit.register(close)


def from_midi(data,group=0):
    if data[0]==0xf0:
        payload=data[1:-1];parts=[payload[i:i+6] for i in range(0,len(payload),6)] or [[]];result=[]
        for i,part in enumerate(parts):
            status=0 if len(parts)==1 else 1 if i==0 else 3 if i==len(parts)-1 else 2
            raw=[0x30|group,(status<<4)|len(part),*part,*([0]*(6-len(part)))];result.append([int.from_bytes(bytes(raw[:4]),'big'),int.from_bytes(bytes(raw[4:]),'big')])
        return result
    if data[0]>=0xf0:
        values=[0x10|group,*data,*([0]*(3-len(data)))];return [[int.from_bytes(bytes(values),'big')]]
    return [[(2<<28)|(group<<24)|(data[0]<<16)|(data[1]<<8)|(data[2] if len(data)>2 else 0)]]


def timeline_events(track,*,timeline=True):
    raw=[(e.time_ms,e.words) for e in track.midi_ump]
    if not timeline:return sorted(raw)
    from .audio_engine import ensure_clips
    ensure_clips(track);result=[]
    for clip in track.clips:
        offset=clip.timeline_start_ms+track.delay_ms-clip.source_start_ms
        result.extend((clip.timeline_start_ms+track.delay_ms,w) for w in chase(raw,clip.source_start_ms))
        result.extend((at+offset,w) for at,w in raw if clip.source_start_ms<=at<clip.source_end_ms)
        # Explicit note-off at each clip boundary; no voice may leak into a gap.
        for words in chase(raw,clip.source_end_ms):
            if words[0]>>28==4 and (words[0]>>20)&15==9:
                result.append((clip.timeline_start_ms+track.delay_ms+clip.duration_ms,[(words[0]&~(15<<20))|(8<<20),0]))
    return sorted(result,key=lambda e:e[0])


def chase(events,at):
    held={};controls={};expressions={}
    for time_ms,words in sorted(events,key=lambda e:e[0]):
        if time_ms>=at:break
        if words[0]>>28!=4:continue
        w=words[0];status=(w>>20)&15;channel=(((w>>24)&15)<<4)|((w>>16)&15);pitch=(w>>8)&127;key=(channel,pitch)
        if status==9:held[key]=words
        elif status==8:held.pop(key,None);expressions.pop(key,None)
        elif status in (11,13,14):controls[(channel,status,pitch if status==11 else 0)]=words
        elif status in (0,1,6,10):expressions.setdefault(key,{})[(status,w&127)]=words
    return [*controls.values(),*held.values(),*[w for key,values in expressions.items() if key in held for w in values.values()]]


class Output:
    def __init__(self,name):self.device=Device(name,'output')
    def send(self,data):
        if isinstance(data,dict):self.device.send(data['ump'])
        else:
            for words in from_midi(data):self.device.send(words)
    def panic(self,channels=range(16)):
        for ch in channels:
            for cc in (64,120,123):self.send([0xb0|ch,cc,0])
    def close(self):
        try:self.panic()
        finally:self.device.close()
