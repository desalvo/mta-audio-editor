"""Standalone SDK discovery and preparation UI must not import or replace editors."""
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

ROOT=Path(__file__).resolve().parents[1]


@pytest.mark.parametrize('managed_override',[False,True])
def test_sdk_chain_discovery_works_without_site_packages_or_auth(tmp_path,managed_override):
    data=tmp_path/'data';managed=tmp_path/('chosen' if managed_override else 'mta-optional-vst3')
    configured=tmp_path/'configured';configured.mkdir(mode=0o755);managed.mkdir(mode=0o755)
    bundle=configured/'Reference.vst3';bundle.mkdir(mode=0o755)
    optional=managed/'MVerb.vst3';optional.mkdir(mode=0o755)
    env={**os.environ,'MTA_DATA_DIR':str(data),'MTA_VST3_PATHS':str(configured),'MTA_NATIVE_SINGLE_USER':'false'}
    env.pop('MTA_OPTIONAL_VST3_DIR',None)
    if managed_override:env['MTA_OPTIONAL_VST3_DIR']=str(managed)
    code='''import sys,json
sys.path.insert(0,sys.argv[1])
class BlockApplicationDependencies:
 def find_spec(self,fullname,path=None,target=None):
  if fullname in ('app.auth','app.optional_plugins','fastapi','qrcode'):
   raise AssertionError('Standalone SDK loaded '+fullname)
sys.meta_path.insert(0,BlockApplicationDependencies())
from native.vst3_probe.native_chain import validate_plugin_path
from app.vst3_host import discover_plugins
assert str(validate_plugin_path(sys.argv[2]))==sys.argv[2]
assert {p['path'] for p in discover_plugins()}>={sys.argv[2],sys.argv[3]}
print(json.dumps({'site_loaded':'site' in sys.modules,'auth_loaded':'app.auth' in sys.modules}))
'''
    result=subprocess.run([sys.executable,'-I','-S','-c',code,str(ROOT),str(bundle),str(optional)],env=env,capture_output=True,text=True,check=True,timeout=15)
    assert json.loads(result.stdout)=={'site_loaded':False,'auth_loaded':False}


@pytest.mark.parametrize('locale',['en','it'])
def test_audio_progress_preserves_open_midi_editor_and_drafts(locale):
    api=pytest.importorskip('playwright.sync_api')
    with api.sync_playwright() as p:
        try:browser=p.chromium.launch(headless=True,args=['--no-sandbox'])
        except api.Error as exc:pytest.skip('Chromium unavailable: '+str(exc)[:160])
        page=browser.new_page(viewport={'width':480,'height':800})
        page.set_content('<style>'+(ROOT/'app/static/app.css').read_text()+'</style><div id="utilityBackdrop"><div id="utilityBody"><select id="midiRoute"><option value="hardware">hardware</option><option value="instrument">instrument</option></select><input id="draft" value="unsaved MIDI notes"></div></div>')
        page.add_script_tag(content=(ROOT/'app/static/playback_prep.js').read_text())
        page.evaluate('(locale)=>{window.tr=(en,it)=>locale==="it"?it:en;window.stopped=0;window.stopPlayback=()=>window.stopped++;window.first={};window.second={};MtaPlaybackPrep.showProgress(first,"Preparing audio",-1,"Checking sources","2/8")}',locale)
        assert page.locator('#midiRoute').is_visible()
        assert page.locator('#draft').input_value()=='unsaved MIDI notes'
        assert page.locator('#audioPreparation progress').get_attribute('value') is None
        page.locator('#midiRoute').select_option('instrument')
        assert page.locator('#midiRoute').input_value()=='instrument'
        page.evaluate('()=>{MtaPlaybackPrep.showProgress(second,"Preparing audio",70,"Decoding audio");MtaPlaybackPrep.hideProgress(first)}')
        assert page.locator('#audioPreparation').is_visible()
        assert page.locator('#audioPreparation progress').get_attribute('value')=='70'
        assert page.locator('#audioPreparation').bounding_box()['width']<=448
        page.get_by_role('button',name='Interrompi' if locale=='it' else 'Stop',exact=True).click()
        assert page.evaluate('stopped')==1
        assert page.locator('#audioPreparation').count()==0
        assert page.locator('#midiRoute').is_visible()
        assert page.locator('#draft').input_value()=='unsaved MIDI notes'
        assert page.locator('#midiRoute').input_value()=='instrument'
        browser.close()


def test_native_transport_preparation_preserves_midi_editor():
    api=pytest.importorskip('playwright.sync_api')
    with api.sync_playwright() as p:
        try:browser=p.chromium.launch(headless=True,args=['--no-sandbox'])
        except api.Error as exc:pytest.skip('Chromium unavailable: '+str(exc)[:160])
        page=browser.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
        page.set_content('<div id="utilityBackdrop"><div id="utilityBody"><input id="midiDraft" value="unsaved notes"></div></div><button id="playMaster">Play</button>')
        page.add_script_tag(content=(ROOT/'app/static/playback_prep.js').read_text())
        page.evaluate('''()=>{
 window.currentUser={native_single_user:true};window.nativeAudioEngineIdentity='cpp';window.current={id:'test',tracks:[{}]};window.playCursorMs=0;window.transportPositionRevision=0;window.playbackPaused=false;window.timelineAudioDirty=false;window.projectDirty=false;
 for(const name of ['previewMaster','stopPlayback','pausePlayback','resumePlayback','togglePlayback','goToTimestamp','seekTransport','goTransportStart','timingAudioChanged','updatePlaybackGains','queueLiveFxRefresh','setPlayCursor','updateTimedPlaybackOverlay','setRenderPlaybackPreparing','collect'])window[name]=()=>{};
 window.playbackActuallyRunning=()=>false;window.$=s=>document.querySelector(s);window.tempoRatio=()=>1;window.tr=en=>en;window.toast=()=>{};
 window.waitForNativeApi=async()=>({transport_control:async()=>({active:true,position_ms:0}),transport_preparation_status:async()=>({stage:'sources',done:1,total:2,track:'Track 1'}),transport_prepare_play:()=>new Promise(r=>window.finishNativePreparation=r)});
}''')
        page.add_script_tag(content=(ROOT/'app/static/native_transport.js').read_text())
        page.evaluate('()=>{window.pendingPlayback=window.previewMaster()}')
        page.locator('#audioPreparation').wait_for(state='visible')
        assert page.locator('#midiDraft').is_visible()
        page.locator('#midiDraft').fill('changed during preparation')
        page.evaluate('async()=>{finishNativePreparation({active:true,position_ms:0});await pendingPlayback}')
        assert page.locator('#audioPreparation').count()==0
        assert page.locator('#midiDraft').is_visible()
        assert page.locator('#midiDraft').input_value()=='changed during preparation'
        assert page.evaluate('window.playbackActuallyRunning()')
        page.evaluate('()=>window.stopPlayback()')
        assert page.locator('#midiDraft').is_visible()
        assert not errors,errors
        browser.close()
