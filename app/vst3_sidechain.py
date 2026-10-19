"""Sidechain-aware isolated offline renders share exactly the live signal graph."""
import time


def enabled(project):
    return any(i.enabled and i.plugin=='vst3' and i.sidechain_track_id for items in [project.master_inserts,*[t.inserts for t in project.tracks]] for i in items)


def render(project,resolver,target,*,track_id=None,prefader=False,host_transport=None):
    import numpy as np
    import soundfile as sf
    from .audio_backend import selected
    from .vst3_live import Session
    from .server_vst3 import read_pcm
    if selected()!='cpp':raise ValueError('External VST3 sidechains require the C++ audio engine')
    from .vst3_transport import settings,render_settings
    transport=host_transport or render_settings() or settings(project)
    snapshot=project.model_copy(deep=True)
    if track_id:
        target_track=next((t for t in snapshot.tracks if t.id==track_id),None)
        if not target_track:raise ValueError('Sidechain target track not found')
        for track in snapshot.tracks:track.mute=track.id!=track_id;track.solo=False;track.master_bypass=False
        if prefader:target_track.volume_db=0;target_track.pan=0
        snapshot.master_inserts=[];snapshot.master_volume_db=0;snapshot.master_fade_enabled=False
    if prefader:snapshot.base_bpm=snapshot.bpm;snapshot.pitch_semitones=0
    paths=[resolver(snapshot.id,t.filename) for t in snapshot.tracks]
    session=Session(snapshot,paths,0,output='browser',original_editor=False,startup_timeout=180,host_transport=transport)
    try:
        status=session.status();total=status['total'];limit=4*1024**3
        if total*8+4096>limit:raise ValueError('Sidechain render exceeds the prepared-audio size limit')
        sequence=0;deadline=time.monotonic()+3600
        with sf.SoundFile(target,'w',samplerate=snapshot.sample_rate,channels=2,subtype='FLOAT',format='WAV') as writer:
            while True:
                if time.monotonic()>deadline:raise RuntimeError('Sidechain render timed out')
                result,raw=read_pcm(session,sequence);sequence=result['sequence'];writer.write(np.frombuffer(raw,dtype='<f4').reshape(-1,2))
                if result['ended']:break
    finally:session.close()
    return target
