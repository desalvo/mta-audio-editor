"""Bounded, advisory tempo and chroma comparison for sample-editor matching."""
import math
import tempfile
from pathlib import Path

import numpy as np
import soundfile as sf

from . import sample_editor
from .audio_engine import estimate_bpm_and_signature
from .musical_clock import MusicalClock


def _pitch_shift(source, reference):
    from .music_text import _harmonic_features
    values=[]
    for path in (source,reference):
        _,chroma,_,energy=_harmonic_features(path)
        if not len(chroma) or not len(energy) or float(np.max(energy)) < 1e-5:
            raise ValueError('Audio troppo silenzioso per stimare la tonalità')
        values.append(np.average(chroma,axis=0,weights=np.maximum(energy,1e-8)))
    a,b=values
    if np.linalg.norm(a)<1e-8 or np.linalg.norm(b)<1e-8:
        raise ValueError('Tonalità non stimabile: usa la trasposizione manuale')
    scores=[(float(np.dot(np.roll(a,k),b)/(np.linalg.norm(a)*np.linalg.norm(b))),k) for k in range(-6,6)]
    scores.sort(reverse=True)
    return scores[0][1],round(scores[0][0],3)


def analyze(project, track, reference, start_sample, end_sample):
    if track.id==reference.id or track.kind!='audio' or reference.kind!='audio':
        raise ValueError('Scegli due tracce audio diverse')
    source=sample_editor.rendered_source(project.id,track)
    target=sample_editor.rendered_source(project.id,reference)
    src=sf.info(source);ref=sf.info(target)
    start=min(start_sample,src.frames);end=min(end_sample or src.frames,src.frames)
    if end<=start or (end-start)/src.samplerate<4:
        raise ValueError('Seleziona almeno quattro secondi di audio')
    at_ms=start*1000/src.samplerate+float(track.delay_ms or 0)
    end_ms=end*1000/src.samplerate+float(track.delay_ms or 0)
    known = (project.tempo_known or (project.tempo_known is not False and project.base_bpm)
             or project.original_bpm or project.metronome_bpm or project.musical_origin_ms is not None
             or project.adaptive_tempo_map or (project.bpm and project.bpm != 120))
    if not known:
        raise ValueError('Imposta prima i BPM del progetto')
    clock=MusicalClock(project);section=clock.sections[max(0,__import__('bisect').bisect_right(clock.times,at_ms)-1)]
    reference_start=(at_ms-float(reference.delay_ms or 0))/1000
    if reference_start<0 or reference_start+4>ref.frames/ref.samplerate:
        raise ValueError('La traccia di riferimento non copre almeno quattro secondi della selezione')
    duration=min(20.,(end-start)/src.samplerate,ref.frames/ref.samplerate-reference_start)
    with tempfile.TemporaryDirectory(prefix='mta-track-match-') as temp:
        paths=[]
        for path,offset in ((source,start/src.samplerate),(target,reference_start)):
            out=Path(temp)/f'{len(paths)}.wav'
            sample_editor.run(['ffmpeg','-y','-v','error','-ss',f'{offset:.6f}','-t',f'{duration:.6f}',
                               '-i',str(path),'-ac','1','-ar','22050','-c:a','pcm_s16le',str(out)])
            paths.append(out)
        try:
            shift,score=_pitch_shift(*paths)
            pitch_warning=''
        except ValueError:
            shift,score=None,None
            pitch_warning=' Tonalità non stimata: impostare manualmente i semitoni.'
        try:bpm,_=estimate_bpm_and_signature(paths[0])
        except ValueError:bpm=None
    target_bpm=float(section['bpm'])
    if not math.isfinite(target_bpm) or target_bpm<=0:raise ValueError('BPM progetto non validi')
    global_ratio=max(.25,min(4.,float(project.bpm or 120)/float(project.base_bpm or project.bpm or 120)))
    beat_info=None;beat_warning=''
    if bpm:
        try:
            from .beat_sync import sync_plan
            _,beat_info=sync_plan(project,track,reference,source,target,start,end,float(bpm),target_bpm)
        except ValueError as exc:
            beat_warning=str(exc)
    return {'source_bpm':bpm,'target_bpm':round(target_bpm,2),'pitch_semitones':shift,
            'tempo_changes':sum(1 for p in clock.sections if at_ms<p['at']<end_ms),
            'target_bpm_audible':round(target_bpm*global_ratio,2),
            'beat_sync':beat_info,'beat_warning':beat_warning,
            'pitch_similarity':score,'analysis_seconds':round(duration,2),
            'warning':'Stima indicativa: controllare tempo, tonalità e beat; il cambio velocità sposta il materiale successivo.'+pitch_warning}


def tempo_sections(project, start_ms, duration_ms, source_bpm, initial_target_bpm):
    """Map a constant source tempo onto the project clock, in project time.

    Each segment ends exactly at a destination tempo boundary. The input length
    consumed depends on the ratio in that destination section.
    """
    import bisect
    values=(start_ms,duration_ms,source_bpm,initial_target_bpm)
    if not all(math.isfinite(float(x)) for x in values) or duration_ms<=0 or source_bpm<=0 or initial_target_bpm<=0:
        raise ValueError('BPM o durata non validi')
    clock=MusicalClock(project)
    index=max(0,bisect.bisect_right(clock.times,start_ms)-1)
    multiplier=initial_target_bpm/clock.sections[index]['bpm']
    consumed=0.0; at=float(start_ms); result=[]
    while consumed < duration_ms-1e-6:
        section=clock.sections[index]
        ratio=section['bpm']*multiplier/source_bpm
        if not .25 <= ratio <= 4:
            raise ValueError('Il rapporto tempo in una zona è fuori dai limiti 0.25–4')
        next_at=clock.sections[index+1]['at'] if index+1<len(clock.sections) else math.inf
        available=max(0.,next_at-at)*ratio
        take=min(duration_ms-consumed,available)
        if take>1e-6:
            if result and abs(result[-1][2]-ratio)<1e-9:
                result[-1]=(result[-1][0],consumed+take,ratio)
            else:
                result.append((consumed,consumed+take,ratio))
                if len(result)>512:raise ValueError('Intervallo con troppi cambi BPM; suddividi la selezione')
            consumed+=take;at+=take/ratio
        if consumed>=duration_ms-1e-6:break
        index+=1
        if index>=len(clock.sections):raise ValueError('Mappa BPM non valida')
        at=clock.sections[index]['at']
    return result
