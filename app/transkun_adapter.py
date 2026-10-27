"""Actual Transkun piano CLI adapter with pinned, operator-managed assets."""
from pathlib import Path
import subprocess
import os
import tempfile


def transcribe(source,options):
    from .studio_asset_registry import runtime,binding
    from .music_interchange import MusicResult,MusicPart,no_notes
    from .midi_smf import read_parts
    import soundfile as sf
    if not isinstance(options,dict) or set(options)-{'asset_id','name'}:raise ValueError('Transkun accepts an installed piano asset and source name')
    value,python=runtime(options.get('asset_id',''),'transkun')
    info=sf.info(source)
    if info.channels not in (1,2) or not 0<info.duration<=600 or not 8000<=info.samplerate<=192000:
        raise ValueError('Transkun accepts bounded mono/stereo audio')
    device=os.getenv('MTA_STUDIO_TRANSKUN_DEVICE','cpu')
    if device not in ('cpu','cuda','mps'):raise ValueError('Invalid operator-selected Transkun device')
    environment={**os.environ,'HF_HUB_OFFLINE':'1','TRANSFORMERS_OFFLINE':'1','PYTHONDONTWRITEBYTECODE':'1'}
    with tempfile.TemporaryDirectory(prefix='mta-transkun-') as temporary:
        target=Path(temporary)/'piano.mid'
        subprocess.run([str(python),str(Path(__file__).with_name('transkun_runner.py')),
            '--source',str(Path(source).resolve()),'--output',str(target),
            '--checkpoint',str(binding(value,'checkpoint')),'--config',str(binding(value,'config')),
            '--checkpoint-sha256',value['files'][value['bindings']['checkpoint']]['sha256'],
            '--config-sha256',value['files'][value['bindings']['config']]['sha256'],
            '--runtime',str(binding(value,'runtime_root')),'--device',device],
            cwd=binding(value,'runtime_root'),env=environment,stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=600,check=True)
        if target.is_symlink() or not target.is_file() or not 14<=target.stat().st_size<=8*1024**2:
            raise ValueError('Transkun produced no safe bounded MIDI file')
        raw=target.read_bytes()
        import mido,io
        midi=mido.MidiFile(file=io.BytesIO(raw))
        if midi.type==2:raise ValueError('Transkun output must be synchronous MIDI')
        if not any(m.type=='note_on' and m.velocity for track in midi.tracks for m in track):
            return no_notes(['Transkun detected no piano notes; no substitute tracks were generated.'])
        parsed=read_parts(raw)
    parts=[]
    for index,part in enumerate(parsed):
        if not part['notes']:continue
        notes=[n.model_copy(update={'id':f'tk-{index}-{i}','origin':'predicted','source_model':'transkun:'+value['id']})
               for i,n in enumerate(part['notes'])]
        if any(n.start_ms+n.duration_ms>info.duration*1000+1000 for n in notes):raise ValueError('Transkun note timeline exceeds source bounds')
        if any(n.channel==9 for n in notes):raise ValueError('Piano specialist output cannot be percussion')
        controls=[c for c in part['controls'] if c.data[0]&240!=192]
        parts.append(MusicPart(id=f'piano-{index}',name=str(options.get('name','Piano'))[:180]+' / Piano',
            program=0,instrument='piano',notes=notes,controls=controls,source_model='transkun:'+value['id']))
    if not parts:return no_notes(['Transkun produced no piano notes.'])
    return MusicResult(parts=parts,warnings=[
        'Transkun is a piano specialist, not a general instrument classifier. Review piano presence and note accuracy.',
        'Timing, velocity and sustain come from the actual model MIDI; no calibrated confidence is implied.'])
