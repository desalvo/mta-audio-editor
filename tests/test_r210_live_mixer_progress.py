"""Regressions for per-plugin activity and persistent C++ mixer playback."""
# ruff: noqa: F811 -- imported pytest fixtures are injected by name
from pathlib import Path
import threading
import time

import numpy as np
import pytest
import soundfile as sf
from fastapi import FastAPI,HTTPException
from fastapi.testclient import TestClient

from app import auth,optional_plugins,cpp_audio,server_vst3
from app.models import Project,Track,Clip
from app.live_mixer import apply
from test_r210_cpp_audio_engine import compiled_core  # noqa: F401

ROOT=Path(__file__).resolve().parents[1]


def project():
    return Project(id='mixer-test',title='Mixer',sample_rate=48000,tracks=[Track(id='tone',name='Tone',filename='tone.wav',channels=2,duration_ms=2000,clips=[Clip(id='clip',source_end_ms=2000)])])


def controls(p):
    return {'tracks':[{'id':t.id,'gain_db':t.gain_db,'volume_db':t.volume_db,'pan':t.pan,'mute':t.mute,'solo':t.solo} for t in p.tracks],'master_volume_db':p.master_volume_db}


def test_plugin_results_are_visible_before_entire_batch_finishes(tmp_path,monkeypatch):
    monkeypatch.setattr(auth,'DATA_ROOT',tmp_path)
    monkeypatch.setenv('MTA_OPTIONAL_VST3_DIR',str(tmp_path/'installed'))
    monkeypatch.setattr(optional_plugins,'_JOBS',{})
    monkeypatch.setattr(optional_plugins,'_LOCK',threading.Lock())
    first=threading.Event();second=threading.Event();release_first=threading.Event();release_second=threading.Event()
    def install(spec,notify):
        if spec['id']=='mverb':
            first.set();assert release_first.wait(5)
            dest=optional_plugins.plugin_root()/spec['id']/spec['revision'];dest.mkdir(parents=True);(dest/'installation.json').write_text('{}')
            return {'id':spec['id'],'bundles':['MVerb.vst3']}
        second.set();assert release_second.wait(5);raise RuntimeError('Compiler unavailable')
    monkeypatch.setattr(optional_plugins,'install_one',install)
    job=optional_plugins.start(['mverb','dragonfly']);identifier=job['id']
    try:
        assert first.wait(5)
        state=optional_plugins.status(identifier)
        assert state['plugins']['mverb']['state']=='installing'
        assert state['plugins']['dragonfly']['state']=='queued'
        assert optional_plugins.catalog()['active_job']==identifier
        release_first.set();assert second.wait(5)
        state=optional_plugins.status(identifier)
        assert state['state']=='running' and state['plugins']['mverb']['state']=='installed'
        assert state['results'][0]['id']=='mverb'
        # A returned snapshot cannot mutate the running job.
        state['plugins']['mverb']['state']='bad'
        assert optional_plugins.status(identifier)['plugins']['mverb']['state']=='installed'
        release_second.set()
        deadline=time.monotonic()+5
        while optional_plugins.status(identifier)['state']=='running':
            assert time.monotonic()<deadline;time.sleep(.01)
        state=optional_plugins.status(identifier)
        assert state['state']=='completed_with_errors'
        assert state['plugins']['dragonfly']['state']=='failed'
        assert state['plugins']['dragonfly']['error']=='Compiler unavailable'
        # Final states survive loss of the in-memory job/restart.
        monkeypatch.setattr(optional_plugins,'_JOBS',{})
        cards={p['id']:p for p in optional_plugins.catalog()['plugins']}
        assert cards['mverb']['state']=='installed' and cards['dragonfly']['state']=='failed'
        assert cards['chow-tape']['state']=='not_installed'
    finally:release_first.set();release_second.set()


def test_live_mixer_validation_and_no_persistence():
    p=project();patch=controls(p);patch['tracks'][0].update(volume_db=-6,pan=.5,gain_db=3,mute=True)
    changed=apply(p,patch)
    assert changed.tracks[0].volume_db==-6 and changed.tracks[0].pan==.5
    assert p.tracks[0].volume_db==0 and changed.tracks[0].filename=='tone.wav'
    for key,value in [('pan',float('nan')),('volume_db',float('inf')),('gain_db',25),('filename','/etc/shadow'),('mute',1)]:
        patch=controls(p);patch['tracks'][0][key]=value
        with pytest.raises(ValueError):apply(p,patch)
    patch=controls(p);patch['tracks'][0]['id']='other'
    with pytest.raises(ValueError):apply(p,patch)


def test_cpp_real_graph_metering_and_immediate_fader_pan_gain(tmp_path,monkeypatch,compiled_core):
    from app.vst3_live_graph import Graph
    monkeypatch.setenv('MTA_AUDIO_CORE_PATH',str(compiled_core));cpp_audio._load.cache_clear()
    source=tmp_path/'tone.wav';sf.write(source,np.full((96000,2),.2,dtype=np.float32),48000,subtype='FLOAT')
    p=project();graph=Graph(p,[source],raw_sources=['tone'])
    try:
        initial=graph.read(4096);assert np.max(initial)>.19
        assert graph.meters['tracks'][0]==pytest.approx([.2,.2,.2,.2])
        assert graph.meters['master']==pytest.approx([.2,.2,.2,.2])
        patch=controls(p);patch['tracks'][0].update(volume_db=-6,pan=1,gain_db=6)
        assert graph.update(apply(p,patch))
        changed=graph.read(4096)
        assert np.max(np.abs(changed[:,0]))<1e-7
        assert np.mean(changed[:,1])==pytest.approx(.2,abs=1e-6)
        assert graph.meters['tracks'][0]==pytest.approx([0,.2,0,.2],abs=1e-6)
        patch=controls(graph.project);patch['tracks'][0]['mute']=True
        assert graph.update(apply(graph.project,patch))
        assert np.max(np.abs(graph.read(4096)))==0
        assert graph.meters['master']==[0,0,0,0]
        assert graph.meters['tracks'][0]==[0,0,0,0]
    finally:graph.close()


def test_real_browser_worker_meters_and_live_controls(tmp_path,monkeypatch,compiled_core,chromium_capability):
    pytest.importorskip('pedalboard');pytest.importorskip('av')
    from app.vst3_live import Session
    monkeypatch.setenv('MTA_AUDIO_CORE_PATH',str(compiled_core));cpp_audio._load.cache_clear()
    source=tmp_path/'tone.wav';sf.write(source,np.full((96000,2),.2,dtype=np.float32),48000,subtype='FLOAT')
    session=Session(project(),[source],0,output='browser',original_editor=False)
    try:
        result,data=server_vst3.read_pcm(session,0,4096)
        assert result['meters']['master']==pytest.approx([.2,.2,.2,.2])
        assert np.max(np.frombuffer(data,dtype='<f4'))>.19
        patch=controls(session.project);patch['tracks'][0].update(volume_db=-12,pan=-1)
        session.update(apply(session.project,patch))
        result,data=server_vst3.read_pcm(session,1,4096)
        assert result['meters']['tracks'][0][1]==0
        samples=np.frombuffer(data,dtype='<f4').reshape(-1,2)
        assert np.max(np.abs(samples[:,1]))==0
        assert np.mean(samples[:,0])==pytest.approx(.2*10**(-12/20),abs=1e-6)
        session.request('pause');assert not session.request('play')['status']['failed']
    finally:session.close()


def test_authenticated_session_mixer_route_rejects_foreign_or_unsafe_controls(monkeypatch):
    monkeypatch.setenv('MTA_NATIVE_SINGLE_USER','false')
    p=project();app=FastAPI();manager=server_vst3.Sessions();monkeypatch.setattr(server_vst3,'sessions',manager)
    class Session:
        project=p
        def update(self,new):self.project=new;return {'ok':True}
    entry=server_vst3.Entry(owner=7,project=p.id,client='test',session=Session())
    manager.entries['owned']=entry
    def actor(req):return {'id':int(req.headers.get('x-test-owner','7'))}
    def guard(req,pid):
        if pid!=p.id:raise HTTPException(404)
        return p
    server_vst3.register_routes(app,guard,actor)
    client=TestClient(app);route=f'/api/projects/{p.id}/vst3-live/owned/control'
    patch=controls(p);patch['tracks'][0]['pan']=1
    assert client.post(route,json={'action':'mixer','mixer':patch}).status_code==200
    assert entry.session.project.tracks[0].pan==1 and p.tracks[0].pan==0
    assert client.post(route,json={'action':'mixer','mixer':patch},headers={'x-test-owner':'8'}).status_code==404
    patch['tracks'][0]['filename']='/etc/shadow'
    assert client.post(route,json={'action':'mixer','mixer':patch}).status_code==422
    assert 'owned' in manager.entries  # Invalid edits do not kill healthy playback.
    manager.entries.clear()


@pytest.mark.parametrize('native',[False,True])
@pytest.mark.parametrize('locale',['en','it'])
def test_browser_per_plugin_progress_and_terminal_states(locale,native,chromium_capability):
    api=pytest.importorskip('playwright.sync_api')
    with api.sync_playwright() as pw:
        browser=pw.chromium.launch(headless=True,args=['--no-sandbox']);page=browser.new_page()
        page.route('http://mta.test/',lambda r:r.fulfill(body='<div id="catalog"></div>',content_type='text/html'));page.goto('http://mta.test/');page.evaluate('(locale)=>{window.MtaLocale={language:locale}}',locale)
        if native:page.evaluate("document.body.classList.add('native-single-user')")
        prefix='/api/native/optional-vst3' if native else '/api/admin/optional-vst3'
        catalog=optional_plugins.catalog();catalog['active_job']=None
        for plugin in catalog['plugins']:plugin.update(installed=False,state='not_installed',error='')
        states={'id':'job','state':'running','started_at':time.time(),'plugins':{'mverb':{'state':'installing','stage':'compile','message':'MVerb'},'dragonfly':{'state':'queued'}},'results':[]}
        page.route('**'+prefix,lambda r:r.fulfill(json=catalog))
        page.route('**'+prefix+'/install',lambda r:r.fulfill(json=states))
        page.route('**'+prefix+'/jobs/job',lambda r:r.fulfill(json=states))
        page.add_script_tag(content=(ROOT/'app/static/optional_plugins.js').read_text())
        page.evaluate("()=>{void openOptionalVst3(document.getElementById('catalog'))}")
        assert page.locator('[data-plugin=mverb] a').first.get_attribute('href')==prefix+'/mverb/license'
        page.locator('input[value="mverb"]').check();page.locator('input[value="dragonfly"]').check()
        page.locator('#catalog > label input').check()
        page.get_by_role('button',name='Installa VST3 selezionati' if locale=='it' else 'Install selected VST3',exact=True).click()
        page.locator('[data-plugin=mverb] progress').wait_for(state='visible')
        assert page.locator('[data-plugin=dragonfly] progress').count()==0
        catalog['active_job']='job'
        page.evaluate("()=>{void openOptionalVst3(document.getElementById('catalog'))}")
        page.locator('[data-plugin=mverb] progress').wait_for(state='visible')
        assert page.get_by_role('button',name='Installa VST3 selezionati' if locale=='it' else 'Install selected VST3',exact=True).is_disabled()
        states['plugins']['mverb']={'state':'installed'};states['plugins']['dragonfly']={'state':'installing','stage':'download','message':'Dragonfly'}
        page.locator('[data-plugin=dragonfly] progress').wait_for(state='visible')
        assert page.locator('[data-plugin=mverb] progress').count()==0
        assert page.locator('[data-plugin=mverb]').get_attribute('data-state')=='installed'
        states['plugins']['dragonfly']={'state':'failed','error':'Compiler unavailable'};states['state']='completed_with_errors'
        page.locator('[data-plugin=dragonfly][data-state=failed]').wait_for()
        assert page.locator('#catalog progress').count()==0
        assert 'Compiler unavailable' in page.locator('[data-plugin=dragonfly]').inner_text()
        assert page.get_by_role('button',name='Installa VST3 selezionati' if locale=='it' else 'Install selected VST3',exact=True).is_enabled()
        browser.close()


def test_real_server_browser_cpp_space_meters_and_mixer(compiled_core,tmp_path,chromium_capability):
    pytest.importorskip('playwright.sync_api');pytest.importorskip('pedalboard');pytest.importorskip('av')
    from scripts.validate_cpp_live_controls import probe
    result=probe(compiled_core,tmp_path/'browser.json')
    assert result['space_pause_resume'] and result['continuous_gesture_updates']
    assert result['fader_to_audible_meter_seconds']<1


def test_native_live_mixer_uses_bridge_without_saving_and_updates_meters(chromium_capability):
    api=pytest.importorskip('playwright.sync_api')
    with api.sync_playwright() as pw:
        browser=pw.chromium.launch(headless=True,args=['--no-sandbox']);page=browser.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
        page.set_content('<button id="playMaster"></button><span id="vu-tone-L"></span><span id="vu-tone-R"></span><span id="vu-master-L"></span><span id="vu-master-R"></span>')
        page.add_script_tag(content=(ROOT/'app/static/playback_prep.js').read_text())
        page.evaluate('''()=>{
 window.currentUser={native_single_user:true};window.nativeAudioEngineIdentity='cpp';window.current={id:'native-mixer',realtime_meter_enabled:true,tracks:[{id:'tone',volume_db:0,pan:0,gain_db:0}]};window.playCursorMs=0;window.transportPositionRevision=0;window.playbackPaused=false;window.timelineAudioDirty=false;window.projectDirty=false;
 for(const name of ['previewMaster','stopPlayback','pausePlayback','resumePlayback','togglePlayback','goToTimestamp','seekTransport','goTransportStart','timingAudioChanged','updatePlaybackGains','queueLiveFxRefresh','setPlayCursor','updateTimedPlaybackOverlay','setRenderPlaybackPreparing','collect'])window[name]=()=>{};
 window.setTrackPan=(id,value)=>{current.tracks[0].pan=value};window.playbackActuallyRunning=()=>false;window.$=s=>document.querySelector(s);window.tempoRatio=()=>1;window.tr=en=>en;window.toast=message=>{throw Error(message)};
 window.saves=0;window.persistCurrentProject=async()=>{saves++;throw Error('Live faders must not save')};window.liveCalls=[];
 const state={active:true,position_ms:0,meters:{tracks:[[.2,.1,.3,.2]],master:[.2,.1,.3,.2]}};window.bridgeState=state;
 window.waitForNativeApi=async()=>({transport_control:async()=>state,transport_prepare_play:async()=>state,transport_update_live:async(pid,mixer)=>{liveCalls.push({pid,mixer});return {requires_prepare:false}}});
}''')
        page.add_script_tag(content=(ROOT/'app/static/native_transport.js').read_text())
        page.evaluate('async()=>{await previewMaster()}')
        assert page.locator('#vu-tone-L').evaluate('(el)=>parseFloat(el.style.height)')>0
        page.evaluate("()=>{current.tracks[0].volume_db=-6;updatePlaybackGains();setTrackPan('tone',.5)}")
        page.wait_for_function('()=>liveCalls.length>0')
        assert page.evaluate('liveCalls.at(-1).mixer.tracks[0].volume_db')==-6
        assert page.evaluate('liveCalls.at(-1).mixer.tracks[0].pan')==.5
        assert page.evaluate('saves')==0
        page.evaluate('()=>{bridgeState.active=false;bridgeState.preparing=true}');page.wait_for_timeout(120)
        assert page.evaluate('playbackActuallyRunning()')
        page.evaluate('()=>{bridgeState.active=true;bridgeState.preparing=false}')
        page.evaluate('async()=>{await pausePlayback()}')
        assert page.locator('#vu-master-L').evaluate('(el)=>parseFloat(el.style.height)')==0
        page.evaluate('async()=>{await resumePlayback()}');page.wait_for_timeout(120)
        assert page.locator('#vu-master-L').evaluate('(el)=>parseFloat(el.style.height)')>0
        page.evaluate('()=>stopPlayback()');assert not errors,errors;browser.close()
