"""Instrument voices in the shared graph, and isolated streaming offline render."""
import json
import os
from pathlib import Path
import subprocess
import tempfile

from .midi import Clock
from .vst3_live_graph import Vst, BLOCK


class Instrument(Vst):
    def __init__(self,track,rate,start_frame=0,*,timeline=True,reuse=None,host=None):
        from .vst3_transport import HostClock
        self.pending=[];self.rate=rate;self.host=host or HostClock(rate=rate)
        self.clock=Clock(track,rate,start_frame,timeline=timeline)
        if track.midi_route in ('hardware','none'):self.plugin=None;return
        if track.instrument and track.instrument.enabled and track.instrument.plugin=='gm_soundfont':
            from .gm_instruments import Synth
            self.item=track.instrument;self.plugin=Synth(track.instrument.params,rate);return
        if not track.instrument or not track.instrument.enabled or track.instrument.plugin!='vst3':
            raise ValueError('MIDI: select and enable a VST3 instrument before playback or export')
        if reuse and reuse.item.params.get('path')==track.instrument.params.get('path'):
            from .vst3_host import apply_parameters
            self.plugin=reuse.plugin;self.plugin.reset();self.item=track.instrument;self.rate=rate
            apply_parameters(self.plugin,{k:v for k,v in self.item.params.items() if k!='path' and v!=reuse.item.params.get(k)})
        else:super().__init__(track.instrument,rate,instrument=True,host=self.host,start_frame=start_frame)

    def values(self):
        if self.item.plugin=='gm_soundfont':return dict(self.plugin.params)
        return super().values()

    def set_parameters(self, values):
        if self.item.plugin=='gm_soundfont':self.plugin.configure(values)
        else:
            from .vst3_host import apply_parameters
            apply_parameters(self.plugin,values)

    def enqueue_ump(self,messages):
        from .midi_ump import vst_message
        if not isinstance(messages,list) or len(messages)>512:raise ValueError('UMP batch too large')
        converted=[list(vst_message(m)) for m in messages]
        if len(self.pending)+len(converted)>2048:raise ValueError('UMP input overflow')
        self.pending.extend(converted)

    def enqueue(self,messages):
        from .midi_devices import validate_messages
        messages=validate_messages(messages,sysex=True)
        if len(self.pending)+len(messages)>2048 or sum(map(len,self.pending))+sum(map(len,messages))>512*1024:
            self.pending=[[0xB0|ch,120,0] for ch in range(16)]
            raise ValueError('MIDI input overflow: voices stopped')
        self.pending.extend(messages)

    def read(self,count):
        import numpy as np
        if self.plugin is None:return np.zeros((count,2),np.float32)
        pieces=[]
        for start,end in self.host.segments(self.clock.position,count):
            size=end-start;self.host.apply(self.plugin,start)
            messages=self.clock.read(size)+[(bytes(msg),0.) for msg in self.pending];self.pending=[]
            result=self.plugin.process(messages,duration=size/self.rate,sample_rate=self.rate,num_channels=2,buffer_size=BLOCK,reset=False)
            if result.shape!=(2,size) or not np.isfinite(result).all():raise RuntimeError('MIDI instrument returned invalid audio')
            pieces.append(result.T)
        return np.ascontiguousarray(np.concatenate(pieces),dtype=np.float32)



def render_source(track,target,rate):
    """Never load third party code in the HTTP/GUI process, including previews."""
    from .vst3_host import worker_command,validate_plugin_path
    from .audio_engine import ensure_clips
    ensure_clips(track)
    duration=max(50,max((clip.timeline_start_ms+track.delay_ms+clip.duration_ms for clip in track.clips),default=0))
    if track.midi_route not in ('hardware','none'):
        if not track.instrument:raise ValueError('MIDI: select a VST3 instrument')
        if track.instrument.plugin=='gm_soundfont':
            from .gm_instruments import validate,bank_path
            bank_path(validate(track.instrument.params)['bank_id'])
        else:validate_plugin_path(str(track.instrument.params.get('path','')))
    with tempfile.TemporaryDirectory(prefix='mta-midi-render-') as directory:
        config=Path(directory)/'midi.json'
        from .vst3_transport import render_settings
        config.write_text(json.dumps({'track':track.model_dump(mode='json'),'target':str(target),'rate':rate,'duration_ms':duration,'transport':render_settings()}),encoding='utf-8')
        result=subprocess.run(worker_command('--midi-config',config),capture_output=True,text=True,timeout=900)
        if result.returncode:raise RuntimeError('MIDI instrument: '+(result.stderr.strip()[-2000:] or 'worker failed'))
    return duration


def run(config):
    import soundfile as sf
    from .models import Track
    data=json.loads(Path(config).read_text());track=Track.model_validate(data['track']);rate=int(data['rate'])
    if rate not in (44100,48000,96000):raise ValueError('Invalid MIDI sample rate')
    import math
    duration_ms = data.get('duration_ms', track.duration_ms)
    if type(duration_ms) not in (int, float) or not math.isfinite(duration_ms) or duration_ms <= 0:
        raise ValueError('Invalid MIDI render duration')
    total=max(1,round(duration_ms*rate/1000))
    limit=max(16*1024**2,min(64*1024**3,int(os.getenv('MTA_SERVER_VST3_DRY_LIMIT_BYTES',str(4*1024**3)))))
    if total*8+4096>limit:raise ValueError('MIDI rendering exceeds the configured prepared-audio size limit')
    from .vst3_transport import HostClock
    host=HostClock(rate=rate);host.data=data.get('transport') or {}
    instrument=Instrument(track,rate,timeline=True,host=host)
    # Publish only fully rendered audio. A failed plug-in or exhausted disk must
    # never destroy a previously successful render at the requested destination.
    target = Path(data['target'])
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(prefix='.mta-midi-', suffix='.wav',
                                         dir=target.parent, delete=False) as staged:
            temporary = Path(staged.name)
        with sf.SoundFile(str(temporary), 'w', samplerate=rate, channels=2, subtype='FLOAT') as writer:
            for start in range(0, total, BLOCK):
                block = instrument.read(min(BLOCK, total-start))
                import numpy as np
                if (not isinstance(block, np.ndarray) or block.shape != (min(BLOCK, total-start), 2)
                        or not np.isfinite(block).all()):
                    raise RuntimeError('MIDI worker received invalid audio')
                writer.write(block)
        os.replace(temporary, target)
        temporary = None
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return 0
