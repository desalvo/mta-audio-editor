#!/usr/bin/env python3
"""Real ASGI, Chromium and C++ DSP playback/keyboard/mixer acceptance probe."""
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


def require(condition,message):
    if not condition:raise RuntimeError(message)


def wait(page,expression,*,arg=None,timeout=10000):
    # Playwright 1.51 wait_for_function uses eval internally; preserve the app CSP.
    deadline=time.monotonic()+timeout/1000
    while time.monotonic()<deadline:
        if page.evaluate(expression,arg):return
        page.wait_for_timeout(25)
    raise RuntimeError('Browser condition timed out: '+expression)


def probe(core,report,*,stress=False):
    import httpx
    from playwright.sync_api import sync_playwright
    with socket.socket() as listener:listener.bind(('127.0.0.1',0));port=listener.getsockname()[1]
    with tempfile.TemporaryDirectory(prefix='mta-cpp-controls-') as folder:
        base=Path(folder);config=base/'config.json';url=f'http://127.0.0.1:{port}'
        env={**os.environ,'MTA_DATA_DIR':str(base/'data'),'MTA_AI_JOB_STATE_DIR':str(base/'jobs'),'MTA_ADMIN_PASSWORD':secrets.token_urlsafe(32),'MTA_PLAYBACK_PROBE_CONFIG':str(config),'MTA_PLAYBACK_PROBE_CPP':'1','MTA_AUDIO_CORE_PATH':str(core),'PYTHONPATH':str(ROOT),'OPENBLAS_NUM_THREADS':'1','MTA_NATIVE_SINGLE_USER':'false','MTA_ALLOW_INSECURE_NO_AUTH':'false','MTA_PLAYBACK_PROBE_JITTER':'1' if stress else '0'}
        with (base/'server.log').open('wb') as log:
            server=subprocess.Popen([sys.executable,str(ROOT/'scripts/validate_playback_preparation.py'),'--serve',str(port)],cwd=ROOT,env=env,stdout=log,stderr=log,start_new_session=os.name=='posix')
            try:
                deadline=time.monotonic()+30
                while time.monotonic()<deadline:
                    if server.poll() is not None:raise RuntimeError((base/'server.log').read_text()[-2000:])
                    try:
                        if httpx.get(url+'/api/health',trust_env=False,timeout=.3).status_code==200:break
                    except httpx.HTTPError:pass
                    time.sleep(.05)
                else:raise RuntimeError('Disposable server startup timed out')
                fixture=json.loads(config.read_text())
                with sync_playwright() as pw:
                    browser=pw.chromium.launch(headless=True,args=['--no-sandbox','--autoplay-policy=no-user-gesture-required']);page=browser.new_page(user_agent='testclient',viewport={'width':1400,'height':1000})
                    page.context.add_cookies([{'name':'mta_session','value':fixture['cookie'],'url':url}]);errors=[];requests=[];page.on('pageerror',lambda e:errors.append(str(e)))
                    page.on('request',lambda r:requests.append({'method':r.method,'path':r.url.split(url)[-1],'body':r.post_data if r.url.endswith('/control') else None}))
                    page.goto(url,wait_until='networkidle');page.evaluate('(id)=>openP(id)',fixture['project'])
                    page.evaluate('()=>{document.activeElement?.blur()}');started=time.monotonic();page.keyboard.press('Space')
                    wait(page,'()=>window.mtaServerVst3.session()!==null');startup=time.monotonic()-started
                    require(page.locator('#playMaster svg rect').count()==2,'Running transport must show two pause bars')
                    wait(page,"()=>parseFloat(document.getElementById('vu-track0-L').style.height)>0",timeout=12000)
                    initial=page.locator('#vu-track0-L').evaluate('(el)=>parseFloat(el.style.height)')
                    page.keyboard.press('Space');wait(page,'()=>playbackPaused===true && !document.querySelector("#playMaster svg rect")');at=page.evaluate('playCursorMs');page.wait_for_timeout(250)
                    require(page.locator('#playMaster svg rect').count()==0,'Paused transport must show Play/Resume')
                    require(abs(page.evaluate('playCursorMs')-at)<2,'Pause did not hold the cursor')
                    require(page.locator('#vu-master-L').evaluate('(el)=>parseFloat(el.style.height)')==0,'Paused master meter is not zero')
                    page.keyboard.press('Space');wait(page,'()=>playbackPaused===false');wait(page,'(at)=>playCursorMs>at+100',arg=at)
                    requests.clear();started=time.monotonic();page.evaluate("()=>setTrackVolume('track0',-60)")
                    wait(page,"()=>parseFloat(document.getElementById('vu-track0-L').style.height)===0",timeout=3000);fader=time.monotonic()-started
                    require(fader<(2.5 if stress else 1),'Mixer update exceeded local playback budget')
                    # Continuous gestures must be throttled, not deferred until release.
                    page.evaluate("()=>{window.dragTicks=0;window.dragTimer=setInterval(()=>{setTrackPan('track1',dragTicks%2?-.5:.5);if(++dragTicks===20)clearInterval(dragTimer)},35)}")
                    page.wait_for_timeout(400)
                    require(page.evaluate('dragTicks')<20,'Gesture completed before mid-drag check')
                    require(any(r['body'] and json.loads(r['body']).get('action')=='mixer' for r in requests),'No mixer controls during gesture')
                    wait(page,'()=>dragTicks===20');page.evaluate("()=>setTrackPan('track1',-1)")
                    wait(page,"()=>parseFloat(document.getElementById('vu-track1-R').style.height)===0",timeout=3000)
                    require(not any(r['body'] and json.loads(r['body']).get('action')=='update' for r in requests),'Fader required save/update')
                    require(not errors,str(errors))
                    stream=page.evaluate('()=>window.mtaServerVst3.stats()')
                    require(stream['mode']=='worklet','Continuous PCM worklet was not used')
                    if stress:
                        for _ in range(5):
                            page.evaluate('()=>{const until=performance.now()+450;while(performance.now()<until){Math.sqrt(Math.random())}}')
                            page.wait_for_timeout(100)
                        stream=page.evaluate('()=>window.mtaServerVst3.stats()')
                        require(stream['underruns']==0,'PCM underrun with irregular network and blocked GUI: '+str(stream))
                    page.evaluate('()=>stopPlayback()');require(page.evaluate('window.mtaServerVst3.session()') is None,'Stop did not close session')
                    result={'engine':'cpp','tracks':8,'start_seconds':round(startup,3),'fader_to_audible_meter_seconds':round(fader,3),'initial_track_meter_percent':initial,'space_pause_resume':True,'pause_holds_cursor':True,'pause_clears_meters':True,'continuous_gesture_updates':True,'pan_updated':True,'live_mixer_requests':sum(bool(r['body']) and json.loads(r['body']).get('action')=='mixer' for r in requests),'errors':errors,'stream':stream,'network_jitter':stress,'gui_stalls_ms':[450]*5 if stress else []}
                    browser.close()
                report.parent.mkdir(parents=True,exist_ok=True);report.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2));return result
            finally:
                if os.name=='posix':
                    try:os.killpg(server.pid,signal.SIGTERM)
                    except ProcessLookupError:pass
                else:server.terminate()
                try:server.wait(timeout=5)
                except subprocess.TimeoutExpired:server.kill();server.wait()


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--stress',action='store_true');parser.add_argument('--core',type=Path,required=True);parser.add_argument('--report',type=Path,default=ROOT/'validation/r210-cpp-live-controls-browser.json');args=parser.parse_args();probe(args.core.resolve(),args.report.resolve(),stress=args.stress)
