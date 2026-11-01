"""Beat tracking and project-clock warping for audio track matching.

All times are in source milliseconds. Ambiguous or insufficient rhythm is
rejected instead of committing a guessed edit.
"""
from __future__ import annotations

import bisect
import math
from pathlib import Path

import numpy as np
import soundfile as sf
from scipy.signal import find_peaks

from .musical_clock import MusicalClock


def _onset_candidates(path: Path, start_ms: float, end_ms: float):
    with sf.SoundFile(str(path)) as stream:
        sr=stream.samplerate
        start=max(0,min(len(stream),round(start_ms*sr/1000)))
        stop=max(start,min(len(stream),round(end_ms*sr/1000)))
        if stop-start < sr*4:
            raise ValueError('Servono almeno quattro secondi di audio per rilevare i beat')
        # Spectral flux avoids treating a sustained low musical note as a
        # regular succession of attacks, as short-window RMS can do. Process
        # bounded blocks and retain the previous spectrum across block edges.
        hop=max(1,round(sr/200));frame_size=1 << max(8,math.ceil(math.log2(sr*.04)))
        window=np.hanning(frame_size).astype(np.float32)
        stream.seek(start);remaining=stop-start
        pending=np.empty((0,stream.channels),dtype=np.float32);blocks=[];previous=None
        while remaining:
            block=stream.read(min(remaining,hop*512),dtype='float32',always_2d=True)
            if not len(block):break
            remaining-=len(block);pending=np.concatenate((pending,block),axis=0)
            count=max(0,(len(pending)-frame_size)//hop+1)
            if not count:continue
            frames=np.lib.stride_tricks.sliding_window_view(pending,frame_size,axis=0)[::hop][:count]
            spectra=np.abs(np.fft.rfft(frames*window,axis=-1)).mean(axis=1)
            spectra=np.log1p(spectra)
            before=np.vstack((spectra[0] if previous is None else previous,spectra[:-1]))
            values=np.maximum(0,spectra-before).sum(axis=1)
            if previous is None:values[0]=float(np.sum(spectra[0]))
            previous=spectra[-1];blocks.append(values);pending=pending[count*hop:]
        if not blocks:raise ValueError('Audio non analizzabile')
        flux=np.concatenate(blocks)
        maximum=float(np.max(flux))
        if not math.isfinite(maximum) or maximum<1e-5:
            raise ValueError('Beat non rilevabili: audio troppo silenzioso o senza attacchi')
        padded=np.pad(flux,(1,1))
        indices,props=find_peaks(padded,distance=max(1,round(sr/hop*.12)),prominence=maximum*.045,height=maximum*.065)
        indices=indices-1
        valid=(indices>=0)&(indices<len(flux));indices=indices[valid]
        strength=flux[indices]/maximum
        times=(indices.astype(np.float64)*hop+frame_size/2)*1000/sr
        times[indices==0]=0
        return times,strength,(stop-start)*1000/sr


def _track_beats(path: Path, start_ms: float, end_ms: float, hint_bpm: float):
    if not math.isfinite(hint_bpm) or not 40<=hint_bpm<=300:
        raise ValueError('BPM iniziali non validi per il rilevamento dei beat')
    times,strength,duration=_onset_candidates(path,start_ms,end_ms)
    if len(times)<4:
        raise ValueError('Beat non rilevabili con sufficiente affidabilità')
    period=60000/hint_bpm
    # An introduction can precede the first attack by several bars.
    significance=max(.15,float(np.quantile(strength,.9))*.35)
    seed_candidates=np.flatnonzero((strength>=significance)&(times<=period*2))
    if not len(seed_candidates):
        seed_candidates=np.flatnonzero(strength>=significance)
        if len(seed_candidates):
            seed_candidates=seed_candidates[times[seed_candidates]<=times[seed_candidates[0]]+period*2]
    if not len(seed_candidates):raise ValueError('Nessun beat iniziale affidabile nella selezione')
    def seed_score(i):
        score=0.
        for beat in range(5):
            desired=times[i]+beat*period
            left=np.searchsorted(times,desired-period*.18)
            right=np.searchsorted(times,desired+period*.18,side='right')
            if right>left:
                distance=np.abs(times[left:right]-desired)/period
                score+=float(np.max(strength[left:right]-.5*distance))
        return score-.015*times[i]/period
    seed=int(max(seed_candidates,key=seed_score));beats=[float(times[seed])];observed=1;cursor=seed+1
    while beats[-1]+period*.6 < duration:
        last=beats[-1];expected=last+period
        while cursor<len(times) and times[cursor] < last+period*.57:cursor+=1
        if cursor>=len(times):break
        end=cursor
        while end<len(times) and times[end] <= last+period*1.43:end+=1
        if cursor<end:
            ix=np.arange(cursor,end)
            # Suppress background oscillations and weak subdivisions whenever
            # the window contains a clearly stronger rhythmic attack.
            ix=ix[strength[ix]>=max(significance,float(np.max(strength[ix]))*.3)]
            if len(ix):
                distance=np.abs(times[ix]-expected)/period
                scores=strength[ix]-.85*distance
                best=int(ix[int(np.argmax(scores))]);chosen=float(times[best]);cursor=best+1
                delta=chosen-last
                if not 60000/300 <= delta <= 60000/40:raise ValueError('Tempo sorgente fuori intervallo')
                period=.45*period+.55*delta
                observed+=1
            else:
                chosen=expected;cursor=end
        else:
            chosen=expected
        if chosen>=duration:break
        beats.append(chosen)
        if len(beats)>6000:raise ValueError('Troppi beat: suddividi la selezione')
    if len(beats)<4 or observed/len(beats)<.65:
        raise ValueError('Ritmo non sufficientemente affidabile: scegli un intervallo più ritmico')
    return beats,observed/len(beats),duration


def _grid_candidates(clock, quarter: float, phase: float):
    """Find nearby phase-shifted beats, respecting meter and zone rephases."""
    anchor_q=[a['q'] for a in clock.anchors]
    index=max(0,bisect.bisect_right(anchor_q,quarter)-1)
    found=[]
    for i in range(max(0,index-1),min(len(clock.anchors),index+2)):
        anchor=clock.anchors[i];pulse=4/anchor['d'];next_q=anchor_q[i+1] if i+1<len(anchor_q) else math.inf
        n=round((quarter-anchor['q'])/pulse-phase)
        for k in range(n-5,n+7):
            q=anchor['q']+(k+phase)*pulse
            if (i==0 or q>=anchor['q']-1e-8) and q<next_q-1e-8:
                found.append(q)
    return sorted(set(found))


def _next_grid_quarter(clock, quarter: float, phase: float):
    candidates=[q for q in _grid_candidates(clock,quarter,phase) if q>quarter+1e-7]
    if not candidates:raise ValueError('Impossibile proseguire sulla griglia musicale')
    return candidates[0]


def sync_plan(project, track, reference, source: Path, ref: Path, start_sample: int, end_sample: int,
              source_bpm: float, initial_target_bpm: float):
    if track.id==reference.id or track.kind!='audio' or reference.kind!='audio':
        raise ValueError('Scegli due tracce audio diverse')
    known=(project.tempo_known or (project.tempo_known is not False and project.base_bpm)
           or project.original_bpm or project.metronome_bpm or project.musical_origin_ms is not None
           or project.adaptive_tempo_map or (project.bpm and project.bpm != 120))
    if not known:raise ValueError('Imposta prima i BPM del progetto')
    info=sf.info(str(source));ref_info=sf.info(str(ref))
    start=max(0,min(info.frames,int(start_sample)));end=min(info.frames,int(end_sample) or info.frames)
    if end<=start:raise ValueError('Intervallo non valido')
    start_ms=start*1000/info.samplerate;end_ms=end*1000/info.samplerate
    project_start=start_ms+float(track.delay_ms or 0)
    ref_start=project_start-float(reference.delay_ms or 0)
    if ref_start<0 or ref_start+4000>ref_info.frames*1000/ref_info.samplerate:
        raise ValueError('Il riferimento non copre almeno quattro secondi dall’inizio della selezione')
    clock=MusicalClock(project)
    sec=clock.sections[max(0,bisect.bisect_right(clock.times,project_start)-1)]
    if not math.isfinite(initial_target_bpm) or initial_target_bpm<=0:
        raise ValueError('BPM progetto non validi')
    # The dialog displays two decimals; adaptive beat intervals can have a
    # higher-precision BPM than the value round-tripped by the client.
    if abs(initial_target_bpm-sec['bpm'])>.011:
        raise ValueError('Per la sincronizzazione automatica usa i BPM della mappa di progetto')
    beats,quality,duration=_track_beats(source,start_ms,end_ms,source_bpm)
    # Examine the portion of the reference corresponding to this beat range,
    # including later changes, rather than checking only the opening seconds.
    estimated_end=clock.time_at_quarter(clock.quarter_at(project_start)+(len(beats)+1)*4/sec['d'])-project_start
    ref_end=min(ref_info.frames*1000/ref_info.samplerate,ref_start+max(5000,estimated_end+500))
    ref_beats,ref_quality,_=_track_beats(ref,ref_start,ref_end,sec['bpm'])
    phases=[]
    for beat in ref_beats:
        when=project_start+beat
        anchor=clock.anchors[max(0,bisect.bisect_right(clock.anchor_times,when)-1)]
        phases.append(((clock.quarter_at(when)-anchor['q'])/(4/anchor['d']))%1)
    vector=np.mean(np.exp(2j*np.pi*np.asarray(phases)))
    if abs(vector)<.65:
        raise ValueError('I beat del riferimento non seguono la mappa BPM del progetto: sincronizza prima il riferimento')
    phase=(np.angle(vector)/(2*np.pi))%1
    # A global average can hide drift confined to the end of a long selection.
    window=min(8,len(phases))
    starts=set(range(0,len(phases)-window+1,max(1,window//2))) | {len(phases)-window}
    for i in sorted(starts):
        local=np.mean(np.exp(2j*np.pi*np.asarray(phases[i:i+window])))
        distance=abs(np.angle(local/vector))/(2*np.pi)
        if abs(local)<.65 or distance>.18:
            raise ValueError('I beat del riferimento non seguono la mappa BPM del progetto: sincronizza prima il riferimento')
    first_source=beats[0]
    approx_q=clock.quarter_at(project_start+first_source)
    choices=[]
    for q in _grid_candidates(clock,approx_q,phase):
        when=clock.time_at_quarter(q)-project_start
        if first_source<10:
            if when>=first_source-10:choices.append((abs(when-first_source),q,max(0.,when)))
        elif first_source/4 <= when <= first_source*4 and when>=0:
            choices.append((abs(when-first_source),q,when))
    if not choices:raise ValueError('Impossibile allineare il primo beat senza tagliare audio: modifica la selezione')
    _,q,target_first=min(choices)
    leading_silence=max(0.,target_first-first_source) if first_source<10 else 0.
    anchors=[(0.,leading_silence)]
    if first_source>=10:anchors.append((first_source,target_first))
    for beat in beats[1:]:
        q=_next_grid_quarter(clock,q,phase)
        target=clock.time_at_quarter(q)-project_start
        anchors.append((beat,target))
    # Extrapolate the last detected local source beat interval. The target
    # remains on the project's tempo map, including a final zone transition.
    last_span=beats[-1]-beats[-2]
    end_fraction=(duration-beats[-1])/last_span
    next_q=_next_grid_quarter(clock,q,phase)
    end_target=clock.time_at_quarter(q+end_fraction*(next_q-q))-project_start
    if duration-beats[-1]>.01:anchors.append((duration,end_target))
    plan=[]
    for (a,x),(b,y) in zip(anchors,anchors[1:]):
        if b-a<1e-4:continue
        if y<=x:raise ValueError('La mappa dei beat non è crescente')
        ratio=(b-a)/(y-x)
        if not .25<=ratio<=4:raise ValueError('Allineamento beat oltre il rapporto di velocità consentito')
        plan.append((a,b,ratio))
    if not plan:raise ValueError('Nessun beat utilizzabile')
    return plan,{'source_beats':len(beats),'reference_beats':len(ref_beats),
                 'source_confidence':round(quality,3),'reference_confidence':round(ref_quality,3),
                 'first_shift_ms':round(target_first-first_source,1),'duration_ms':round(end_target,1),
                 'leading_silence_ms':leading_silence,
                 'reference_covers_output':bool(ref_start+end_target<=ref_info.frames*1000/ref_info.samplerate+1)}
