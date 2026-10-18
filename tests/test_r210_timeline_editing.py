import json
import shutil
import subprocess
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf
from fastapi.testclient import TestClient

from app.models import Project, Track, Clip, Marker
from app.audio_engine import ensure_clips, render_mix, render_track, project_duration_ms, project_time_pitch_filter
from app.timeline_editing import unique_track_name, validate_new_overlaps, prepare_metronome_insert, trim_project, audible_bounds


def project(start=0, delay=0, length=2000):
    return Project(id='test', title='Test', bpm=120, tracks=[Track(id='t', name='Drums', filename='a.wav', duration_ms=length, delay_ms=delay, clips=[Clip(id='c', source_start_ms=0, source_end_ms=length, timeline_start_ms=start)])])


def test_stem_names_are_case_insensitive_and_numbered():
    p = project()
    p.tracks.append(p.tracks[0].model_copy(update={'id': 'x', 'name': 'drums 2'}))
    assert unique_track_name(p, 'Drums') == 'Drums 3'
    assert unique_track_name(p, 'Bass') == 'Bass'


def test_overlap_guard_preserves_legacy_but_rejects_new_or_changed():
    p = project()
    p.tracks[0].clips.append(Clip(id='d', source_end_ms=1000, timeline_start_ms=1000))
    validate_new_overlaps(p, p.model_copy(deep=True))
    q = p.model_copy(deep=True)
    q.tracks[0].clips[1].timeline_start_ms = 1100
    with pytest.raises(ValueError):
        validate_new_overlaps(p, q)
    q.tracks[0].clips[1].timeline_start_ms = 2000
    validate_new_overlaps(p, q)


def test_preroll_extends_and_shifts_audio_and_events():
    p = project()
    p.markers = [Marker(time_ms=200, label='Verse')]
    q, extra = prepare_metronome_insert(p, 500, 2)
    assert extra == 3500
    assert q.tracks[0].clips[0].timeline_start_ms == 3500
    assert q.markers[0].time_ms == 3700
    assert q.metronome_start_ms == 0
    assert q.metronome_insertion_ms == 4000
    assert p.tracks[0].clips[0].timeline_start_ms == 0


@pytest.mark.parametrize('start,bars', [(-1, 1), (0, -1), (0, 65), (1.1, 0), (False, 0)])
def test_preroll_validates_input(start, bars):
    with pytest.raises(ValueError):
        prepare_metronome_insert(project(), start, bars)


def test_trim_bakes_delay_and_preserves_intentionally_empty_tracks():
    p = project(start=400, delay=-100)
    p.tracks.append(Track(id='other', name='Other', filename='b.wav', duration_ms=200, clips=[Clip(id='d', source_end_ms=200)]))
    q = trim_project(p, 500, 1800)
    assert q.tracks[0].delay_ms == 0
    assert q.tracks[0].clips[0].source_start_ms == 200
    assert q.tracks[0].clips[0].source_end_ms == 1500
    reloaded = Project.model_validate_json(q.model_dump_json())
    ensure_clips(reloaded.tracks[1])
    assert reloaded.tracks[1].clips == []
    assert project_duration_ms(reloaded) == 1300


@pytest.mark.skipif(not shutil.which('ffmpeg'), reason='FFmpeg required')
def test_actual_audio_delay_fades_and_trim(tmp_path):
    rate = 44100
    sf.write(tmp_path/'a.wav', np.full(rate*2, .4), rate, subtype='FLOAT')
    p = project(start=100, delay=200)
    render_track(p.tracks[0], tmp_path/'a.wav', tmp_path/'track.wav')
    audio, sr = sf.read(tmp_path/'track.wav', always_2d=True)
    assert np.max(abs(audio[:int(sr*.29)])) == 0
    assert np.max(abs(audio[int(sr*.31):int(sr*.4)])) > .1
    p.master_fade_enabled, p.master_fade_in_ms, p.master_fade_out_ms = True, 500, 500
    render_mix(p, lambda pid, name: tmp_path/name, tmp_path/'mix.wav', fmt='wav', wav_bit_depth=32)
    audio, sr = sf.read(tmp_path/'mix.wav', always_2d=True)
    assert abs(audio[int(sr*.35), 0]) < abs(audio[int(sr*.8), 0])
    assert abs(audio[-1, 0]) < .0001
    assert audible_bounds(p, lambda pid, name: tmp_path/name) == (300, 2300)
    assert project_time_pitch_filter(project()) == 'anull'


def test_rules_group_snap_magnets_and_collision():
    node = shutil.which('node')
    if not node:
        pytest.skip('Node required')
    code = '''const assert=require('assert'),R=require('./app/static/timeline_rules.js');
const c=(id,s,n=1000)=>({id,timeline_start_ms:s,source_start_ms:0,source_end_ms:n});
const p={bpm:120,time_signature:'4/4',timeline_snap:'off',tracks:[{id:'a',clips:[c('x',1000),c('wall',4000)]},{id:'b',clips:[c('y',2000)]}]};
const keys=new Set(['a:x','b:y']);assert.equal(R.delta(p,keys,9999),2000);assert.equal(R.delta(p,keys,-9999),-1000);
p.timeline_snap='beats';assert.equal(R.delta(p,keys,620),500);
p.timeline_snap='off';p.timeline_magnetic=true;assert.equal(R.delta(p,new Set(['a:x']),1950,100),2000);
p.timeline_magnetic=false;assert.equal(R.delta(p,new Set(['a:x']),1950,100),1950);
p.timeline_snap='bars';assert.equal(R.delta(p,keys,900),1000);
p.master_fade_enabled=true;p.master_fade_in_ms=1000;p.master_fade_out_ms=1000;assert.equal(R.fade(p,500),.5);assert.equal(R.fade(p,5000),0);
'''
    subprocess.run([node, '-e', code], check=True, capture_output=True, text=True)


def test_insert_endpoint_extends_then_generates_at_correct_sample(tmp_path, monkeypatch):
    import app.main as main
    import app.storage as storage
    monkeypatch.setattr(storage, 'ROOT', tmp_path)
    monkeypatch.setenv('MTA_ALLOW_INSECURE_NO_AUTH', 'true')
    p = storage.create_project('Metronome')
    p.tracks = project().tracks
    storage.save_project(p)
    client = TestClient(main.app, headers={'X-MTA-Request': '1'})
    response = client.post(f'/api/projects/{p.id}/metronome-insert', json={'start_ms': 500, 'pre_roll_bars': 1})
    assert response.status_code == 200, response.text
    saved = storage.load_project(p.id)
    assert saved.metronome_insertion_ms == 2000
    assert saved.tracks[0].clips[0].timeline_start_ms == 1500
    assert response.json()['project_extended_ms'] == 1500
    assert response.json()['track']['type'] == 'click'
    assert client.post(f'/api/projects/{p.id}/metronome-insert', json={'start_ms': 0, 'pre_roll_bars': -1}).status_code == 400


def test_insert_failure_rolls_back_project(tmp_path, monkeypatch):
    import app.main as main
    import app.storage as storage
    from fastapi import HTTPException
    monkeypatch.setattr(storage, 'ROOT', tmp_path)
    monkeypatch.setenv('MTA_ALLOW_INSECURE_NO_AUTH', 'true')
    p = storage.create_project('Rollback')
    p.tracks = project().tracks
    storage.save_project(p)
    before = json.loads(storage.load_project(p.id).model_dump_json())
    def fail(*args, **kwargs):
        raise HTTPException(400, 'generation failed')
    monkeypatch.setattr(main, '_create_metronome_track_locked', fail)
    client = TestClient(main.app, headers={'X-MTA-Request': '1'})
    response = client.post(f'/api/projects/{p.id}/metronome-insert', json={'start_ms': 0, 'pre_roll_bars': 2})
    assert response.status_code == 400
    after = json.loads(storage.load_project(p.id).model_dump_json())
    assert after == before


def test_fade_and_timeline_options_persist():
    p = project()
    p.master_fade_enabled, p.master_fade_in_ms, p.master_fade_out_ms = True, 123, 456
    p.timeline_snap, p.timeline_magnetic = 'bars', True
    q = Project.model_validate_json(p.model_dump_json())
    assert (q.master_fade_enabled, q.master_fade_in_ms, q.master_fade_out_ms, q.timeline_snap, q.timeline_magnetic) == (True, 123, 456, 'bars', True)


def test_timeline_js_and_template_are_valid():
    source = Path('app/templates/index.html').read_text()
    assert source.index('/static/timeline_rules.js') < source.index('/static/app.js')
    subprocess.run(['node', '--check', 'app/static/app.js'], check=True, capture_output=True)


def test_actual_pointer_group_drag_cancel_and_history():
    code = r'''const fs=require('fs'),vm=require('vm'),assert=require('assert');
const source=fs.readFileSync('app/static/app.js','utf8');
const listeners={},clip=(id,s)=>({id,timeline_start_ms:s,source_start_ms:0,source_end_ms:1000});
const p={id:'p',bpm:120,timeline_snap:'beats',tracks:[{id:'a',clips:[clip('x',1000),clip('wall',4000)]},{id:'b',clips:[clip('y',2000)]}]};
const cls={toggle(){},add(){},remove(){}},elements=[];
for(const t of p.tracks)for(const c of t.clips)elements.push({dataset:{trackId:t.id,clipId:c.id},style:{},classList:cls});
const context={console,current:p,timelineAudioRevision:0,timelineTool:'select',selectedTimelineSegments:new Set(),selectedTrackIdSet:new Set(),pxPerSec:100,history:0,focusCount:0,render(){},markDirty(){},invalidateTrackAudioCache(){},clearPlaybackWarmCache(){},waPlaybackActive:false,waPlaybackPaused:false,updateSel(){},cancelTrackContextLongPress(){},drawWave(){},checkpointHistory(){context.history++},CSS:{escape:x=>x},document:{body:{classList:cls},querySelectorAll:()=>elements,querySelector:()=>null,getElementById:()=>({focus(){context.focusCount++}})},window:{addEventListener:(n,f)=>listeners[n]=f,removeEventListener:n=>delete listeners[n]},MtaTimelineRules:require('./app/static/timeline_rules.js')};
context.trackById=id=>p.tracks.find(t=>t.id===id);vm.createContext(context);
vm.runInContext(source.slice(source.indexOf('function focusTrackShortcuts('),source.indexOf('function handleGeneratedTrackShortcut(')),context);
vm.runInContext(source.slice(source.indexOf('function paintSegmentSelection(){'),source.indexOf('function refreshTimelineToolControls(){')),context);
function click(t,c,multi=false){context.beginTimelineClipDrag({button:0,pointerId:1,clientX:0,preventDefault(){},stopPropagation(){},ctrlKey:multi},t,c);if(listeners.pointerup)listeners.pointerup({pointerId:1})}
click('a','x');click('b','y',true);assert.equal(context.selectedTimelineSegments.size,2);assert.equal(context.focusCount,2);
context.beginTimelineClipDrag({button:0,pointerId:1,clientX:0,preventDefault(){},stopPropagation(){}},'a','x');
listeners.pointermove({pointerId:1,clientX:60,preventDefault(){}});assert.equal(p.tracks[0].clips[0].timeline_start_ms,1000);assert.equal(context.history,0);
listeners.pointerup({pointerId:1});assert.equal(p.tracks[0].clips[0].timeline_start_ms,1500);assert.equal(p.tracks[1].clips[0].timeline_start_ms,2500);assert.equal(context.history,1);
context.beginTimelineClipDrag({button:0,pointerId:1,clientX:0,preventDefault(){},stopPropagation(){}},'a','x');listeners.pointermove({pointerId:1,clientX:50,preventDefault(){}});listeners.pointercancel({pointerId:1});assert.equal(p.tracks[0].clips[0].timeline_start_ms,1500);assert.equal(context.history,1);
click('b','y',true);assert.equal(context.selectedTimelineSegments.size,1);
context.moveSelectedSegments(500);assert.equal(p.tracks[0].clips[0].timeline_start_ms,2000);assert.equal(p.tracks[1].clips[0].timeline_start_ms,2500);
'''
    subprocess.run(['node', '-e', code], check=True, capture_output=True, text=True)


def test_trim_endpoint_persists_audio_bounds_and_checks_project_access(tmp_path, monkeypatch):
    import app.main as main
    import app.storage as storage
    from fastapi import HTTPException
    monkeypatch.setattr(storage, 'ROOT', tmp_path)
    monkeypatch.setenv('MTA_ALLOW_INSECURE_NO_AUTH', 'true')
    p = storage.create_project('Trim')
    p.tracks = project(start=300).tracks
    storage.save_project(p)
    sf.write(storage.audio_path(p.id, 'a.wav'), np.full(44100*2, .3), 44100)
    client = TestClient(main.app, headers={'X-MTA-Request': '1'})
    response = client.post(f'/api/projects/{p.id}/timeline-trim', json={'side': 'left'})
    assert response.status_code == 200, response.text
    assert response.json()['removed_start_ms'] == 300
    assert storage.load_project(p.id).tracks[0].clips[0].timeline_start_ms == 0
    def denied(*args, **kwargs):
        raise HTTPException(403, 'Forbidden')
    monkeypatch.setattr(main, '_project_for_actor', denied)
    assert client.post(f'/api/projects/{p.id}/timeline-trim', json={'side': 'right'}).status_code == 403
    assert client.post(f'/api/projects/{p.id}/metronome-insert', json={'start_ms': 0}).status_code == 403


def test_negative_delay_crops_audio_not_only_the_waveform(tmp_path):
    p = project(delay=-500)
    source = np.r_[np.zeros(44100//2), np.full(44100*3//2, .4)]
    sf.write(tmp_path/'a.wav', source, 44100)
    render_track(p.tracks[0], tmp_path/'a.wav', tmp_path/'negative.wav')
    actual, rate = sf.read(tmp_path/'negative.wav', always_2d=True)
    assert abs(len(actual)/rate-1.5) < .002
    assert actual[20, 0] > .1
    assert project_duration_ms(p) == 1500


def test_master_automation_seek_tempo_and_paused_transport():
    code = r'''const fs=require('fs'),vm=require('vm'),assert=require('assert'),R=require('./app/static/timeline_rules.js');
const s=fs.readFileSync('app/static/app.js','utf8'),events=[];
const c={current:{master_volume_db:0,master_fade_enabled:true,master_fade_in_ms:1000,master_fade_out_ms:1000,timeline_end_ms:4000,tracks:[]},audioCtx:{currentTime:10},masterPlaybackGainNode:{gain:{cancelScheduledValues:t=>events.push(['cancel',t]),setValueAtTime:(v,t)=>events.push(['set',v,t]),linearRampToValueAtTime:(v,t)=>events.push(['ramp',v,t])}},MtaTimelineRules:R,dbToGain:db=>Math.pow(10,db/20),tempoRatio:()=>2,waPlaybackActive:true,waPlaybackPaused:true,paused:0,resumed:0,pausePlayback(){c.paused++},resumePlayback(){c.resumed++}};vm.createContext(c);
vm.runInContext(s.slice(s.indexOf('function scheduleMasterFades('),s.indexOf('function openProjectFade(')),c);
c.scheduleMasterFades(500,10);assert.deepEqual(events[1],['set',.5,10]);assert.deepEqual(events.at(-1),['ramp',0,11.75]);
vm.runInContext(s.slice(s.indexOf('async function togglePlayback(){'),s.indexOf('function seekTransport(',s.indexOf('async function togglePlayback(){'))),c);
c.togglePlayback();assert.equal(c.resumed,1);c.waPlaybackPaused=false;c.togglePlayback();assert.equal(c.paused,1);
'''
    subprocess.run(['node', '-e', code], check=True, capture_output=True, text=True)


def test_loading_audio_retries_if_a_segment_moves_during_decode():
    code = r'''const fs=require('fs'),vm=require('vm'),assert=require('assert'),s=fs.readFileSync('app/static/app.js','utf8');
const c={current:{id:'p',tracks:[{id:'t',delay_ms:1}]},timelineAudioRevision:0,calls:0,saves:0,tr:x=>x,async persistCurrentProject(){c.saves++},async waDecodeTrack(t){const value=t.delay_ms;c.calls++;if(c.calls===1){c.current.tracks[0].delay_ms=2;c.timelineAudioRevision++}return value}};vm.createContext(c);
vm.runInContext(s.slice(s.indexOf('async function prepareTimelinePlaybackBuffers('),s.indexOf('async function startWebAudioProjectPlayback(')),c);
(async()=>{const result=await c.prepareTimelinePlaybackBuffers(false);assert.equal(c.calls,2);assert.equal(c.saves,2);assert.equal(result.buffers[0],2)})().catch(e=>{console.error(e);process.exitCode=1});
'''
    subprocess.run(['node', '-e', code], check=True, capture_output=True, text=True)
