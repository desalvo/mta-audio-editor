"""Audible master inserts and non-destructive track/master bounce PCM tests."""
import subprocess
import time
import numpy as np
import pytest
import soundfile as sf
from fastapi.testclient import TestClient
from app import storage,main,audio_engine
from app.models import Track,Clip,InsertPlugin
from app.bounce import bounce


@pytest.fixture
def project(tmp_path,monkeypatch):
    monkeypatch.setattr(storage,'ROOT',tmp_path/'projects');storage.ROOT.mkdir()
    monkeypatch.setenv('MTA_ALLOW_INSECURE_NO_AUTH','true')
    p=storage.create_project('Bounce',target='DAW',sample_rate=48000)
    p.bpm=p.base_bpm=120
    samples=.1*np.sin(2*np.pi*440*np.arange(48000)/48000)
    sf.write(storage.audio_path(p.id,'tone.wav'),np.column_stack([samples,samples]),48000,subtype='FLOAT')
    p.tracks=[Track(id='tone',name='Tone',filename='tone.wav',channels=2,duration_ms=1000,sample_rate=48000,clips=[Clip(id='c',source_end_ms=1000)])]
    storage.save_project(p)
    return p


def rms(path):return float(np.sqrt(np.mean(sf.read(path,always_2d=True)[0]**2)))


def test_master_insert_applies_once_to_summed_audio(project,tmp_path):
    dry=tmp_path/'dry.wav';wet=tmp_path/'wet.wav'
    audio_engine.render_mix(project,storage.audio_path,dry,fmt='wav',wav_bit_depth=32)
    project.master_inserts=[InsertPlugin(id='masterfx',plugin='amplify',preset='minus-12db')]
    audio_engine.render_mix(project,storage.audio_path,wet,fmt='wav',wav_bit_depth=32)
    assert rms(wet)/rms(dry)==pytest.approx(10**(-12/20),rel=.01)


def test_track_bounce_bakes_gain_fader_pan_delay_inserts_and_persists(project):
    source=project.tracks[0];source.gain_db=3;source.volume_db=-6;source.pan=-1;source.delay_ms=200
    source.inserts=[InsertPlugin(id='fx',plugin='amplify',preset='minus-3db')]
    storage.save_project(project);before=storage.audio_path(project.id,source.filename).read_bytes()
    result=bounce(project.id,source.id);loaded=storage.load_project(project.id)
    t=next(t for t in loaded.tracks if t.id==result['track_id'])
    assert t.mute and not t.inserts and t.gain_db==0 and t.volume_db==0 and t.pan==0 and t.delay_ms==0
    data,rate=sf.read(storage.audio_path(project.id,t.filename),always_2d=True)
    assert rate==48000 and len(data)>=57000
    assert np.max(np.abs(data[:9000]))==0
    assert np.max(np.abs(data[:,1]))<1e-6
    assert np.max(np.abs(data[:,0]))==pytest.approx(.1*10**(-6/20),rel=.02)
    assert storage.audio_path(project.id,source.filename).read_bytes()==before
    assert loaded.tracks[0].model_dump()==source.model_dump()
    again=bounce(project.id,source.id)
    names=[x.name for x in storage.load_project(project.id).tracks]
    assert len(names)==len(set(names))
    assert again['track_id']!=t.id


def test_master_bounce_is_post_master_not_double_processed(project,tmp_path):
    project.master_volume_db=-3;project.master_inserts=[InsertPlugin(id='m',plugin='amplify',preset='minus-6db')]
    storage.save_project(project)
    original=tmp_path/'original.wav';audio_engine.render_mix(project,storage.audio_path,original,fmt='wav',wav_bit_depth=32)
    result=bounce(project.id);loaded=storage.load_project(project.id)
    t=next(t for t in loaded.tracks if t.id==result['track_id']);assert t.master_bypass and t.mute
    t.mute=False;loaded.tracks[0].mute=True
    after=tmp_path/'bounce-only.wav';audio_engine.render_mix(loaded,storage.audio_path,after,fmt='wav',wav_bit_depth=32)
    assert rms(after)==pytest.approx(rms(original),rel=.01)


def test_failed_bounce_leaves_no_track_or_orphan(project,monkeypatch):
    import app.bounce as service
    before=set(storage.audio_path(project.id,'tone.wav').parent.iterdir())
    def fail(*a,**kw):raise RuntimeError('Bad insert')
    monkeypatch.setattr(service,'render_track_export',fail)
    with pytest.raises(RuntimeError):bounce(project.id,'tone')
    assert len(storage.load_project(project.id).tracks)==1
    assert set(storage.audio_path(project.id,'tone.wav').parent.iterdir())==before


def test_bounce_capacity_failure_does_not_publish(project):
    def denied(*a):raise ValueError('Quota exceeded')
    with pytest.raises(ValueError,match='Quota'):bounce(project.id,'tone',capacity_check=denied)
    assert len(storage.load_project(project.id).tracks)==1


def test_background_bounce_endpoint_finishes_and_authenticates(project):
    client=TestClient(main.app,headers={'X-MTA-Request':'1'})
    result=client.post(f'/api/projects/{project.id}/tracks/tone/bounce')
    assert result.status_code==200,result.text
    job=result.json()['bounce_job_id']
    for _ in range(150):
        state=client.get('/api/media-jobs/'+job).json()
        if state['status'] not in ('queued','running'):break
        time.sleep(.03)
    assert state['status']=='completed',state
    assert len(storage.load_project(project.id).tracks)==2
    assert client.post(f'/api/projects/{project.id}/tracks/missing/bounce').status_code==404


def test_master_preview_is_wet_wav_and_cleans_temporary(project):
    project.master_inserts=[InsertPlugin(id='m',plugin='amplify',preset='minus-12db')];storage.save_project(project)
    client=TestClient(main.app)
    response=client.get(f'/api/projects/{project.id}/preview-mix?format=wav&full_master=true')
    assert response.status_code==200,response.text
    import io
    data,rate=sf.read(io.BytesIO(response.content));assert rate==48000
    assert np.max(np.abs(data))==pytest.approx(.1*10**(-12/20),rel=.02)


def test_bounce_shortcut_ignores_inputs_modifiers_and_repeat():
    from test_r210_decimal_bpm_shortcuts import function
    code="""const assert=require('assert');let current={id:'p'},selectedTrackId='t',calls=[];
const document={querySelector(){return null}},trackById=id=>({id});function closeTrackContextMenu(){}function bounceToTrack(id){calls.push(id)};
"""+function('handleBounceShortcut')+"""
const event=()=>({key:'b',target:{closest(){return null}},preventDefault(){},stopPropagation(){}});
assert.equal(handleBounceShortcut(event()),true);assert.deepEqual(calls,['t']);
for(const value of ['ctrlKey','metaKey','altKey','shiftKey','repeat'])assert.equal(handleBounceShortcut({...event(),[value]:true}),false);
assert.equal(handleBounceShortcut({...event(),target:{closest(){return {}}}}),false);
"""
    subprocess.run(['node','-e',code],check=True)


def test_master_limiter_receives_the_sum_before_master_fader(project,tmp_path):
    samples=.8*np.sin(2*np.pi*440*np.arange(48000)/48000)
    sf.write(storage.audio_path(project.id,'tone.wav'),np.column_stack([samples,samples]),48000,subtype='FLOAT')
    second=project.tracks[0].model_copy(deep=True);second.id='second';second.clips[0].id='second-clip'
    project.tracks.append(second)
    project.master_inserts=[InsertPlugin(id='limit',plugin='limiter')]
    project.master_volume_db=-3
    out=tmp_path/'limited.wav'
    audio_engine.render_mix(project,storage.audio_path,out,fmt='wav',wav_bit_depth=32)
    data,_=sf.read(out)
    assert np.max(np.abs(data))==pytest.approx(.891*10**(-3/20),rel=.02)


def test_master_vst_processes_summed_signal_once(project,tmp_path,monkeypatch):
    from app import vst3_host
    second=project.tracks[0].model_copy(deep=True);second.id='second';second.clips[0].id='second-clip';project.tracks.append(second)
    plugin=tmp_path/'test.vst3';plugin.mkdir()
    project.master_inserts=[InsertPlugin(id='vst',plugin='vst3',params={'path':str(plugin)})]
    monkeypatch.setattr(vst3_host,'validate_plugin_path',lambda value:plugin)
    real_run=audio_engine.subprocess.run;seen=[]
    def run(args,**kwargs):
        if 'app.vst3_host' in args:
            index=args.index('--process');source,dest=args[index+1:index+3]
            data,rate=sf.read(source,always_2d=True);seen.append(np.max(np.abs(data)))
            sf.write(dest,data*.5,rate,subtype='FLOAT')
            return subprocess.CompletedProcess(args,0,'','')
        return real_run(args,**kwargs)
    monkeypatch.setattr(audio_engine.subprocess,'run',run)
    out=tmp_path/'vst.wav';audio_engine.render_mix(project,storage.audio_path,out,fmt='wav',wav_bit_depth=32)
    assert len(seen)==1 and seen[0]==pytest.approx(.2,rel=.01)
    assert np.max(np.abs(sf.read(out)[0]))==pytest.approx(.1,rel=.01)


def test_concurrent_audio_change_rejects_bounce_but_preserves_other_edits(project,monkeypatch):
    import app.bounce as service
    original=service.render_track_export
    def change(*args,**kwargs):
        original(*args,**kwargs)
        latest=storage.load_project(project.id);latest.tracks[0].gain_db=4;storage.save_project(latest)
    monkeypatch.setattr(service,'render_track_export',change)
    with pytest.raises(ValueError,match='changed'):bounce(project.id,'tone')
    loaded=storage.load_project(project.id)
    assert len(loaded.tracks)==1 and loaded.tracks[0].gain_db==4


def test_webaudio_master_mode_fetches_full_mix_without_double_fader():
    from pathlib import Path
    from test_r210_decimal_bpm_shortcuts import function
    source=Path('app/static/app.js').read_text()
    # Extract the active (last) declarations, not the obsolete compatibility player.
    start=source.index('function waBuildMasterGraph()');end=source.index('function waScheduleItem(',start)
    graph=source[start:end]
    setup="""const assert=require('assert');let waMasterBus,masterPlaybackGainNode,masterMeterAnalysers,waMasterMixMode=true,current={master_volume_db:-12};
const audioCtx={createGain(){return {gain:{value:0},connect(){}}},destination:{}};
"""
    check="""waBuildMasterGraph();assert.equal(masterPlaybackGainNode.gain.value,1);
waMasterMixMode=false;waBuildMasterGraph();assert.ok(Math.abs(masterPlaybackGainNode.gain.value-Math.pow(10,-12/20))<1e-8);"""
    subprocess.run(['node','-e',setup+'\nfunction dbToGain(v){return Math.pow(10,v/20)}\n'+graph+check],check=True)
    decode=function('waDecodeMasterMix')
    setup="""const assert=require('assert');let url,waRenderFilters=false,current={id:'p'};
async function persistCurrentProject(){}function tr(en){return en}
const audioCtx={async decodeAudioData(){return 'buffer'}};
async function fetch(value){url=value;return {ok:true,async arrayBuffer(){return new ArrayBuffer(1)}}}
"""
    subprocess.run(['node','-e',setup+decode+"""
(async()=>{assert.equal(await waDecodeMasterMix(false),'buffer');assert.ok(url.includes('format=wav'));assert.ok(url.includes('full_master=true'));assert.ok(url.includes('render_tracks=false'))})().catch(e=>{console.error(e);process.exitCode=1});
"""],check=True)


def test_context_menu_categories_keep_all_actions_and_shortcuts():
    from test_r210_decimal_bpm_shortcuts import function
    setup="""const assert=require('assert');let html='',selectedTrackId,selectedTrackIdSet=new Set(),current={tracks:[]},playCursorMs=0;
const trackById=()=>({id:'t',type:'click'}),pluginInfo={stem_splitter:{available:true}},window={innerWidth:1000,innerHeight:800};
function closeTrackContextMenu(){}function isGeneratedChordsTrack(){return false}function tr(en){return en}const $$=()=>[];
const document={createElement(){return {setAttribute(){},addEventListener(){},focus(){},getBoundingClientRect(){return {width:200,height:300}},style:{},set innerHTML(value){html=value}}},body:{appendChild(){}}};
"""
    check="""openTrackContextMenuAt('t',900,700);
assert.equal((html.match(/<details/g)||[]).length,4);
for(const action of ['duplicateTrack','renameTrack','bounceToTrack','openTrackStemWorkflow','openAiRemixPanel','openSampleEditor','recalculateBpmFromTrack','openTextAnalysisChooser','extractMarkersFromTrack','openMetronomeSettings','refreshGeneratedTrackFromContext','openTrackDelayDialog','addTimelineChordAtPlayhead','addTimelineMarkerAtPlayhead','deleteSelection','deleteTracksByIds'])assert.ok(html.includes(action),action);
assert.ok(html.includes('aria-keyshortcuts="B"'));
"""
    subprocess.run(['node','-e',setup+function('openTrackContextMenuAt')+check],check=True)
