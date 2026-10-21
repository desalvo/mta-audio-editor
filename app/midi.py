"""Bounded SMF I/O and deterministic, sample-clock MIDI for native/server VSTi.

Project notes use source milliseconds, preserving imported tempo maps without
changing existing audio. Clip edits and track delay map those events to transport.
"""
import bisect


MAX_EVENTS = 150000
MAX_MS = 86400000


def read_smf(data,*,extended=False):
    from .midi_smf import read_parts
    parts=read_parts(data)
    notes=[note for part in parts for note in part['notes']]
    controls=[event for part in parts for event in part['controls']]
    sysex=[event for part in parts for event in part['sysex']]
    result=(notes,controls,max(part['duration_ms'] for part in parts))
    return (*result,sysex) if extended else result


def events(track, *, timeline=True,ump=True):
    raw=[]
    channels={};allocated=[]
    from .midi_ump import mpe_setup,vst_message
    raw.extend((0,msg) for msg in mpe_setup(track.mpe_zone,track.mpe_members,track.mpe_pitch_bend))
    members=list(range(1,track.mpe_members+1) if track.mpe_zone=='lower' else range(15-track.mpe_members,15))
    for n in sorted(track.midi_notes,key=lambda n:n.start_ms):
        ch=n.channel
        if track.mpe_zone!='off' and ch in (0,15):
            allocated=[item for item in allocated if item[0]>n.start_ms]
            ch=next((c for c in members if c not in {v for _,v in allocated}),None)
            if ch is None:raise ValueError('MPE polyphony exceeds the configured member channels')
            allocated.append((n.start_ms+n.duration_ms,ch))
        channels[n.id]=ch
    for n in track.midi_notes:
        if n.start_ms+n.duration_ms>MAX_MS:raise ValueError('MIDI: note exceeds 24 hours')
        raw.extend([(n.start_ms,[0x90|channels[n.id],n.pitch,n.velocity]),(n.start_ms+n.duration_ms,[0x80|channels[n.id],n.pitch,0])])
    raw.extend((c.time_ms,list(c.data)) for c in track.midi_controls)
    if ump and track.midi_route in ('instrument','both') and not timeline:raw.extend((c.time_ms,list(vst_message(c.words))) for c in track.midi_ump)
    if sum(len(e.data) for e in track.midi_sysex)>8*1024**2:raise ValueError('MIDI SysEx exceeds project size limit')
    raw.extend((e.time_ms,list(e.data)) for e in track.midi_sysex)
    if len(raw)>MAX_EVENTS:raise ValueError('MIDI: event limit exceeded')
    if not timeline:return sorted(raw,key=lambda x:(x[0],0 if x[1][0]&0xF0==0x80 else 1))
    from .audio_engine import ensure_clips
    ensure_clips(track);result=[]
    for clip in track.clips:
        start=clip.source_start_ms;end=clip.source_end_ms
        # Start each clip with restored controllers and held/sustained notes.
        restore=chase(raw,start)
        offset=clip.timeline_start_ms+track.delay_ms
        result.extend((offset,msg) for msg in restore)
        result.extend((at-start+offset,msg) for at,msg in raw if start<=at<end)
        # Clip boundaries explicitly release sustain and voices.
        channels={msg[0]&15 for _,msg in raw if msg[0]<0xF0}
        for channel in sorted(channels):
            result.extend([(offset+end-start,[0xB0|channel,64,0]),(offset+end-start,[0xB0|channel,123,0])])
        if len(result)>MAX_EVENTS:raise ValueError('MIDI: expanded clip event limit exceeded')
    if ump and track.midi_route in ('instrument','both'):
        from .midi_ump import timeline_events
        result.extend((at,list(vst_message(words))) for at,words in timeline_events(track))
    return sorted(result,key=lambda x:(x[0],0 if x[1][0]&0xF0==0x80 else 1))


def chase(events,at):
    """Restore channel state and notes sounding at seek; never replay old audio."""
    controls={};held={};sustained={};pedal={}
    for time,msg in sorted(events,key=lambda x:x[0]):
        if time>=at:break
        if msg[0]>=0xF0:continue  # SysEx is never replayed when seeking.
        kind=msg[0]&0xF0;ch=msg[0]&15
        if kind==0x90 and msg[2]:held[(ch,msg[1])]=list(msg);sustained.pop((ch,msg[1]),None)
        elif kind==0x80 or (kind==0x90 and not msg[2]):
            note=held.pop((ch,msg[1]),None)
            if pedal.get(ch) and note:sustained[(ch,msg[1])]=note
        else:
            key=(ch,kind,msg[1] if kind in (0xB0,0xA0) else 0);controls[key]=list(msg)
            if kind==0xB0:
                if msg[1]==64:
                    pedal[ch]=msg[2]>=64
                    if not pedal[ch]:sustained={k:v for k,v in sustained.items() if k[0]!=ch}
                elif msg[1] in (120,123):
                    held={k:v for k,v in held.items() if k[0]!=ch};sustained={k:v for k,v in sustained.items() if k[0]!=ch}
    # Bank selection before program change, then other controllers/pitch.
    out=sorted(controls.values(),key=lambda m:(0 if m[0]&0xF0==0xB0 and m[1] in (0,32) else 1 if m[0]&0xF0==0xC0 else 2))
    out+=list(held.values())
    for (ch,pitch),msg in sustained.items():out.extend([msg,[0x80|ch,pitch,0]])
    return out


class Clock:
    def __init__(self,track,rate,start_frame=0,*,timeline=True):
        self.rate=rate;self.position=start_frame
        self.events=[(round(ms*rate/1000),msg) for ms,msg in events(track,timeline=timeline)]
        self.times=[at for at,_ in self.events]
        self.index=bisect.bisect_left(self.times,start_frame)
        self.restore=chase(self.events,start_frame)
        from .midi_ump import timeline_events,chase as ump_chase,vst_message
        self.restore.extend(list(vst_message(words)) for words in ump_chase(timeline_events(track,timeline=timeline),start_frame*1000/rate))

    def read(self,count):
        end=self.position+count;out=[(bytes(msg),0.0) for msg in self.restore];self.restore=[]
        while self.index<len(self.events) and self.events[self.index][0]<end:
            at,msg=self.events[self.index];self.index+=1
            out.append((bytes(msg),max(0,at-self.position)/self.rate))
        self.position=end;return out


def write_smf(track,bpm=120,time_signature='4/4'):
    from .midi_smf import write_parts
    return write_parts([track],file_type=0,bpm=bpm,time_signature=time_signature)
