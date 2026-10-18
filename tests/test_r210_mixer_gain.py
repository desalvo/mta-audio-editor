"""Input trim is independent, persistent, pre-FX and applied exactly once."""
from pathlib import Path
import subprocess

import numpy as np
import pytest
import soundfile as sf
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app import main, storage, audio_engine
from app.models import Track, InsertPlugin
from test_r210_decimal_bpm_shortcuts import function


def node(*names,setup='',check=''):
    code="const assert=require('assert/strict');\n"+setup+'\n'+'\n'.join(function(n) for n in names)+'\n'+check
    return subprocess.run(['node','-e',code],check=True,capture_output=True,text=True)


@pytest.mark.parametrize('value',[float('inf'),float('nan'),25,-25])
def test_gain_rejects_nonfinite_or_out_of_range(value):
    with pytest.raises(ValidationError):Track(id='t',name='T',filename='t.wav',gain_db=value)


def test_old_projects_default_to_unity_gain():
    assert Track(id='t',name='T',filename='t.wav').gain_db==0


@pytest.fixture
def project(tmp_path,monkeypatch):
    monkeypatch.setattr(storage,'ROOT',tmp_path);monkeypatch.setenv('MTA_ALLOW_INSECURE_NO_AUTH','true')
    p=storage.create_project('Input trim');p.bpm=p.base_bpm=120
    track=Track(id='tone',name='Tone',filename='tone.wav',duration_ms=500,channels=1)
    p.tracks=[track];storage.save_project(p)
    wave=.1*np.sin(2*np.pi*440*np.arange(22050)/44100)
    sf.write(storage.audio_path(p.id,'tone.wav'),wave,44100,subtype='FLOAT')
    return TestClient(main.app,headers={'X-MTA-Request':'1'}),p,track,wave


def peak(path):return np.max(np.abs(sf.read(path)[0]))


def test_save_reopen_and_duplicate_preserve_independent_gain(project):
    client,p,t,_=project;data=p.model_dump(mode='json');data['tracks'][0]['gain_db']=6.3;data['tracks'][0]['volume_db']=-9
    response=client.put(f'/api/projects/{p.id}',json=data);assert response.status_code==200,response.text
    track=client.get(f'/api/projects/{p.id}').json()['tracks'][0]
    assert track['gain_db']==6.3 and track['volume_db']==-9
    duplicate=t.model_copy(deep=True);duplicate.gain_db=6.3
    assert Track.model_validate_json(duplicate.model_dump_json()).gain_db==6.3


def test_track_and_mix_exports_apply_gain_exactly_once(project,tmp_path):
    _,p,t,wave=project;t.gain_db=6;t.volume_db=-3;p.master_volume_db=0
    source=storage.audio_path(p.id,t.filename)
    dry=tmp_path/'render.wav';audio_engine.render_track(t,source,dry)
    assert peak(dry)/np.max(np.abs(wave))==pytest.approx(10**(6/20),rel=.002)
    t.gain_db=0
    baseline=tmp_path/'export-base.wav';audio_engine.render_track_export(t,source,baseline,fmt='wav',project=p)
    mixbase=tmp_path/'mix-base.wav';audio_engine.render_mix(p,storage.audio_path,mixbase,fmt='wav')
    t.gain_db=6
    out=tmp_path/'export.wav';audio_engine.render_track_export(t,source,out,fmt='wav',project=p)
    assert peak(out)/peak(baseline)==pytest.approx(10**(6/20),rel=.002)
    out=tmp_path/'mix.wav';audio_engine.render_mix(p,storage.audio_path,out,fmt='wav')
    assert peak(out)/peak(mixbase)==pytest.approx(10**(6/20),rel=.005)


def test_gain_precedes_nonlinear_insert(project,tmp_path):
    _,p,t,_=project;t.gain_db=24;t.inserts=[InsertPlugin(id='limit',plugin='limiter',preset='default')]
    out=tmp_path/'limited.wav';audio_engine.render_track(t,storage.audio_path(p.id,t.filename),out)
    assert .85<peak(out)<.92  # pre-gain drives limiter, not a clipped post-limiter boost


@pytest.mark.parametrize('render,inserts,gain_baked',[(False,False,False),(True,False,False),(False,True,False),(True,True,True)])
def test_preview_bakes_gain_only_before_enabled_inserts(project,monkeypatch,render,inserts,gain_baked):
    client,p,t,_=project;t.gain_db=6
    if inserts:t.inserts=[InsertPlugin(id='fx',plugin='amplify',preset='default')]
    storage.save_project(p);seen=[]
    def preview(track,source,out,**kwargs):
        seen.append(track.gain_db);sf.write(out,np.zeros(100),44100)
    monkeypatch.setattr(main,'render_track_export',preview)
    response=client.get(f'/api/projects/{p.id}/preview-track/{t.id}?render={str(render).lower()}')
    assert response.status_code==200,response.text
    assert seen==[6 if gain_baked else 0]
    p=storage.load_project(p.id);p.tracks[0].gain_db=9;storage.save_project(p)
    response=client.get(f'/api/projects/{p.id}/preview-track/{t.id}?render={str(render).lower()}')
    assert response.status_code==200
    assert seen==([6,9] if gain_baked else [0])


def test_actual_js_live_gain_and_baked_buffers_do_not_double_apply():
    node('normalizeTrackGain','trackGainDb','dbToGain','waTrackGain','playbackGainForTrack','trackGainBaked',
         setup="let current={master_volume_db:-2};function trackAudibleNow(t){return !t.mute}",
         check="""const track={gain_db:6,volume_db:-3,inserts:[{enabled:true}]};
assert.equal(trackGainBaked(track,true),true);assert.equal(trackGainBaked(track,false),false);
assert.equal(waTrackGain(track),dbToGain(3));assert.equal(waTrackGain(track,{gainBaked:true}),dbToGain(-3));
assert.equal(playbackGainForTrack(track),dbToGain(1));assert.equal(playbackGainForTrack(track,{gainBaked:true}),dbToGain(-5));
track.mute=true;assert.equal(waTrackGain(track),0);assert.equal(playbackGainForTrack(track),0);
assert.equal(normalizeTrackGain('6,3'),6.3);assert.equal(normalizeTrackGain(''),null);assert.equal(normalizeTrackGain('NaN'),null);
assert.equal(normalizeTrackGain(100),24);assert.equal(normalizeTrackGain(-100),-24);
""")


def test_setter_keeps_fader_and_saves_rebuilds_only_processed_audio():
    node('normalizeTrackGain','trackGainDb','trackGainBaked','setTrackGain',setup="""
let track={id:'t',gain_db:0,volume_db:-9,inserts:[]},current={id:'p'},waPlaybackActive=true,waRenderFilters=true,renderedStemPlayback=true,renderedMasterPlayback=false,trackPlaybacks=[],fx=0,dirty=0,live=0;
function trackById(){return track}function updateTrackGainUi(){}function markDirty(){dirty++}function invalidateTrackAudioCache(){}function clearPlaybackWarmCache(){}function updatePlaybackGains(){live++}function queueLiveFxRefresh(){fx++}
""",check="""setTrackGain('t',6.3);assert.equal(track.gain_db,6.3);assert.equal(track.volume_db,-9);assert.equal(fx,0);assert.equal(dirty,1);assert.equal(live,1);
track.inserts=[{enabled:true}];trackPlaybacks=[{trackId:'t',gainBaked:true}];waRenderFilters=false;setTrackGain('t',-2);assert.equal(fx,1);assert.equal(track.volume_db,-9);
setTrackGain('t','NaN');assert.equal(track.gain_db,-2);assert.equal(dirty,2);
""")


def test_keyboard_drag_cancel_and_control_markup():
    r=node('normalizeTrackGain','trackGainDb','trackGainKey','startTrackGainDrag','trackGainControlHtml',setup="""
let current={id:'p'},track={id:'t',name:'Tone',gain_db:0},listeners={};const window={addEventListener:(n,f)=>listeners[n]=f,removeEventListener:n=>delete listeners[n]};
function trackById(){return track}function setTrackGain(id,v){track.gain_db=normalizeTrackGain(v)}function esc(s){return s}function tr(en){return en}
""",check="""const event=key=>({key,preventDefault(){},stopPropagation(){}});
trackGainKey(event('ArrowUp'),'t');assert.equal(track.gain_db,.1);trackGainKey({...event('ArrowRight'),shiftKey:true},'t');assert.equal(track.gain_db,1.1);
trackGainKey(event('0'),'t');assert.equal(track.gain_db,0);
startTrackGainDrag({button:0,pointerId:1,clientX:50,clientY:50,preventDefault(){},stopPropagation(){}},'t');
listeners.pointermove({pointerId:1,clientX:70,clientY:40});assert.equal(track.gain_db,6);
listeners.pointercancel();assert.equal(Object.keys(listeners).length,0);
console.log(trackGainControlHtml(track));
""")
    html=r.stdout
    for text in ['Gain · dB','role="slider"','type="number"','min="-24"','max="24"','step="0.1"','ondblclick="resetTrackGain']:
        assert text in html


def test_gain_knob_has_own_keyboard_scope_and_pre_fx_cache_key():
    js=Path('app/static/app.js').read_text()
    assert "e.target?.closest?.('.gain-knob')" in js
    assert 'trackGainBaked(track,renderFilters)?trackGainDb(track):0' in js
    assert 'waTrackGain(t,item)' in js and 'waCreateTrackGraph(t,buffers[i],renderFilters)' in js
