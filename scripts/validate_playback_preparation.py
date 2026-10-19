#!/usr/bin/env python3
"""Reproducible local Chromium playback probe; only disposable test data is used."""
import argparse
import json
import os
from pathlib import Path
import secrets
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
    from app.models import Track,Clip
    auth.init_auth_db();admin=auth.find_user('admin')
    project=storage.create_project('Playback preparation regression',owner_user_id=admin['id'],sample_rate=48000)
    audio=storage.pdir(project.id)/'audio';audio.mkdir(exist_ok=True)
    samples=np.sin(np.arange(48000*30,dtype=np.float32)*.04)*.025
    for i in range(8):
        name=f'track-{i}.wav';sf.write(audio/name,np.column_stack((samples,samples)),48000,subtype='PCM_16')
        project.tracks.append(Track(id=f'track{i}',name=f'Track {i+1}',filename=name,channels=2,sample_rate=48000,duration_ms=30000,delay_ms=500,clips=[Clip(id=f'clip{i}',source_start_ms=1000,source_end_ms=29000,timeline_start_ms=1000)]))
    if os.getenv('MTA_PLAYBACK_PROBE_CPP')=='1':
        from app import audio_backend
        audio_backend.select('cpp');project.realtime_meter_enabled=True
    storage.save_project(project)
    request=Request({'type':'http','headers':[(b'user-agent',b'testclient')]})
    Path(os.environ['MTA_PLAYBACK_PROBE_CONFIG']).write_text(json.dumps({'project':project.id,'cookie':auth.create_session(admin['id'],request)}))
    from app.main import app
    import uvicorn
    uvicorn.run(app,host='127.0.0.1',port=port,log_level='warning',lifespan='off')


def probe(report):
    import httpx
    from playwright.sync_api import sync_playwright
    with socket.socket() as listener:
        listener.bind(('127.0.0.1',0));port=listener.getsockname()[1]
    with tempfile.TemporaryDirectory(prefix='mta-playback-probe-') as folder:
        base=Path(folder);config=base/'config.json'
        env={**os.environ,'MTA_DATA_DIR':str(base/'data'),'MTA_AI_JOB_STATE_DIR':str(base/'jobs'),'MTA_ADMIN_PASSWORD':secrets.token_urlsafe(32),'MTA_PLAYBACK_PROBE_CONFIG':str(config),'PYTHONPATH':str(ROOT),'OPENBLAS_NUM_THREADS':'1','MTA_NATIVE_SINGLE_USER':'false','MTA_ALLOW_INSECURE_NO_AUTH':'false'}
        with (base/'server.log').open('wb') as log:
            server=subprocess.Popen([sys.executable,str(Path(__file__).resolve()),'--serve',str(port)],cwd=ROOT,env=env,stdout=log,stderr=log)
            try:
                url=f'http://127.0.0.1:{port}'
                deadline=time.monotonic()+30
                while time.monotonic()<deadline:
                    if server.poll() is not None:raise RuntimeError('Disposable playback server failed to start')
                    try:
                        if httpx.get(url+'/api/health',trust_env=False,timeout=.3).status_code==200:break
                    except httpx.HTTPError:pass
                    time.sleep(.05)
                else:raise RuntimeError('Disposable playback server startup timed out')
                fixture=json.loads(config.read_text())
                with sync_playwright() as p:
                    browser=p.chromium.launch(headless=True,args=['--no-sandbox','--autoplay-policy=no-user-gesture-required'])
                    page=browser.new_page(user_agent='testclient',viewport={'width':1400,'height':1000})
                    page.context.add_cookies([{'name':'mta_session','value':fixture['cookie'],'url':url}])
                    errors=[];requests=[];page.on('pageerror',lambda e:errors.append(str(e)));page.on('request',lambda r:requests.append(r.url))
                    page.goto(url,wait_until='networkidle');page.evaluate('(id)=>openP(id)',fixture['project']);page.wait_for_timeout(200)
                    requests.clear();start=time.monotonic();page.evaluate('()=>previewMaster()');first=time.monotonic()-start
                    result=page.evaluate('({active:waPlaybackActive,tracks:trackPlaybacks.length,raw:trackPlaybacks.map(t=>t.rawTimeline),cacheBytes:waDecodedBuffers.bytes})')
                    page.wait_for_timeout(300);page.evaluate('()=>stopPlayback()');start=time.monotonic();page.evaluate('()=>previewMaster()');second=time.monotonic()-start;page.evaluate('()=>stopPlayback()')
                    result.update(first_start_seconds=round(first,3),cached_restart_seconds=round(second,3),backend_preview_requests=[x.split(url,1)[-1] for x in requests if 'preview-track' in x or 'preview-mix' in x],errors=errors)
                    if not result['active'] or result['tracks']!=8 or not all(result['raw']) or result['backend_preview_requests'] or errors:raise RuntimeError('Playback regression: '+json.dumps(result))
                    page.evaluate("()=>{current.tracks[0].inserts=[{id:'rv',plugin:'reverb_lexicon',enabled:true,preset:'default',params:{}}];openInsertEditor(false,'rv',current.tracks[0].id)}")
                    if page.locator('.insert-setup-title').inner_text()!='Lexicon-style reverb' or page.locator('.fx-artwork svg').count()!=1:raise RuntimeError('Internal plugin artwork/name regression')
                    if not page.locator('.plugin-field-knob').evaluate_all('(fields)=>fields.every(f=>f.querySelector(".plugin-number").getBoundingClientRect().right<=f.getBoundingClientRect().right)'):raise RuntimeError('Internal plugin controls overflow')
                    page.locator('.plugin-number').first.fill('0.6')
                    page.evaluate('()=>startWebAudioProjectPlayback(false,0)');page.evaluate('()=>stopPlayback()')
                    if not page.locator('.insert-setup-title').is_visible() or page.locator('.plugin-number').first.input_value()!='0.6':raise RuntimeError('Playback replaced the plugin editor or discarded its draft')
                    result['plugin_editor_preserved']=True
                    browser.close()
                report.parent.mkdir(parents=True,exist_ok=True);report.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
            finally:
                server.terminate()
                try:server.wait(timeout=5)
                except subprocess.TimeoutExpired:server.kill();server.wait()


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--report',type=Path,default=ROOT/'validation/r210-playback-browser-result.json');parser.add_argument('--serve',type=int,help=argparse.SUPPRESS)
    args=parser.parse_args()
    if args.serve:serve(args.serve)
    else:probe(args.report.resolve())
