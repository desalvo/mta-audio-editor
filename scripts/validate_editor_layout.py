#!/usr/bin/env python3
"""Disposable authenticated browser regression and manual screenshot capture."""
# ruff: noqa: S101 -- executable regression probe, assertions do not guard production actions
import argparse
import json
import os
from pathlib import Path
import secrets
import signal
import socket
import subprocess
import sys
import tempfile
import time

ROOT=Path(__file__).resolve().parents[1]


def serve(port):
    import numpy as np
    import soundfile as sf
    from starlette.requests import Request
    from app import auth,storage
    from app.models import Track,Clip,Marker
    auth.init_auth_db();admin=auth.find_user('admin')
    project=storage.create_project('MTA · Studio session',owner_user_id=admin['id'],sample_rate=48000)
    project.metronome_mode='zones';project.metronome_bpm=112.5
    project.markers=[Marker(id='intro',time_ms=6000,label='Verse'),Marker(id='chorus',time_ms=18000,label='Chorus')]
    for i,name in enumerate(['Piano','Strings','Bass','Drums']):
        rate=48000;t=np.arange(rate*30,dtype=np.float32)/rate
        pcm=.12*np.sin(t*(220+i*110)*2*np.pi)*(.5+.5*np.sin(t*np.pi*(i+1))**2)
        filename=f'source-{i}.wav';sf.write(storage.audio_path(project.id,filename),pcm,rate)
        project.tracks.append(Track(id=f't{i}',name=name,filename=filename,duration_ms=30000,sample_rate=rate,clips=[Clip(id=f'clip{i}',source_end_ms=30000)],waveform_peaks=[float(x) for x in np.max(np.abs(pcm[:len(pcm)//1000*1000].reshape(-1,1000)),axis=1)]))
    if os.getenv('MTA_LAYOUT_PROBE_CPP')=='1':
        from app import audio_backend
        audio_backend.select('cpp');project.realtime_meter_enabled=True
    storage.save_project(project)
    request=Request({'type':'http','headers':[(b'user-agent',b'testclient')]})
    Path(os.environ['MTA_LAYOUT_CONFIG']).write_text(json.dumps({'project':project.id,'cookie':auth.create_session(admin['id'],request)}))
    from app.main import app
    import uvicorn
    uvicorn.run(app,host='127.0.0.1',port=port,log_level='warning',lifespan='off')


def probe(report,screenshots=False):
    import httpx
    from playwright.sync_api import sync_playwright
    with socket.socket() as listener:
        listener.bind(('127.0.0.1',0));port=listener.getsockname()[1]
    with tempfile.TemporaryDirectory(prefix='mta-layout-probe-') as folder:
        base=Path(folder);config=base/'config.json'
        env={**os.environ,'MTA_DATA_DIR':str(base/'data'),'MTA_AI_JOB_STATE_DIR':str(base/'jobs'),'MTA_ADMIN_PASSWORD':secrets.token_urlsafe(32),'MTA_LAYOUT_CONFIG':str(config),'PYTHONPATH':str(ROOT),'OPENBLAS_NUM_THREADS':'1','MTA_NATIVE_SINGLE_USER':'false','MTA_ALLOW_INSECURE_NO_AUTH':'false'}
        with (base/'server.log').open('wb') as log:
            server=subprocess.Popen([sys.executable,str(Path(__file__).resolve()),'--serve',str(port)],cwd=ROOT,env=env,stdout=log,stderr=log,start_new_session=os.name=='posix')
            try:
                url=f'http://127.0.0.1:{port}'
                deadline=time.monotonic()+90
                while time.monotonic()<deadline:
                    if server.poll() is not None:raise RuntimeError((base/'server.log').read_text()[-3000:])
                    try:
                        if httpx.get(url+'/api/health',trust_env=False,timeout=.3).status_code==200:break
                    except httpx.HTTPError:pass
                    time.sleep(.1)
                else:raise RuntimeError('Local server startup timeout')
                fixture=json.loads(config.read_text());result={'screenshots':[]}
                with sync_playwright() as p:
                    browser=p.chromium.launch(headless=True,args=['--no-sandbox','--autoplay-policy=no-user-gesture-required'])
                    page=browser.new_page(user_agent='testclient',viewport={'width':1440,'height':1000})
                    page.context.add_cookies([{'name':'mta_session','value':fixture['cookie'],'url':url}]);errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
                    page.goto(url,wait_until='networkidle');page.evaluate('(id)=>openP(id)',fixture['project']);page.wait_for_selector('.editor-toolbar .layout-icon-only')
                    page.evaluate('()=>{document.getElementById("timelinePane").scrollLeft=700}')
                    page.wait_for_timeout(80)
                    center=page.evaluate('()=>{const p=document.getElementById("timelinePane");return (p.scrollLeft+p.clientWidth/2)/pxPerSec}')
                    page.evaluate('()=>{beginZoomPreview();previewZoom(140)}');page.wait_for_timeout(50)
                    page.evaluate('commitZoom(140)');page.wait_for_timeout(300)
                    def timeline_center():return page.evaluate('()=>{const p=document.getElementById("timelinePane");return (p.scrollLeft+p.clientWidth/2)/pxPerSec}')
                    assert abs(timeline_center()-center)<.03
                    page.evaluate('stepZoom(-1)');page.wait_for_timeout(300)
                    assert abs(timeline_center()-center)<.03
                    page.evaluate('applyZoomPreset("pct:200")');page.wait_for_timeout(300)
                    assert abs(timeline_center()-center)<.03
                    assert page.evaluate('document.getElementById("timelinePane").scrollLeft')>0
                    page.evaluate('flushAutosave()');page.wait_for_timeout(100)
                    assert abs(timeline_center()-center)<.03
                    result['zoom_anchor_retained']=True
                    page.evaluate('()=>{setZoom(70);document.getElementById("timelinePane").scrollLeft=0}');page.wait_for_timeout(100)
                    page.evaluate('document.getElementById("timelinePane").scrollLeft=0')
                    result['icon_buttons']=page.locator('.editor-toolbar button.layout-icon-only').count()
                    assert page.locator('.editor-toolbar>button:not(.layout-icon-only)').count()==0
                    assert page.locator('#transportBpmInput').evaluate('(e)=>e.closest(".compact-number")!==null')
                    page.locator('#transportBpmInput').fill('112.5')
                    page.locator('#transportBpmInput').evaluate('(e)=>e.closest(".compact-number").querySelector("button").click()')
                    assert page.locator('#transportBpmInput').input_value()=='112.51'
                    # Revert before creating the zone metronome.
                    page.evaluate('()=>{current.bpm=112.5;current.base_bpm=112.5;current.metronome_bpm=112.5;render()}')
                    # Exercise the real dialog while an autosave is queued in flight.
                    def delayed_insert(route):
                        time.sleep(.2);route.continue_()
                    page.route('**/metronome-insert',delayed_insert)
                    page.evaluate('async()=>{openMetronomeSettings(750);document.getElementById("metronomeMode").value="zones";const originalFetch=window.fetch;window.fetch=function(input,options){if(String(input).endsWith("/metronome-insert"))setTimeout(()=>markDirty(0),20);return originalFetch.call(this,input,options)};try{await applyMetronomeSettings()}finally{window.fetch=originalFetch}}')
                    page.unroute('**/metronome-insert',delayed_insert)
                    page.wait_for_timeout(300)
                    assert page.evaluate('current.tracks.some(t=>t.type==="click")'),page.locator('#toast').inner_text()
                    result['generation_survives_queued_autosave']=True
                    old=page.evaluate('current.tracks.find(t=>t.type==="click").waveform_revision')
                    assert page.evaluate('async()=>{await previewMaster();return playbackActuallyRunning()}')
                    session=page.evaluate('window.mtaServerVst3?.session()?.id||null')
                    page.evaluate('async()=>{current.markers[0].time_ms=6500;await saveMetaQuickEdit()}');page.wait_for_timeout(1200)
                    deadline=time.monotonic()+20
                    while not page.evaluate('playbackActuallyRunning()') and time.monotonic()<deadline:page.wait_for_timeout(100)
                    assert page.evaluate('playbackActuallyRunning()'),page.locator('#toast').inner_text()
                    if session:assert page.evaluate('window.mtaServerVst3.session().id')!=session
                    page.evaluate('stopPlayback()');result['live_audio_refresh_engine']='cpp' if session else 'current'
                    assert page.evaluate('current.tracks.find(t=>t.type==="click").waveform_revision')!=old
                    result['marker_audio_revision_changed']=True
                    # Each submenu expansion must keep the menu within a short viewport.
                    page.set_viewport_size({'width':900,'height':600});page.evaluate('()=>openTrackContextMenuAt(current.tracks[0].id,890,590)')
                    for category in page.locator('#trackContextMenu details').all():
                        category.evaluate('(e)=>e.open=true');page.wait_for_timeout(80)
                        assert page.locator('#trackContextMenu').evaluate('(e)=>{const r=e.getBoundingClientRect();return r.top>=7&&r.bottom<=innerHeight-7&&r.left>=7&&r.right<=innerWidth-7}')
                    last=page.locator('#trackContextMenu button').last;last.scroll_into_view_if_needed();assert last.is_visible();page.evaluate('closeTrackContextMenu()');result['menu_in_viewport']=True
                    page.set_viewport_size({'width':1440,'height':1000});page.evaluate('MtaEditorLayout.configure()');page.select_option('#layout-bar','editor');page.locator('[data-row="0"]').select_option(index=1);page.click('#layout-save');page.wait_for_timeout(200)
                    prefs=page.evaluate('async()=>await (await fetch("/api/account/editor-layout")).json()');assert len(prefs['rows'])>=2,repr(prefs)
                    page.reload(wait_until='networkidle');page.wait_for_selector('.editor-toolbar');page.wait_for_timeout(200)
                    assert page.locator('.editor-toolbar>.layout-row-break').count()>=1;result['toolbar_reload_persisted']=True
                    handle=page.locator('#aj-drag');original_y=handle.bounding_box()['y'];handle.focus();page.keyboard.press('ArrowRight');page.wait_for_timeout(200)
                    assert abs(handle.bounding_box()['y']-original_y)<1
                    pos=page.evaluate('async()=>(await (await fetch("/api/account/editor-layout")).json()).job_position');assert pos['x']>0
                    page.reload(wait_until='networkidle');page.wait_for_selector('#aj-drag');page.wait_for_timeout(200)
                    assert page.locator('#aj-drag').bounding_box()['x']>8;result['monitor_reload_persisted']=True
                    # Reset for readable manual captures, then exercise project reopening.
                    page.evaluate('async()=>await api("/api/account/editor-layout",{method:"PUT",headers:{"content-type":"application/json"},body:JSON.stringify({rows:[]})})');page.reload(wait_until='networkidle');page.wait_for_selector('.editor-toolbar');page.wait_for_timeout(200)
                    page.evaluate('()=>{const b=document.createElement("button");b.hidden=true;b.className="transport-btn";b.id="layoutHiddenProbe";b.title="Hidden capability";document.querySelector(".transport").append(b)}');page.wait_for_timeout(80)
                    assert page.locator('#layoutHiddenProbe').is_hidden()
                    page.evaluate('()=>{document.getElementById("layoutHiddenProbe").remove();document.body.classList.add("native-single-user")}')
                    assert page.locator('#adminNav').is_hidden()
                    page.evaluate('document.body.classList.remove("native-single-user")')
                    page.set_viewport_size({'width':390,'height':844});page.wait_for_timeout(120)
                    assert page.locator('#aj-launch').evaluate('(e)=>{const r=e.getBoundingClientRect();return r.left>=0&&r.right<=innerWidth&&r.top>=0&&r.bottom<=innerHeight}')
                    page.evaluate('()=>openTrackContextMenuAt(current.tracks[0].id,380,830)');page.wait_for_timeout(80)
                    assert page.locator('#trackContextMenu').evaluate('(e)=>{const r=e.getBoundingClientRect();return r.top>=7&&r.bottom<=innerHeight-7&&r.right<=innerWidth-7}')
                    page.evaluate('closeTrackContextMenu()');page.set_viewport_size({'width':1440,'height':1000});page.wait_for_timeout(100)
                    result['mobile_and_capability_visibility']=True
                    result['mixer_labels']=page.locator('.mixer-pan-title').count()
                    assert result['mixer_labels']==5
                    assert all(label.startswith('FX') for label in page.locator('.channel-insert-action').all_text_contents())
                    if screenshots:
                        folder=ROOT/'app/static/docs-assets/r210';folder.mkdir(exist_ok=True)
                        def shot(name,selector=None):
                            path=folder/(name+'.png');target=page.locator(selector) if selector else page;target.screenshot(path=str(path));result['screenshots'].append(str(path.relative_to(ROOT)))
                        for language in ('en','it'):
                            page.evaluate('(language)=>{window.MtaLocale.setChoice(language);uiLanguage=language;window.dispatchEvent(new CustomEvent("mta:language",{detail:{language}}))}',language)
                            shot('workspace-'+language)
                            page.evaluate('openMetronomeSettings(750)');page.wait_for_timeout(150);shot('metronome-'+language,'.utility-modal');page.evaluate('closeUtilityModal()')
                            page.evaluate('MtaEditorLayout.configure()');page.select_option('#layout-bar','editor');shot('toolbar-'+language,'.utility-modal');page.evaluate('closeUtilityModal()')
                            page.evaluate('()=>openTrackContextMenuAt(current.tracks[0].id,650,380)');page.wait_for_timeout(80);shot('context-'+language,'#trackContextMenu');page.evaluate('closeTrackContextMenu()')
                            shot('mixer-'+language,'#mixerDock')
                            page.evaluate('window.mtaAiJobs.open()');page.wait_for_timeout(100);shot('jobs-'+language,'#aj-panel');page.click('#aj-close')
                        for path,name in [('/settings','admin-settings'),('/ai-billing','admin-billing'),('/account','user-account')]:
                            page.goto(url+path,wait_until='networkidle');page.wait_for_timeout(150);shot(name)
                    page.goto(url+'/docs/user/en',wait_until='networkidle');page.set_viewport_size({'width':390,'height':844})
                    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+1')
                    result['online_manual_mobile_layout']=True
                    result['errors']=errors;assert not errors,errors
                    browser.close()
                report.parent.mkdir(parents=True,exist_ok=True);report.write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
            finally:
                if os.name=='posix':
                    try:os.killpg(server.pid,signal.SIGTERM)
                    except ProcessLookupError:pass
                else:server.terminate()
                server.wait(timeout=15)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--serve',type=int);parser.add_argument('--screenshots',action='store_true');parser.add_argument('--report',type=Path,default=ROOT/'validation/r210-zones-layout-browser.json');args=parser.parse_args()
    if args.serve:serve(args.serve)
    else:probe(args.report,args.screenshots)
