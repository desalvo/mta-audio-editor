import numpy as np
import pytest
import soundfile as sf

from app.models import Clip,Marker,SampleEffectRequest,Track


def _clicks(path,times,duration=8,rate=44100):
    data=np.zeros(int(duration*rate),dtype='float32')
    for t in times:
        i=round(t*rate);n=min(882,len(data)-i)
        if n>0:data[i:i+n]+=.6*np.hanning(n).astype('float32')*np.sin(2*np.pi*880*np.arange(n)/rate)
    sf.write(path,data,rate,subtype='PCM_24')


def _fixture(tmp_path,monkeypatch):
    from app import storage
    monkeypatch.setattr(storage,'ROOT',(tmp_path/'projects').resolve())
    p=storage.create_project('Beat sync');p.bpm=p.base_bpm=120;p.tempo_known=True;p.metronome_mode='zones'
    p.markers=[Marker(id='change',time_ms=2000,label='Change')]
    p.metronome_manual_zone_bpms={'START|change':120,'change|END':90}
    source=[.25,.75,1.25,1.75,2.4,3.05,3.7,4.35,5.,5.65,6.3,6.95,7.6]
    # 0.4 s beat phase with 120 -> 90 BPM in project time.
    reference=[.4,.9,1.4,1.9]+[2.533333+i*2/3 for i in range(9)]
    for name,beats in [('source',source),('ref',reference)]:
        path=storage.audio_path(p.id,name+'.wav');_clicks(path,beats)
        p.tracks.append(Track(id=name,name=name,filename=name+'.wav',duration_ms=8000,channels=1,
            clips=[Clip(id=name+'clip',source_start_ms=0,source_end_ms=8000,timeline_start_ms=0)]))
    return p,source,reference


def test_variable_source_and_project_tempo_map_with_beat_phase(tmp_path,monkeypatch):
    from app import storage
    from app.beat_sync import sync_plan
    p,source,reference=_fixture(tmp_path,monkeypatch)
    plan,info=sync_plan(p,p.tracks[0],p.tracks[1],storage.audio_path(p.id,'source.wav'),
        storage.audio_path(p.id,'ref.wav'),0,8*44100,120,120)
    assert info['source_beats']>=len(source)-1
    assert info['first_shift_ms']==pytest.approx(150,abs=20)
    # The end of each plan segment is a detected source beat and lands on the
    # reference phase and project tempo map, even after the source slows down.
    mapping=[];elapsed=0
    for a,b,ratio in plan:
        elapsed+=(b-a)/ratio;mapping.append((b/1000,elapsed/1000))
    for src,dst in zip(source,reference):
        nearby=min(mapping,key=lambda x:abs(x[0]-src))
        assert nearby[0]==pytest.approx(src,abs=.025)
        assert nearby[1]==pytest.approx(dst,abs=.035)


def test_actual_ffmpeg_render_aligns_pulses_and_preserves_outer_selection(tmp_path,monkeypatch):
    from app import sample_editor,storage
    p,source,reference=_fixture(tmp_path,monkeypatch)
    req=SampleEffectRequest(effect='match',start_sample=0,end_sample=8*44100,
        params={'reference_track_id':'ref','source_bpm':120,'target_bpm':120,'semitones':0})
    result=sample_editor.apply_effect(p,p.tracks[0],req,False);audio,sr=sf.read(result)
    for when in reference[:len(source)]:
        window=audio[max(0,int((when-.065)*sr)):int((when+.065)*sr)]
        assert np.max(np.abs(window))>.025,(when,np.max(np.abs(window)))


def test_no_rhythm_does_not_commit_or_guess(tmp_path,monkeypatch):
    from app import sample_editor,storage
    p,_,_=_fixture(tmp_path,monkeypatch)
    sf.write(storage.audio_path(p.id,'ref.wav'),np.zeros(8*44100),44100,subtype='PCM_24')
    before=p.tracks[0].filename
    req=SampleEffectRequest(effect='match',start_sample=0,end_sample=8*44100,
        params={'reference_track_id':'ref','source_bpm':120,'target_bpm':120,'semitones':0})
    with pytest.raises(ValueError,match='Beat|beat'):
        sample_editor.apply_effect(p,p.tracks[0],req,False)
    assert p.tracks[0].filename==before


def test_partial_selection_preserves_audio_before_and_after(tmp_path,monkeypatch):
    from app import sample_editor
    p,_,_=_fixture(tmp_path,monkeypatch)
    rate=44100
    req=SampleEffectRequest(effect='match',start_sample=rate,end_sample=rate*6,
        params={'reference_track_id':'ref','source_bpm':120,'target_bpm':120,'semitones':0})
    original,_=sf.read(sample_editor.rendered_source(p.id,p.tracks[0]))
    out=sample_editor.apply_effect(p,p.tracks[0],req,False);audio,sr=sf.read(out)
    assert sr==rate
    assert np.max(np.abs(audio[:rate]-original[:rate]))<.0001
    assert np.max(np.abs(audio[-2*rate:]-original[-2*rate:]))<.0001
    for when in (1.4,1.9,2.5333,3.2,3.8667,4.5333,5.2,5.8667):
        window=audio[int((when-.07)*sr):int((when+.07)*sr)]
        assert np.max(np.abs(window))>.025,when


def test_phase_grid_restarts_when_zone_boundary_rephases():
    from app.beat_sync import _next_grid_quarter
    from app.musical_clock import MusicalClock
    from app.models import Project
    p=Project(id='p',title='x',bpm=120,base_bpm=120,metronome_mode='zones',
       markers=[Marker(id='zone',time_ms=2100,label='Zone')],
       metronome_manual_zone_bpms={'START|zone':120,'zone|END':90})
    clock=MusicalClock(p);q=3.8
    assert clock.time_at_quarter(q)==pytest.approx(1900)
    q=_next_grid_quarter(clock,q,.8)
    assert clock.time_at_quarter(q)==pytest.approx(2100+(.8*60000/90))
    q=_next_grid_quarter(clock,q,.8)
    assert clock.time_at_quarter(q)==pytest.approx(2100+(1.8*60000/90))


def test_adaptive_project_map_uses_reference_phase(tmp_path,monkeypatch):
    from app import storage
    from app.beat_sync import sync_plan
    from app.models import AdaptiveTempoPoint
    p,source,_=_fixture(tmp_path,monkeypatch)
    p.metronome_mode='adaptive'
    p.adaptive_tempo_map=[AdaptiveTempoPoint(time_ms=0,bpm=120,beat_index=0),
        AdaptiveTempoPoint(time_ms=2000,bpm=90,beat_index=4),
        AdaptiveTempoPoint(time_ms=4000,bpm=90,beat_index=7)]
    plan,info=sync_plan(p,p.tracks[0],p.tracks[1],storage.audio_path(p.id,'source.wav'),
        storage.audio_path(p.id,'ref.wav'),0,8*44100,120,120)
    mapped=[];elapsed=0
    for a,b,ratio in plan:
        elapsed+=(b-a)/ratio;mapped.append((b/1000,elapsed/1000))
    assert info['first_shift_ms']==pytest.approx(150,abs=20)
    for src,dst in zip(source,[.4,.9,1.4,1.9]+[2.533333+i*2/3 for i in range(9)]):
        assert min(mapped,key=lambda x:abs(x[0]-src))[1]==pytest.approx(dst,abs=.035)


def test_http_match_applies_undoable_new_source_and_rejects_missing_reference(tmp_path,monkeypatch):
    from fastapi.testclient import TestClient
    from app import main,storage
    p,_,_=_fixture(tmp_path,monkeypatch);storage.save_project(p)
    monkeypatch.setenv('MTA_ALLOW_INSECURE_NO_AUTH','true')
    client=TestClient(main.app,headers={'X-MTA-Request':'1'})
    url=f'/api/projects/{p.id}/tracks/source/sample-editor/effect-apply'
    payload={'effect':'match','start_sample':44100,'end_sample':6*44100,
             'params':{'reference_track_id':'ref','source_bpm':120,'target_bpm':120,'semitones':0}}
    invalid=client.post(url,json={**payload,'params':{**payload['params'],'reference_track_id':'missing'}})
    assert invalid.status_code==400
    assert storage.load_project(p.id).tracks[0].filename=='source.wav'
    response=client.post(url,json=payload);assert response.status_code==200,response.text
    updated=response.json()['project'];assert updated['tracks'][0]['filename']!='source.wav'
    assert any(x['filename']=='source.wav' for x in updated['clip_library'])
    assert updated['tracks'][0]['waveform_peaks']
    # The prior project can be restored with the retained asset.
    before=p.model_dump(mode='json');before['clip_library']=updated['clip_library']
    restored=client.put(f'/api/projects/{p.id}',json=before)
    assert restored.status_code==200,restored.text
    assert storage.load_project(p.id).tracks[0].filename=='source.wav'


def test_accelerating_source_matches_fixed_project_and_reference(tmp_path,monkeypatch):
    from app import storage,sample_editor
    from app.beat_sync import sync_plan
    p,_,_=_fixture(tmp_path,monkeypatch);p.metronome_mode='fixed';p.metronome_bpm=120
    # Constantly accelerating source, from 100 BPM to approximately 150 BPM.
    source=[];t=.3;interval=.6
    while t<7.7:
        source.append(t);t+=interval;interval=max(.40,interval-.015)
    reference=np.arange(.12,8,.5).tolist()
    _clicks(storage.audio_path(p.id,'source.wav'),source)
    _clicks(storage.audio_path(p.id,'ref.wav'),reference)
    plan,info=sync_plan(p,p.tracks[0],p.tracks[1],storage.audio_path(p.id,'source.wav'),
        storage.audio_path(p.id,'ref.wav'),0,8*44100,100,120)
    mapped=[];elapsed=0
    for a,b,ratio in plan:
        elapsed+=(b-a)/ratio;mapped.append((b/1000,elapsed/1000))
    assert info['source_beats']==len(source)
    # The closest reference beat to the first source beat is .12 s.
    for i,src in enumerate(source):
        pair=min(mapped,key=lambda x:abs(x[0]-src))
        assert pair[0]==pytest.approx(src,abs=.025)
        assert pair[1]==pytest.approx(.12+i*.5,abs=.035)
    req=SampleEffectRequest(effect='match',start_sample=0,end_sample=8*44100,
        params={'reference_track_id':'ref','source_bpm':100,'target_bpm':120,'semitones':0})
    audio,sr=sf.read(sample_editor.apply_effect(p,p.tracks[0],req,False))
    for i in range(len(source)):
        at=.12+i*.5;window=audio[max(0,int((at-.07)*sr)):int((at+.07)*sr)]
        assert np.max(np.abs(window))>.025,(i,at)


def test_project_delay_is_accounted_for_and_adaptive_bpm_rounds(tmp_path,monkeypatch):
    from app import storage
    from app.beat_sync import sync_plan
    from app.models import AdaptiveTempoPoint
    p,_,_=_fixture(tmp_path,monkeypatch)
    p.tracks[0].delay_ms=100;p.tracks[1].delay_ms=100
    p.metronome_mode='adaptive';p.adaptive_tempo_map=[
        AdaptiveTempoPoint(time_ms=0,bpm=120,beat_index=0),
        AdaptiveTempoPoint(time_ms=2003,bpm=90,beat_index=4),
        AdaptiveTempoPoint(time_ms=4000,bpm=90,beat_index=7)]
    bpm=round(60000*4/2003,2)
    plan,info=sync_plan(p,p.tracks[0],p.tracks[1],storage.audio_path(p.id,'source.wav'),
        storage.audio_path(p.id,'ref.wav'),0,8*44100,120,bpm)
    assert plan and info['first_shift_ms']==pytest.approx(150,abs=20)


def test_first_beat_at_start_can_be_delayed_without_losing_audio(tmp_path,monkeypatch):
    from app import sample_editor,storage
    from app.beat_sync import sync_plan
    p,_,_=_fixture(tmp_path,monkeypatch);p.metronome_mode='fixed';p.metronome_bpm=120
    source=np.arange(0,8,.5).tolist();reference=np.arange(.2,8,.5).tolist()
    _clicks(storage.audio_path(p.id,'source.wav'),source)
    _clicks(storage.audio_path(p.id,'ref.wav'),reference)
    plan,info=sync_plan(p,p.tracks[0],p.tracks[1],storage.audio_path(p.id,'source.wav'),
        storage.audio_path(p.id,'ref.wav'),0,8*44100,120,120)
    assert info['first_shift_ms']==pytest.approx(200,abs=20)
    assert info['leading_silence_ms']==pytest.approx(200,abs=20)
    req=SampleEffectRequest(effect='match',start_sample=0,end_sample=8*44100,
        params={'reference_track_id':'ref','source_bpm':120,'target_bpm':120,'semitones':0})
    audio,sr=sf.read(sample_editor.apply_effect(p,p.tracks[0],req,False))
    assert np.max(np.abs(audio[:int(.15*sr)]))<.001
    for t in reference:
        window=audio[int((t-.06)*sr):int((t+.06)*sr)]
        assert np.max(np.abs(window))>.025,t


def test_reference_that_disagrees_with_project_clock_is_rejected(tmp_path,monkeypatch):
    from app import storage
    from app.beat_sync import sync_plan
    p,_,_=_fixture(tmp_path,monkeypatch);p.metronome_mode='fixed';p.metronome_bpm=120
    _clicks(storage.audio_path(p.id,'ref.wav'),np.arange(.2,8,.6))
    with pytest.raises(ValueError,match='riferimento.*mappa BPM'):
        sync_plan(p,p.tracks[0],p.tracks[1],storage.audio_path(p.id,'source.wav'),
           storage.audio_path(p.id,'ref.wav'),0,8*44100,120,120)


def test_simple_meter_eighth_note_project_positions():
    from app.beat_sync import _next_grid_quarter
    from app.models import Project
    from app.musical_clock import MusicalClock
    p=Project(id='p',title='6/8',bpm=120,base_bpm=120,metronome_bpm=120,
              metronome_time_signature='6/8')
    clock=MusicalClock(p);q=.125
    assert clock.time_at_quarter(q)==pytest.approx(125)
    nxt=_next_grid_quarter(clock,q,.25)
    assert clock.time_at_quarter(nxt)==pytest.approx(625)


def test_polyphonic_mix_with_weaker_offbeat_attacks(tmp_path,monkeypatch):
    from app import storage
    from app.beat_sync import sync_plan
    p,source,reference=_fixture(tmp_path,monkeypatch)
    rate=44100
    for name,beats in [('source',source),('ref',reference)]:
        path=storage.audio_path(p.id,name+'.wav');data,_=sf.read(path)
        tt=np.arange(len(data))/rate
        data+=.06*np.sin(2*np.pi*220*tt)+.035*np.sin(2*np.pi*330*tt)
        for i in range(len(beats)-1):
            pos=int((beats[i]+(beats[i+1]-beats[i])/2)*rate);n=440
            data[pos:pos+n]+=.10*np.hanning(n)*np.sin(2*np.pi*3500*np.arange(n)/rate)
        sf.write(path,data,rate,subtype='PCM_24')
    plan,info=sync_plan(p,p.tracks[0],p.tracks[1],storage.audio_path(p.id,'source.wav'),
       storage.audio_path(p.id,'ref.wav'),0,rate*8,120,120)
    assert info['source_beats']==len(source)
    elapsed=0;mapped=[]
    for a,b,ratio in plan:
        elapsed+=(b-a)/ratio;mapped.append((b/1000,elapsed/1000))
    for src,dst in zip(source,reference):
        assert min(mapped,key=lambda x:abs(x[0]-src))[1]==pytest.approx(dst,abs=.05)


@pytest.mark.parametrize('frequency',[55,123,440])
def test_sustained_note_is_not_mistaken_for_a_beat(tmp_path,frequency):
    from app.beat_sync import _track_beats
    rate=44100;t=np.arange(rate*8)/rate;path=tmp_path/'tone.wav'
    sf.write(path,.3*np.sin(2*np.pi*frequency*t),rate,subtype='PCM_24')
    with pytest.raises(ValueError,match='Beat|beat|Ritmo|ritmo'):
        _track_beats(path,0,8000,120)


def test_http_analysis_includes_reference_beat_phase_then_apply(tmp_path,monkeypatch):
    from fastapi.testclient import TestClient
    from app import main,storage
    p,_,_=_fixture(tmp_path,monkeypatch);storage.save_project(p)
    monkeypatch.setenv('MTA_ALLOW_INSECURE_NO_AUTH','true')
    client=TestClient(main.app,headers={'X-MTA-Request':'1'})
    base=f'/api/projects/{p.id}/tracks/source/sample-editor'
    result=client.post(base+'/match-analysis',json={'reference_track_id':'ref','start_sample':0,'end_sample':8*44100})
    assert result.status_code==200,result.text
    info=result.json()
    assert info['source_bpm'] and info['beat_sync'],info
    assert info['beat_sync']['first_shift_ms']==pytest.approx(150,abs=30)
    response=client.post(base+'/effect-apply',json={'effect':'match','start_sample':0,'end_sample':8*44100,
        'params':{'reference_track_id':'ref','source_bpm':info['source_bpm'],'target_bpm':info['target_bpm'],'semitones':0}})
    assert response.status_code==200,response.text


def test_reference_drift_after_twenty_seconds_is_rejected(tmp_path,monkeypatch):
    from app import storage
    from app.beat_sync import sync_plan
    p,_,_=_fixture(tmp_path,monkeypatch);p.metronome_mode='fixed';p.metronome_bpm=120
    source=np.arange(.25,32,.5).tolist()
    reference=np.arange(.4,20,.5).tolist()+np.arange(20.4,32,.6).tolist()
    _clicks(storage.audio_path(p.id,'source.wav'),source,duration=32)
    _clicks(storage.audio_path(p.id,'ref.wav'),reference,duration=32)
    with pytest.raises(ValueError,match='riferimento.*mappa BPM'):
        sync_plan(p,p.tracks[0],p.tracks[1],storage.audio_path(p.id,'source.wav'),
           storage.audio_path(p.id,'ref.wav'),0,32*44100,120,120)


def test_manual_pitch_remains_available_in_beat_sync(tmp_path,monkeypatch):
    from app import sample_editor,storage
    p,_,_=_fixture(tmp_path,monkeypatch);rate=44100
    path=storage.audio_path(p.id,'source.wav');data,_=sf.read(path);t=np.arange(len(data))/rate
    data+=.07*np.sin(2*np.pi*220*t);sf.write(path,data,rate,subtype='PCM_24')
    req=SampleEffectRequest(effect='match',start_sample=0,end_sample=8*rate,
        params={'reference_track_id':'ref','source_bpm':120,'target_bpm':120,'semitones':2})
    audio,sr=sf.read(sample_editor.apply_effect(p,p.tracks[0],req,False))
    def amplitude(f):
        x=audio[int(sr*.5):int(sr*1.4)];n=np.arange(len(x));return abs(np.sum(x*np.exp(-2j*np.pi*f*n/sr)))
    assert amplitude(220*2**(2/12))>amplitude(220)*3
