import subprocess

import numpy as np
import pytest
import soundfile as sf

from app.codec import _normalize_mta_slots


def test_mta_common_gain_is_measured_on_unclipped_master_and_keeps_ratio(tmp_path):
    rate=44100
    t=np.arange(rate)/rate
    a=np.column_stack([.55*np.sin(2*np.pi*440*t)]*2)
    b=np.column_stack([.35*np.sin(2*np.pi*440*t)]*2)
    paths=[tmp_path/'a.wav',tmp_path/'b.wav']
    for p,x in zip(paths,[a,b]): sf.write(p,x,rate,subtype='FLOAT')
    output=_normalize_mta_slots(paths,-6,tmp_path)
    aa,_=sf.read(output[0]);bb,_=sf.read(output[1])
    assert np.max(np.abs(aa+bb))==pytest.approx(10**(-6/20),abs=2e-4)
    assert np.max(np.abs(aa))/np.max(np.abs(bb))==pytest.approx(.55/.35,rel=.002)
    assert np.max(np.abs(aa))<np.max(np.abs(a))


def test_mta_normalization_rejects_silence_and_individual_slot_clipping(tmp_path):
    paths=[tmp_path/'a.wav',tmp_path/'b.wav']
    for p in paths: sf.write(p,np.zeros((4410,2)),44100,subtype='FLOAT')
    with pytest.raises(ValueError,match='silent'): _normalize_mta_slots(paths,-1,tmp_path)
    sf.write(paths[0],np.full((4410,2),.8),44100,subtype='FLOAT')
    sf.write(paths[1],np.full((4410,2),-.6),44100,subtype='FLOAT')
    with pytest.raises(ValueError,match='clip an individual'): _normalize_mta_slots(paths,-1,tmp_path)


def test_mta_normalization_can_amplify_and_handles_unequal_lengths(tmp_path):
    a=tmp_path/'a.wav'; b=tmp_path/'b.wav'
    sf.write(a,np.full((4410,2),.10),44100,subtype='FLOAT')
    sf.write(b,np.full((2205,2),.05),44100,subtype='FLOAT')
    out=_normalize_mta_slots([a,b],-6,tmp_path)
    x,_=sf.read(out[0]);y,_=sf.read(out[1])
    assert x[0,0]+y[0,0]==pytest.approx(10**(-6/20),abs=.001)
    assert x[0,0]/y[0,0]==pytest.approx(2,abs=.001)
    assert len(x)==4410 and len(y)==2205


def test_select_all_updates_tracks_and_lanes_without_rebuilding():
    js=r'''const fs=require('fs'),vm=require('vm'),assert=require('assert');
const src=fs.readFileSync('app/static/app.js','utf8');
const a=src.indexOf('function selectAllTracks()'),b=src.indexOf('\nfunction trackHeightPx',a);
const elements=(prefix)=>['a','b'].map(id=>({id:prefix+id,dataset:{track:id},classList:{values:{},toggle(k,v){this.values[k]=v}}}));
const heads=elements('head-'),lanes=elements('');let updates=0;
const ctx={current:{tracks:[{id:'a'},{id:'b'}]},selectedTrackId:'a',selectedTrackIdSet:new Set(['a']),$$:s=>s==='.track-head'?heads:lanes,updateSel:()=>updates++};
vm.createContext(ctx);vm.runInContext(src.slice(a,b),ctx);ctx.selectAllTracks();
assert.deepEqual(Array.from(ctx.selectedTrackIdSet),['a','b']);assert.ok(heads[1].classList.values.selected);assert.ok(lanes[1].classList.values['edit-selected']);assert.equal(updates,1);
// The context menu's track/timeline dispatch is exercised by test_r210_bounce_master.
assert.ok(src.includes("key==='a'&&!e.shiftKey"));
'''
    subprocess.run(['node','-e',js],check=True)


def test_normalized_mta_actual_export_preserves_streams_and_peak(tmp_path,monkeypatch):
    import app.storage as storage
    from app.codec import export_mta
    from app.models import Clip, Track
    from app.mta_reverse import deobfuscate_media_copy
    monkeypatch.setattr(storage,'ROOT',(tmp_path/'projects').resolve())
    project=storage.create_project('Peak',target='MTA16',owner_user_id=1)
    rate=44100;t=np.arange(rate*2)/rate
    for i,amplitude in enumerate((.2,.1)):
        name=f'{i}.wav';path=storage.audio_path(project.id,name)
        sig=np.column_stack([amplitude*np.sin(2*np.pi*440*t)]*2)
        sf.write(path,sig,rate,subtype='PCM_24')
        project.tracks.append(Track(id=f't{i}',name=f'T{i}',filename=name,duration_ms=2000,channels=2,
            clips=[Clip(id=f'c{i}',source_start_ms=0,source_end_ms=2000,timeline_start_ms=0)]))
    output=tmp_path/'normal.mta';export_mta(project,output,profile='generic',normalize_peak_db=-6)
    canonical=tmp_path/'out.mka';deobfuscate_media_copy(output,canonical)
    decoded=[]
    for i in range(2):
        path=tmp_path/f'decoded{i}.wav'
        subprocess.run(['ffmpeg','-y','-v','error','-i',str(canonical),'-map',f'0:a:{i}',
                        '-c:a','pcm_f32le',str(path)],check=True)
        decoded.append(sf.read(path)[0])
    x,y=decoded
    assert np.max(np.abs(x+y))==pytest.approx(10**(-6/20),abs=.04)
    assert np.max(np.abs(x))/np.max(np.abs(y))==pytest.approx(2,rel=.05)


def test_tempo_plan_respects_destination_boundaries_and_source_consumption():
    from app.models import Project,Marker,AdaptiveTempoPoint
    from app.track_match import tempo_sections
    p=Project(id='p',title='Tempo',bpm=120,base_bpm=120,metronome_mode='zones',
              markers=[Marker(id='change',time_ms=2000,label='Change')],
              metronome_manual_zone_bpms={'START|change':120,'change|END':90})
    plan=tempo_sections(p,0,4000,120,120)
    assert len(plan)==2
    assert plan[0]==pytest.approx((0,2000,1))
    assert plan[1]==pytest.approx((2000,4000,.75))
    assert sum((b-a)/ratio for a,b,ratio in plan)==pytest.approx(2000+2000/.75)
    p.metronome_mode='adaptive'
    p.adaptive_tempo_map=[AdaptiveTempoPoint(time_ms=0,bpm=120,beat_index=0),
                          AdaptiveTempoPoint(time_ms=2000,bpm=90,beat_index=4),
                          AdaptiveTempoPoint(time_ms=4000,bpm=90,beat_index=7)]
    adaptive=tempo_sections(p,0,4000,120,120)
    assert len(adaptive)==len(plan)
    for actual,expected in zip(adaptive,plan):
        assert actual==pytest.approx(expected)


def test_multizone_match_renders_real_audio_at_project_tempo(tmp_path,monkeypatch):
    from app import storage,sample_editor
    from app.models import Track,Clip,Marker,SampleEffectRequest
    monkeypatch.setattr(storage,'ROOT',(tmp_path/'projects').resolve())
    p=storage.create_project('Tempo zones');p.bpm=p.base_bpm=120;p.tempo_known=True;p.metronome_mode='zones'
    p.markers=[Marker(id='change',time_ms=2000,label='Change')]
    p.metronome_manual_zone_bpms={'START|change':120,'change|END':90}
    rate=44100;signal=np.zeros(rate*4)
    for second in np.arange(.25,4,.5):
        i=round(second*rate);signal[i:i+441]=.4*np.hanning(441)
    sf.write(storage.audio_path(p.id,'pulse.wav'),signal,rate,subtype='PCM_24')
    track=Track(id='t',name='T',filename='pulse.wav',duration_ms=4000,channels=1,
        clips=[Clip(id='c',source_start_ms=0,source_end_ms=4000,timeline_start_ms=0)])
    p.tracks=[track]
    req=SampleEffectRequest(effect='match',start_sample=0,end_sample=len(signal),params={'source_bpm':120,'target_bpm':120,'semitones':0})
    out=sample_editor.apply_effect(p,track,req,False);audio,sr=sf.read(out)
    assert len(audio)/sr==pytest.approx(2+2/.75,abs=.02)
    for at in (.25,.75,1.25,1.75,2+.25/.75,2+.75/.75,2+1.25/.75,2+1.75/.75):
        x=audio[max(0,int((at-.10)*sr)):int((at+.10)*sr)]
        assert np.max(np.abs(x))>.05,(at,np.max(np.abs(x)))
