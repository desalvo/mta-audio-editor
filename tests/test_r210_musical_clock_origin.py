"""User-facing musical position, actual grid and MIDI round-trip contracts."""
import json
from pathlib import Path
import subprocess

import pytest

from app.models import Project, MidiNote, Clip, Track
from app.musical_clock import MusicalClock
from app.vst3_tempo_map import TempoMap
from app.midi_smf import read_parts, write_parts


def test_fixed_origin_preroll_and_tick_carry():
    p=Project(id='clock',title='Clock',bpm=120,musical_origin_ms=1000)
    c=MusicalClock(p)
    assert c.format(1000)=='1:1:1:000'
    assert c.format(1125)=='1:1:2:000'
    assert c.format(1500)=='1:2:1:000'
    assert c.format(2999.999)=='2:1:1:000'
    assert c.position(500)['bar']==0
    assert c.parse('1:1:2:120')==1187.5
    assert c.parse('2:1')==3000
    with pytest.raises(ValueError):c.parse('1:1:1:240')
    assert Project.model_validate_json(p.model_dump_json()).musical_origin_ms==1000
    assert Project(id='default',title='Default').transport_time_mode=='auto'


def test_global_bars_across_zones_instead_of_resetting_to_one():
    p={'bpm':120,'musical_origin_ms':0,'metronome_mode':'zones','markers':[{'id':'verse','time_ms':1000}],
       'metronome_manual_zone_bpms':{'START|verse':120,'verse|END':60},
       'metronome_manual_zone_signatures':{'verse|END':'3/4'}}
    c=MusicalClock(p)
    assert c.format(1000)=='2:1:1:000'
    assert c.format(4000)=='3:1:1:000'
    assert c.parse('3:1:1:000')==4000
    assert c.quarter_at(2000)==3
    assert c.time_at_quarter(3)==2000
    with pytest.raises(ValueError):c.parse('1:4:1:000') # partial bar before marker
    host=TempoMap(p)
    assert host.position(1000)==(60,3,4,2.,2.)


def test_adaptive_real_intervals_preroll_shift_and_compound_meter():
    p={'bpm':120,'time_signature':'6/8','musical_origin_ms':500,'metronome_shift_ms':100,
       'metronome_mode':'adaptive','metronome_pre_roll_bars':1,
       'adaptive_tempo_map':[{'time_ms':500,'bpm':120,'beat_index':0},{'time_ms':1000,'bpm':60,'beat_index':1},{'time_ms':2000,'bpm':60,'beat_index':2}]}
    c=MusicalClock(p)
    assert c.format(600)=='1:1:1:000'
    assert c.format(1100)=='1:2:1:000'
    assert c.format(1600)=='1:2:3:000'
    assert c.parse('1:3:1:000')==2100
    assert c.quarter_at(2100)==1
    assert TempoMap(p).position(1600)[3]==.75


@pytest.mark.parametrize('project',[
    {'bpm':123.5,'musical_origin_ms':1250},
    {'bpm':120,'metronome_mode':'zones','musical_origin_ms':500,'markers':[{'id':'x','time_ms':2750}], 'metronome_zone_bpms':{'0':120,'2750':73},'metronome_zone_signatures':{'2750':'7/8'}},
    {'bpm':120,'time_signature':'6/8','metronome_mode':'adaptive','musical_origin_ms':500,'metronome_shift_ms':125,'adaptive_tempo_map':[{'time_ms':1000,'beat_index':0,'bpm':120},{'time_ms':1500,'beat_index':1,'bpm':60},{'time_ms':2500,'beat_index':2,'bpm':60}]},
])
def test_python_javascript_and_inverse_agree(project):
    times=[0,125,500,625,999,1000,1375,1500,2750,5000,12000]
    script="const {Clock}=require('./app/static/musical_clock.js');const c=new Clock(JSON.parse(process.argv[1]));console.log(JSON.stringify(JSON.parse(process.argv[2]).map(t=>[c.format(t),c.parse(c.format(t)),c.quarterAt(t),c.timeAtQuarter(c.quarterAt(t))])))"
    actual=json.loads(subprocess.check_output(['node','-e',script,json.dumps(project),json.dumps(times)],text=True))
    c=MusicalClock(project)
    for t, row in zip(times, actual, strict=True):
        assert row[0]==c.format(t)
        assert row[1]==pytest.approx(c.parse(c.format(t)))
        assert row[2]==pytest.approx(c.quarter_at(t))
        assert row[3]==pytest.approx(t)


def test_smf_export_preserves_absolute_audio_time_and_project_tempo_changes():
    p=Project(id='export',title='Export',target='DAW_MIDI',bpm=120,musical_origin_ms=500,metronome_mode='zones',
              markers=[{'id':'slow','time_ms':2000,'label':'Slow'}],metronome_zone_bpms={'0':120,'2000':60})
    t=Track(id='keys',name='Keys',filename='anchor.wav',kind='midi',duration_ms=6000,
            midi_notes=[MidiNote(id='a',pitch=60,start_ms=2500,duration_ms=500),MidiNote(id='b',pitch=64,start_ms=4000,duration_ms=250)],
            clips=[Clip(id='full',source_end_ms=6000)])
    data=write_parts([t],file_type=1,project=p)
    parts=read_parts(data)
    notes=[n for part in parts for n in part['notes']]
    assert [n.start_ms for n in notes]==pytest.approx([2500,4000],abs=1)
    assert [n.duration_ms for n in notes]==pytest.approx([500,250],abs=1)
    metas=[m.message for part in parts for m in part['midi_meta']]
    assert any(m.get('tempo')==1000000 for m in metas)
    assert any(m.get('text')=='MTA-MUSICAL-ORIGIN:500' for m in metas)


def test_template_loads_clock_before_editor_and_explicit_format():
    html=Path('app/templates/index.html').read_text()
    assert html.index('/static/musical_clock.js')<html.index('/static/app.js')
    assert 'Bar:Beats:Division:Ticks' in html


@pytest.mark.parametrize('mode',['fixed','adaptive'])
def test_metronome_endpoint_sets_first_audible_preroll_as_origin(tmp_path,monkeypatch,mode):
    import numpy as np
    import soundfile as sf
    import app.main as main
    import app.storage as storage
    from fastapi.testclient import TestClient
    from app.models import AdaptiveTempoPoint
    monkeypatch.setattr(storage,'ROOT',tmp_path)
    monkeypatch.setenv('MTA_ALLOW_INSECURE_NO_AUTH','true')
    p=storage.create_project('Musical origin')
    p.bpm=120
    p.metronome_mode=mode
    p.tracks=[Track(id='music',name='Music',filename='music.wav',duration_ms=12000,clips=[Clip(id='all',source_end_ms=12000)])]
    storage.save_project(p)
    source=storage.audio_path(p.id,'music.wav')
    sf.write(source,np.zeros(44100*12),44100)
    initial=source.read_bytes()
    if mode=='adaptive':
        times=[7000,7500,8500,9500,10500,11500]
        monkeypatch.setattr(main,'estimate_adaptive_tempo_map',lambda _: (times,[AdaptiveTempoPoint(time_ms=t,bpm=120 if i==0 else 60,beat_index=i) for i,t in enumerate(times)]))
        monkeypatch.setattr(main,'stabilize_adaptive_beats',lambda values,sensitivity:values)
    client=TestClient(main.app,headers={'X-MTA-Request':'1'})
    response=client.post(f'/api/projects/{p.id}/metronome-insert',json={'start_ms':6000,'pre_roll_bars':1})
    assert response.status_code==200,response.text
    saved=storage.load_project(p.id)
    c=MusicalClock(saved)
    assert saved.musical_origin_ms==4000
    assert c.format(4000)=='1:1:1:000'
    assert source.read_bytes()==initial
    assert saved.tracks[0].clips[0].timeline_start_ms==0
    from app.midi_metronome import beats
    assert beats(saved,12000)[0][0]==4000
    if mode=='adaptive':
        assert saved.adaptive_tempo_map[0].time_ms==4000
        assert [x.time_ms for x in saved.adaptive_tempo_map][:4]==[4000,4500,5000,5500]
        assert c.format(7000)=='2:1:1:000'


def test_audio_speed_ratio_is_applied_once_to_click_transport_and_midi(tmp_path):
    import numpy as np
    import soundfile as sf
    from app.audio_engine import generate_metronome_wav
    from app.midi_metronome import beats
    p=Project(id='speed',title='Speed',target='DAW_MIDI',bpm=240,base_bpm=120,metronome_bpm=240,
              musical_origin_ms=0,tracks=[Track(id='audio',name='Audio',filename='a.wav',duration_ms=2500)])
    out=tmp_path/'click.wav'
    generate_metronome_wav(p,out)
    pcm,rate=sf.read(out)
    # Source pulses every500ms render at250ms when the project runs at2x.
    assert np.max(np.abs(pcm[int(.49*rate):int(.54*rate)]))>.5
    assert np.max(np.abs(pcm[int(.24*rate):int(.29*rate)]))==0
    assert [x[0] for x in beats(p,2000)]==[0,500,1000,1500]
    c=MusicalClock(p)
    assert c.quarter_at(500)==1
    assert c.format(500)=='1:2:1:000'
    assert TempoMap(p.model_dump()).position(500)[3]==1
    assert c.time_at_quarter(.5)==250 # an eighth-note quantization point
    script="global.window=global;const {Clock}=require('./app/static/musical_clock.js');require('./app/static/midi_tempo.js');const p=JSON.parse(process.argv[1]),c=new Clock(p),h=new MtaTempoMap(p),r=require('./app/static/timeline_rules.js');console.log(JSON.stringify([c.quarterAt(500),h.ppq(500),r.step({...p,timeline_snap:'beats'},0)]))"
    actual=json.loads(subprocess.check_output(['node','-e',script,p.model_dump_json()],text=True))
    assert actual==[1,1,500]


def test_audible_smf_matches_stretched_audio_but_own_import_restores_source_time():
    import io
    import mido
    p=Project(id='stretch',title='Stretch',target='DAW_MIDI',bpm=240,base_bpm=120,musical_origin_ms=500)
    t=Track(id='keys',name='Keys',filename='keys.wav',kind='midi',duration_ms=3000,
            midi_notes=[MidiNote(id='n',pitch=60,start_ms=1000,duration_ms=500)],clips=[Clip(id='all',source_end_ms=3000)])
    data=write_parts([t],file_type=1,project=p)
    external=mido.MidiFile(file=io.BytesIO(data))
    at=0;note_on=None;note_off=None
    for message in external:
        at+=message.time
        if message.type=='note_on' and message.velocity:note_on=at
        if message.type=='note_off':note_off=at
    assert note_on==pytest.approx(.5)
    assert note_off==pytest.approx(.75)
    recovered=read_parts(data)[0]['notes'][0]
    assert recovered.start_ms==pytest.approx(1000)
    assert recovered.duration_ms==pytest.approx(500)
    t.midi_meta=read_parts(data)[0]['midi_meta']
    p.bpm=360
    reexported=write_parts([t],file_type=1,project=p)
    # SMF tempo is integer microseconds/quarter: 3x has a 2us round-trip error.
    assert read_parts(reexported)[0]['notes'][0].start_ms==pytest.approx(1000,abs=.01)
    p.bpm=240
    source_data=write_parts([t],file_type=1,project=p,time_domain='source')
    external=mido.MidiFile(file=io.BytesIO(source_data));at=0
    for message in external:
        at+=message.time
        if message.type=='note_on' and message.velocity:assert at==pytest.approx(1.)


def test_auto_display_distinguishes_placeholder_from_known_tempo():
    code="""const fs=require('fs'),vm=require('vm');const text=fs.readFileSync('app/static/app.js','utf8'),start=text.indexOf('function musicalTransportMode()'),end=text.indexOf('function transportMusicalPosition',start);const c={current:{bpm:120,base_bpm:null,tempo_known:false,transport_time_mode:'auto'}};vm.createContext(c);vm.runInContext(text.slice(start,end),c);if(c.musicalTransportMode())throw Error('Placeholder is not estimated tempo');c.current.tempo_known=true;if(!c.musicalTransportMode())throw Error('Manual/estimated tempo');c.current.transport_time_mode='time';if(c.musicalTransportMode())throw Error('Explicit time wins');c.current={bpm:120,base_bpm:120,transport_time_mode:'auto'};if(!c.musicalTransportMode())throw Error('Legacy known base tempo')"""
    subprocess.run(['node','-e',code],check=True)


def test_midi_only_metronome_sets_preroll_origin_atomically(tmp_path,monkeypatch):
    import app.main as main
    import app.storage as storage
    from fastapi.testclient import TestClient
    monkeypatch.setattr(storage,'ROOT',tmp_path)
    monkeypatch.setenv('MTA_ALLOW_INSECURE_NO_AUTH','true')
    p=storage.create_project('MIDI click',target='MIDI')
    p.timeline_end_ms=10000
    storage.save_project(p)
    client=TestClient(main.app,headers={'X-MTA-Request':'1'})
    result=client.post(f'/api/projects/{p.id}/midi',json={'name':'Click','midi_metronome':{},'duration_ms':10000,'metronome_insertion_ms':6000,'metronome_pre_roll_bars':1})
    assert result.status_code==200,result.text
    saved=storage.load_project(p.id)
    assert saved.musical_origin_ms==4000
    assert all(t.kind=='midi' for t in saved.tracks)
    assert saved.tracks[0].midi_notes[0].start_ms==4000
    assert MusicalClock(saved).format(4000)=='1:1:1:000'
