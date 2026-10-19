"""Persistent block graph. Runs only in the isolated live worker, never WebView/callback.

Pedalboard owns the native VST3 instances. PyAV owns ordered FFmpeg filters.
Each route pulls enough lookahead to compensate buffered plugin/filter output
before summing, rather than delaying the other tracks by a guessed latency.
"""
from collections import deque
from fractions import Fraction
import base64
import math
import numpy as np
import soundfile as sf
from .vst3_host import validate_plugin_path,apply_parameters
from .plugins import plugin_filter
from .cpp_audio import runtime

BLOCK=512
MAX_LOOKAHEAD=96000*10


class Filter:
    def __init__(self,expression,rate,channels):
        import av
        self.av=av;self.rate=rate;self.channels=channels;self.pts=0
        self.graph=av.filter.Graph();self.graph.threads=1
        node=self.graph.add_abuffer(sample_rate=rate,format='fltp',layout='mono' if channels==1 else 'stereo',time_base=Fraction(1,rate))
        for part in expression.split(','):
            name,_,args=part.partition('=');next_node=self.graph.add(name,args or None);node.link_to(next_node);node=next_node
        out=self.graph.add('aformat','sample_fmts=fltp:sample_rates='+str(rate));node.link_to(out)
        sink=self.graph.add('abuffersink');out.link_to(sink);self.graph.configure()

    def process(self,data):
        frame=self.av.AudioFrame.from_ndarray(np.ascontiguousarray(data.T),format='fltp',layout='mono' if data.shape[1]==1 else 'stereo')
        frame.sample_rate=self.rate;frame.time_base=Fraction(1,self.rate);frame.pts=self.pts;self.pts+=len(data);self.graph.push(frame)
        return self.drain()

    def drain(self):
        out=[]
        while True:
            try:f=self.graph.pull()
            except (self.av.error.BlockingIOError,self.av.error.EOFError):break
            out.append(np.ascontiguousarray(f.to_ndarray().T,dtype=np.float32))
        return out

    def flush(self):self.graph.push(None);return self.drain()


class Vst:
    def __init__(self,item,rate,*,instrument=False,host=None,start_frame=0,sidechain=None):
        self.sidechain=sidechain
        from .vst3_transport import HostClock
        self.host=host or HostClock(rate=rate);self.position=start_frame
        from pedalboard import load_plugin
        self.item=item;self.rate=rate;self.plugin=load_plugin(str(validate_plugin_path(str(item.params.get('path','')))))
        if bool(self.plugin.is_instrument)!=instrument:raise ValueError('Select a VST3 instrument for MIDI tracks, or an audio effect for inserts')
        apply_parameters(self.plugin,{k:v for k,v in item.params.items() if k!='path'})

    def process(self,data):
        parts=[]
        if data.shape[1]==1:data=np.repeat(data,2,axis=1)*np.float32(2**-.5)
        for start,end in self.host.segments(self.position,len(data)):
            self.host.apply(self.plugin,start)
            chunk=np.ascontiguousarray(data[start-self.position:end-self.position].T)
            if self.sidechain:
                aux=self.sidechain.read(end-start)
                if aux.shape[1]==1:aux=np.repeat(aux,2,axis=1)*np.float32(2**-.5)
                aux=np.ascontiguousarray(aux.T)*np.float32(10**(self.item.sidechain_gain_db/20))
                method=getattr(self.plugin,'_mta_process_sidechain',None)
                if method is None:raise RuntimeError('Update the compiled VST host for external sidechains')
                out=method(chunk,aux,self.rate,self.item.sidechain_bus)
            else:out=self.plugin.process(chunk,self.rate,buffer_size=BLOCK,reset=False)
            if out.ndim!=2 or out.shape[0] not in (1,2):raise RuntimeError('VST3 returned an unsupported channel layout')
            if out.shape[0]==1:out=np.repeat(out,2,axis=0)*np.float32(2**-.5)
            if out.shape[-1]:parts.append(np.ascontiguousarray(out.T,dtype=np.float32))
        self.position+=len(data);return parts

    def values(self):
        state=base64.b64encode(self.plugin.raw_state).decode()
        if len(state)>12*1024*1024:raise ValueError('VST3 state too large')
        return {'path':str(self.item.params['path']),'__mta_state_b64':state,**{k:float(v.raw_value) for k,v in self.plugin.parameters.items()}}


def pipeline(source,nodes):
    for node in nodes:
        def stage(upstream,node):
            silent_input=0
            for data in upstream:
                parts=node.process(data);silent_input+=len(data)
                for out in parts:
                    if len(out):silent_input=0;yield out
                if silent_input>MAX_LOOKAHEAD:raise RuntimeError("Live plugin buffered more than the supported lookahead")
            if isinstance(node,Filter):yield from node.flush()
            elif silent_input>BLOCK:raise RuntimeError('VST3 stopped producing audio before the stream completed')
        source=stage(source,node)
    return source


class Pull:
    def __init__(self,source,channels=2):self.source=iter(source);self.queue=deque();self.channels=channels;self.done=False

    def read(self,n):
        chunks=[];remaining=n;pulled=0
        while remaining:
            if not self.queue and not self.done:
                try:
                    part=next(self.source);pulled+=len(part)
                    if pulled>MAX_LOOKAHEAD:raise RuntimeError('Live processing exceeded bounded lookahead')
                    if len(part):self.queue.append(part);self.channels=part.shape[1]
                except StopIteration:self.done=True
            if not self.queue:break
            part=self.queue.popleft();k=min(remaining,len(part));chunks.append(part[:k]);remaining-=k
            if k<len(part):self.queue.appendleft(part[k:])
        out=np.zeros((n,self.channels),dtype=np.float32)
        if chunks:out[:n-remaining]=np.concatenate(chunks)
        if not np.isfinite(out).all():raise RuntimeError('Live plugin returned non-finite audio')
        return out


class SharedSource:
    def __init__(self,source):self.source=iter(source);self.cache=deque();self.base=0;self.cursors=[]
    def subscribe(self):
        index=len(self.cursors);self.cursors.append(0)
        def iterator():
            while True:
                at=self.cursors[index]
                if at-self.base>=len(self.cache):
                    try:self.cache.append(next(self.source))
                    except StopIteration:return
                if sum(len(x) for x in self.cache)>MAX_LOOKAHEAD:raise RuntimeError('Sidechain lookahead exceeds the bounded cache')
                data=self.cache[at-self.base].copy();self.cursors[index]+=1
                while self.cache and self.base<min(self.cursors):self.cache.popleft();self.base+=1
                yield data
        return iterator()


class Graph:
    def __init__(self,project,paths,start_frame=0,*,tail_seconds=2,reuse=None,raw_sources=()):
        from .audio_engine import project_duration_ms,project_time_pitch_filter
        if not 1<=len(project.tracks)<=64:raise ValueError('Live mixing supports 1–64 tracks')
        self.reuse=reuse or {};self.project=project;self.rate=int(project.sample_rate);self.core=runtime();self.readers=[];self.plugins={};self.offset=0;self.meters={};self._meter_tracks={};self.raw_sources=set(raw_sources)
        from .vst3_transport import HostClock
        self.host=HostClock(project,self.rate)
        self.input_total=round(project_duration_ms(project)*self.rate/1000)
        self.ratio=max(.25,min(4,float(project.bpm)/float(project.base_bpm or project.bpm)))
        self.total=math.ceil((self.input_total+round(tail_seconds*self.rate))/self.ratio)
        self.start_frame=start_frame;self.source_start=round(start_frame*self.ratio);self.route_pulls=[];self.filters=[];self.sources={};self.sidechains=[]
        try:
            for t,path in zip(project.tracks,paths,strict=True):
                if t.kind=='midi':
                    from .midi_render import Instrument
                    node=Instrument(t,self.rate,self.source_start,reuse=self.reuse.get((t.id,'instrument')),host=self.host)
                    if node.plugin is not None:self.plugins[(t.id,'instrument')]=node
                    self.sources[t.id]=SharedSource(self.midi_source(node,t))
                    nodes=self.nodes(t.inserts,t.id,2)
                    self.route_pulls.append(Pull(pipeline(self.sources[t.id].subscribe(),nodes),2))
                    continue
                reader=sf.SoundFile(str(path));self.readers.append(reader);reader.seek(min(reader.frames,self.source_start))
                if reader.samplerate!=self.rate or reader.channels not in (1,2):raise ValueError('Live source format mismatch')
                self.sources[t.id]=SharedSource(self.raw_source(reader,t) if t.id in self.raw_sources else self.source(reader,t))
                nodes=self.nodes(t.inserts,t.id,reader.channels)
                self.route_pulls.append(Pull(pipeline(self.sources[t.id].subscribe(),nodes),2 if any(isinstance(x,Vst) for x in nodes) else reader.channels))
            master=self.nodes(project.master_inserts,'master',2)
            for node,item in self.sidechains:
                if item.sidechain_track_id not in self.sources:raise ValueError('Sidechain source track not found')
                node.sidechain=Pull(self.sources[item.sidechain_track_id].subscribe())
            tempo=project_time_pitch_filter(project)
            if tempo!='anull':master.append(Filter(tempo,self.rate,2))
            self.master_pull=Pull(pipeline(self.mix(False),master[:-1] if tempo!='anull' else master))
            self.bypass_pull=Pull(self.mix(True));self.output=Pull(pipeline(self.post_master(),[master[-1]] if tempo!='anull' else []));self.position=start_frame
        except BaseException:self.close();raise

    def nodes(self,items,route,channels):
        nodes=[]
        for item in items:
            if not item.enabled:continue
            if item.plugin=='vst3':
                node=self.reuse.get((route,item.id))
                if node and node.item.params.get('path')==item.params.get('path'):
                    node.plugin.reset()
                    apply_parameters(node.plugin,{k:v for k,v in item.params.items() if k!='path' and v!=node.item.params.get(k)})
                    node.item=item
                    node.host=self.host;node.position=self.source_start
                else:node=Vst(item,self.rate,host=self.host,start_frame=self.source_start)
                node.sidechain=None
                if item.sidechain_track_id:self.sidechains.append((node,item))
                self.plugins[(route,item.id)]=node;channels=2
            else:
                expr=plugin_filter(item)
                if not expr:continue
                node=Filter(expr,self.rate,channels)
                if item.plugin=='stereo_imager':channels=2
            nodes.append(node)
        return nodes

    def source(self,reader,track):
        total=max(self.input_total,reader.frames)+self.rate*12
        for at in range(self.source_start,total,BLOCK):
            data=np.zeros((min(BLOCK,total-at),reader.channels),dtype=np.float32)
            part=reader.read(len(data),dtype='float32',always_2d=True);data[:len(part)]=part
            self.core.gain(data,10**(float(track.gain_db)/20));yield data

    def raw_source(self,reader,track):
        # Read only intersecting source frames, with bounded block memory. Clip
        # placement and negative delay are applied here, before gain and inserts.
        clips=sorted(track.clips,key=lambda c:c.timeline_start_ms)
        spans=[]
        for clip in clips:
            start=round((clip.timeline_start_ms+track.delay_ms)*self.rate/1000)
            source=round(clip.source_start_ms*self.rate/1000)
            length=round((clip.source_end_ms-clip.source_start_ms)*self.rate/1000)
            spans.append((start,start+length,source))
        index=0
        for at in range(self.source_start,self.input_total+self.rate*12,BLOCK):
            data=np.zeros((BLOCK,reader.channels),dtype=np.float32)
            while index<len(spans) and spans[index][1]<=at:index+=1
            for n in range(index,len(spans)):
                start,end,source=spans[n]
                if start>=at+BLOCK:break
                left=max(at,start);right=min(at+BLOCK,end)
                if right<=left:continue
                offset=source+left-start
                if offset>=reader.frames:continue
                # Preserve the decoder cursor for adjacent blocks (especially MP3/FLAC).
                if reader.tell()!=max(0,offset):reader.seek(max(0,offset))
                part=reader.read(min(right-left,reader.frames-offset),dtype='float32',always_2d=True)
                data[left-at:left-at+len(part)]+=part
            self.core.gain(data,10**(float(track.gain_db)/20));yield data

    def midi_source(self,node,track):
        for at in range(self.source_start,self.input_total+self.rate*12,BLOCK):
            data=node.read(BLOCK)
            self.core.gain(data,10**(float(track.gain_db)/20));yield data

    def mix(self,bypass_mode):
        for at in range(self.source_start,self.input_total+self.rate*12,BLOCK):
            n=BLOCK;arrays=[];normal=[];bypass=[];solo=any(t.solo for t in self.project.tracks)
            for t,pull in zip(self.project.tracks,self.route_pulls):
                data=pull.read(n) if bool(t.master_bypass)==bypass_mode else np.zeros((n,2),dtype=np.float32)
                if data.shape[1]==1:data=np.ascontiguousarray(np.repeat(data,2,axis=1)*np.float32(2**-.5))
                arrays.append(data);enabled=not (t.mute or (solo and not t.solo));normal.append(enabled and not t.master_bypass);bypass.append(enabled and t.master_bypass)
                if bool(t.master_bypass)==bypass_mode:
                    gains=np.array([1-max(0,t.pan),1+min(0,t.pan)])*(10**(t.volume_db/20) if enabled else 0)
                    measured=data*gains
                    energy,peak,count=self._meter_tracks.get(t.id,(np.zeros(2),np.zeros(2),0))
                    self._meter_tracks[t.id]=(energy+np.sum(measured*measured,axis=0),np.maximum(peak,np.max(np.abs(measured),axis=0)),count+n)
            out=self.core.mix(arrays,[10**(t.volume_db/20) for t in self.project.tracks],[t.pan for t in self.project.tracks],bypass if bypass_mode else normal)
            # Master fader/envelope belong after master inserts. Applied in read()
            # to the compensated project clock, after all inserted processing.
            self.offset=at+n;yield out

    def post_master(self):
        for at in range(self.source_start,self.input_total+self.rate*12,BLOCK):
            out=self.master_pull.read(BLOCK);p=self.project
            bounded=p.master_fade_enabled or p.timeline_end_ms is not None
            count=min(BLOCK,max(0,self.input_total-at)) if bounded else BLOCK
            if bounded:
                if count:self.core.envelope(out[:count],at,max(1,self.input_total),10**(p.master_volume_db/20),round(p.master_fade_in_ms*self.rate/1000) if p.master_fade_enabled else 0,round(p.master_fade_out_ms*self.rate/1000) if p.master_fade_enabled else 0)
                out[count:]=0
            else:self.core.gain(out,10**(p.master_volume_db/20))
            out+=self.bypass_pull.read(BLOCK);yield out

    def read(self,n=BLOCK):
        n=min(n,max(0,self.total-self.position))
        if not n:return np.empty((0,2),dtype=np.float32)
        self._meter_tracks={}
        out=self.output.read(n);self.position+=n
        def values(energy,peak,count):return [*np.sqrt(energy/max(1,count)).tolist(),*peak.tolist()]
        tracks=[]
        for track in self.project.tracks:
            stats=self._meter_tracks.get(track.id)
            tracks.append(values(*stats) if stats else [0.,0.,0.,0.])
        self.meters={'tracks':tracks,'master':values(np.sum(out.astype(np.float64)**2,axis=0),np.max(np.abs(out),axis=0),n)}
        self.meters={key:[[round(min(16.,v),6) for v in row] for row in val] if key=='tracks' else [round(min(16.,v),6) for v in val] for key,val in self.meters.items()}
        return out

    def update(self,project):
        from .vst3_transport import settings
        if (project.sample_rate,project.bpm,project.base_bpm,project.pitch_semitones)!=(self.project.sample_rate,self.project.bpm,self.project.base_bpm,self.project.pitch_semitones):return False
        self.host.data=settings(project)
        # Topology/clip changes require a new graph. Parameter-only edits preserve
        # plugin delay lines and never rebuild the dry project or reload a plugin.
        def shape(p):return [(t.id,t.filename,[i.model_dump(exclude={'params'}) for i in t.inserts]) for t in p.tracks]+[('master','',[i.model_dump(exclude={'params'}) for i in p.master_inserts])]
        if shape(project)!=shape(self.project):return False
        for old,new in zip(self.project.tracks,project.tracks):
            if (old.kind,old.midi_route,old.midi_notes,old.midi_controls,old.clips,old.delay_ms)!=(new.kind,new.midi_route,new.midi_notes,new.midi_controls,new.clips,new.delay_ms):return False
            if old.instrument!=new.instrument:
                if not old.instrument or not new.instrument or old.instrument.params.get('path')!=new.instrument.params.get('path'):return False
                node=self.plugins.get((old.id,'instrument'))
                if node:
                    apply_parameters(node.plugin,{k:v for k,v in new.instrument.params.items() if k!='path' and v!=old.instrument.params.get(k)})
                    node.item=new.instrument
        for t in [*project.tracks,None]:
            route=t.id if t else 'master';items=t.inserts if t else project.master_inserts
            prior=next((x for x in self.project.tracks if x.id==route),None)
            old_items=prior.inserts if prior else self.project.master_inserts
            for item,old in zip(items,old_items):
                if item.params==old.params:continue
                if item.plugin!='vst3':return False
                if item.params.get('path')!=old.params.get('path'):return False
                node=self.plugins.get((route,item.id))
                if node:
                    apply_parameters(node.plugin,{k:v for k,v in item.params.items() if k!='path' and v!=old.params.get(k)})
                    node.item=item
        # Source generators keep track references: update in place, not replace.
        for t,new in zip(self.project.tracks,project.tracks):
            for key in ('gain_db','volume_db','pan','mute','solo','inserts','instrument'):setattr(t,key,getattr(new,key))
        for key in ('master_volume_db','master_fade_enabled','master_fade_in_ms','master_fade_out_ms','master_inserts'):setattr(self.project,key,getattr(project,key))
        return True

    def close(self):
        for r in self.readers:r.close()
        self.readers.clear()

    def set_playing(self,value):
        self.host.playing=bool(value)
        for node in self.plugins.values():self.host.apply(node.plugin,node.clock.position if hasattr(node,'clock') else node.position)

    def live_ump(self,tid,messages):
        node=self.plugins.get((tid,'instrument'))
        if node is None:raise ValueError('Live instrument not found')
        node.enqueue_ump(messages)

    def live_midi(self,track_id,messages):
        node=self.plugins.get((track_id,'instrument'))
        if node is None:raise ValueError('Monitoring instrument unavailable')
        node.enqueue(messages)

    def panic(self):
        for node in self.plugins.values():
            if hasattr(node,'enqueue'):node.enqueue([[0xB0|channel,control,0] for channel in range(16) for control in (64,120,123)])

    def live_parameters(self,params):
        if not isinstance(params,dict) or len(params)>64 or 'path' in params or '__mta_state_b64' in params:raise ValueError('Invalid live MIDI parameters')
        node=self.plugins.get((self.project.tracks[0].id,'instrument'))
        if node is None:raise ValueError('Monitoring instrument unavailable')
        apply_parameters(node.plugin,params)
