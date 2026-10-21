"""Opt-in real Chromium + HTTP + actual VST3 worker. No WebAudio/HTTP mocks."""
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import time

import numpy as np
import pytest
import soundfile as sf
from fastapi import Request
from app import auth,storage
from test_r210_server_vst3 import server  # noqa: F401
from test_r210_cpp_audio_engine import compiled_core  # noqa: F401
from test_r210_live_vst3 import real_plugin  # noqa: F401


@pytest.mark.skipif(os.getenv('MTA_TEST_BROWSER_VST3')!='1',reason='Set MTA_TEST_BROWSER_VST3=1 with Playwright/Chromium installed')
def test_real_browser_live_play_pause_seek_parameter_update_and_stop(request,tmp_path,chromium_capability):
    api=pytest.importorskip('playwright.sync_api')
    import httpx
    _,project,source,_,_,user,_=request.getfixturevalue('server')
    project.tracks[0].duration_ms=30000
    clock=np.arange(48000*30)/48000
    sf.write(source,np.column_stack([.14*np.sin(2*np.pi*211*clock),.13*np.sin(2*np.pi*331*clock)]),48000,subtype='FLOAT')
    storage.save_project(project,_skip_flac_conversion=True)
    with socket.socket() as listener:
        listener.bind(('127.0.0.1',0));port=listener.getsockname()[1]
    root=Path(__file__).resolve().parents[1];base=f'http://127.0.0.1:{port}'
    env={**os.environ,'MTA_DEMUCS_MODEL_AUTO_UPDATE':'false'}
    if env.get('MTA_TEST_VSTI'):
        env['MTA_VST3_PATHS']=env.get('MTA_VST3_PATHS','')+os.pathsep+str(Path(env['MTA_TEST_VSTI']).parent)
    with (tmp_path/'http-server.log').open('wb') as log:
        proc=subprocess.Popen([sys.executable,'-m','uvicorn','app.main:app','--host','127.0.0.1','--port',str(port)],cwd=root,env=env,stdout=log,stderr=log,start_new_session=os.name=='posix')
        try:
            with httpx.Client(trust_env=False) as probe:
                deadline=time.monotonic()+30
                while True:
                    try:
                        if probe.get(base+'/api/health',timeout=1).status_code==200:break
                    except httpx.HTTPError:pass
                    if proc.poll() is not None or time.monotonic()>deadline:pytest.fail((tmp_path/'http-server.log').read_text()[-4000:])
                    time.sleep(.1)
            with api.sync_playwright() as pw:
                browser=pw.chromium.launch(headless=True,args=['--no-sandbox','--autoplay-policy=no-user-gesture-required','--use-fake-ui-for-media-stream','--use-fake-device-for-media-stream'])
                context=browser.new_context();page=context.new_page();ua=page.evaluate('navigator.userAgent')
                req=Request({'type':'http','headers':[(b'user-agent',ua.encode())]})
                context.add_cookies([{'name':'mta_session','value':auth.create_session(user,req),'url':base,'httpOnly':True,'sameSite':'Lax'}])
                streams=[];errors=[]
                page.on('pageerror',lambda exc:errors.append(str(exc)))
                page.on('response',lambda response:streams.append(response) if response.url.endswith('/pcm') else None)
                page.goto(base+'/?ai_project='+project.id,wait_until='domcontentloaded')
                # Playwright's in-page wait_for_function uses eval, forbidden by
                # MTA's CSP. Poll from the test process; keep the CSP unchanged.
                def wait_for(expression,argument=None,timeout=15):
                    deadline=time.monotonic()+timeout
                    while not page.evaluate(expression,argument):
                        if time.monotonic()>deadline:pytest.fail('Browser condition timed out: '+expression+'; errors='+repr(errors)+'; MIDI='+str(page.locator('#midiLiveStatus').text_content() if page.locator('#midiLiveStatus').count() else ''))
                        page.wait_for_timeout(50)
                wait_for('(pid)=>typeof current!=="undefined"&&current?.id===pid',project.id)
                page.evaluate('() => window.previewMaster()')
                wait_for('() => window.playbackActuallyRunning() && playCursorMs>100')
                assert streams and any(r.status==200 for r in streams)
                assert page.evaluate('() => audioCtx.state')=='running'
                page.evaluate('() => window.pausePlayback()')
                paused=page.evaluate('() => playCursorMs');page.wait_for_timeout(150)
                assert abs(page.evaluate('() => playCursorMs')-paused)<5
                assert not page.evaluate('() => window.playbackActuallyRunning()')
                page.evaluate('() => window.goToTimestamp(500)');page.wait_for_timeout(150)
                page.evaluate('() => window.resumePlayback()')
                wait_for('() => window.playbackActuallyRunning() && playCursorMs>550',timeout=10)
                page.evaluate('() => openVst3Config(false,"tape","tone")')
                control=page.locator('.vst3-parameter').first
                control.wait_for(state='visible')
                parameter=control.get_attribute('data-name')
                labels=page.locator('.insert-setup-actions button').all_text_contents()
                assert 'Original plugin editor' in labels or 'Editor originale del plugin' in labels
                if __import__('app.server_vst3_display',fromlist=['available']).available():
                    page.evaluate('() => openOriginalVst3Editor("tape","tone")')
                    wait_for('() => {const c=document.querySelector(".remote-vst-window canvas");return c&&c.width>10&&c.width<1600}',timeout=20)
                    page.locator('.remote-vst-window [data-close]').click()
                    wait_for('() => !document.querySelector(".remote-vst-window")',timeout=15)
                with page.expect_response(lambda r:'/control' in r.url and r.request.method=='POST'):
                    control.evaluate('(el) => {el.value="0.29";el.dispatchEvent(new Event("input",{bubbles:true}))}')
                assert storage.load_project(project.id).tracks[0].inserts[0].params[parameter]==pytest.approx(.29)
                with page.expect_response(lambda r:'/control' in r.url and r.request.method=='POST'):
                    page.evaluate('() => {current.master_volume_db=-9;window.updatePlaybackGains()}')
                page.evaluate('() => window.stopPlayback()');page.wait_for_timeout(150)
                assert not page.evaluate('() => window.playbackActuallyRunning()')
                # Actual MIDI editor: create, piano roll, numeric note edit,
                # save/reopen. With an installed VSTi, also play the MIDI-only
                # project through the real server worker and WebAudio stream.
                page.evaluate('() => closeUtilityModal()')
                page.evaluate('() => createMidiTrack()')
                page.locator('#midiRoll').wait_for(state='visible')
                assert page.locator('#midiSave').evaluate('(el)=>getComputedStyle(el).backgroundColor')=='rgb(3, 105, 161)'
                page.locator('#midiRoll').dblclick(position={'x':120,'y':1076})
                page.locator('#midiNoteFields input[data-key="pitch"]').fill('64')
                page.locator('#midiNoteFields input[data-key="pitch"]').dispatch_event('change')
                page.locator('#midiNoteFields input[data-key="start_ms"]').fill('0')
                page.locator('#midiNoteFields input[data-key="start_ms"]').dispatch_event('change')
                page.locator('#midiNoteFields input[data-key="duration_ms"]').fill('1500')
                page.locator('#midiNoteFields input[data-key="duration_ms"]').dispatch_event('change')
                page.screenshot(path=str(tmp_path/'midi-editor.png'))
                if env.get('MTA_TEST_VSTI'):
                    page.locator('#midiInstrument').select_option(label=Path(env['MTA_TEST_VSTI']).stem)
                    page.locator('#midiLoad').click()
                    wait_for('() => document.querySelectorAll("#midiParameters input").length>0',timeout=30)
                page.locator('#midiSave').click()
                wait_for('() => current.tracks.some(t=>t.kind==="midi"&&t.midi_notes?.some(n=>n.pitch===64&&n.duration_ms===1500))')
                saved=storage.load_project(project.id);midi_track=saved.tracks[-1]
                assert midi_track.kind=='midi' and midi_track.midi_notes[0].pitch==64
                # A deterministic virtual MIDI port tests browser permission/input
                # plumbing; audio, HTTP and the instrument remain real.
                page.evaluate('() => {window.testMidiPort=Object.assign(new EventTarget(),{id:"test",name:"Test keyboard"});navigator.requestMIDIAccess=async()=>({inputs:new Map([["test",window.testMidiPort]]),outputs:new Map()})}')
                page.locator('#midiInput').click()
                wait_for('() => typeof window.testMidiPort.onmidimessage==="function"')
                page.evaluate('() => {window.testMidiPort.onmidimessage({data:[176,64,127]});window.testMidiPort.onmidimessage({data:[144,67,95]})}')
                page.wait_for_timeout(50)
                page.evaluate('() => window.testMidiPort.onmidimessage({data:[128,67,0]})')
                page.locator('#midiInput').click()
                assert page.evaluate('() => window.testMidiPort.onmidimessage===null')
                page.locator('#midiSave').click()
                wait_for('() => current.tracks.some(t=>t.kind==="midi"&&t.midi_notes?.length===2)')
                assert storage.load_project(project.id).tracks[-1].midi_controls[0].data==[176,64,127]
                page.evaluate('(id) => openMidiEditor(id)',midi_track.id)
                wait_for('() => document.getElementById("midiNoteFields")?.textContent.includes("2 ")')
                if env.get('MTA_TEST_VSTI'):
                    # Audition must work with a stopped project transport.
                    page.evaluate('() => {window.monitorPeak=0;const old=AudioBufferSourceNode.prototype.start;AudioBufferSourceNode.prototype.start=function(...args){if(this.buffer)for(const v of this.buffer.getChannelData(0))window.monitorPeak=Math.max(window.monitorPeak,Math.abs(v));return old.apply(this,args)}}')
                    page.locator('#midiMonitorToggle').click()
                    wait_for('() => /Stop monitoring|Ferma monitoring/.test(document.getElementById("midiMonitorToggle")?.textContent)',timeout=30)
                    key=page.locator('#midiPad button[data-midi-note="60"]')
                    key.hover();page.mouse.down()
                    wait_for('() => window.monitorPeak>0.00001')
                    page.mouse.up()
                    assert not page.evaluate('() => window.playbackActuallyRunning()')
                    page.locator('#midiPanic').click()
                    page.locator('#midiMonitorToggle').click()
                    wait_for('() => /Start monitoring|Avvia monitoring/.test(document.getElementById("midiMonitorToggle")?.textContent)')
                # Real browser scheduler with a virtual MIDI output: note-on,
                # clock, pause/continue and Panic must reach the selected port.
                page.evaluate('() => {window.hardwareMidi=[];window.outputMidiPort={id:"output",name:"Test output",send:(data,time)=>window.hardwareMidi.push([...data]),clear:()=>{}};navigator.requestMIDIAccess=async()=>({inputs:new Map([["test",window.testMidiPort]]),outputs:new Map([["output",window.outputMidiPort]])})}')
                page.locator('#midiConnect').click()
                wait_for('() => document.querySelectorAll("#midiLiveOutput option").length===2')
                page.locator('#midiLiveOutput').select_option('output')
                page.locator('#midiRoute').select_option('hardware')
                page.locator('#midiSendClock').check()
                page.locator('#midiSave').click()
                wait_for('() => current.tracks.some(t=>t.kind==="midi"&&t.midi_route==="hardware")')
                page.evaluate('() => window.goToTimestamp(0)')
                page.evaluate('() => window.previewMaster()')
                wait_for('() => window.hardwareMidi.some(m=>m[0]===144&&m[1]===64)')
                wait_for('() => window.hardwareMidi.some(m=>m[0]===248)')
                assert page.locator('#midiRoute').is_visible(), 'Audio preparation replaced or hid the open MIDI editor'
                assert page.locator('#midiRoute').input_value()=='hardware'
                page.evaluate('() => window.pausePlayback()')
                wait_for('() => window.hardwareMidi.some(m=>m[0]===252)')
                page.evaluate('() => window.resumePlayback()')
                wait_for('() => window.hardwareMidi.some(m=>m[0]===251||m[0]===250)')
                page.evaluate('() => window.stopPlayback()')
                assert page.evaluate('() => window.hardwareMidi.some(m=>(m[0]&240)===176&&m[1]===123)')
                assert page.locator('#midiRoute').is_visible(), 'Stopping playback must preserve the MIDI editor'
                page.locator('#midiRoute').select_option('instrument')
                page.locator('#midiSave').click()
                wait_for('() => current.tracks.some(t=>t.kind==="midi"&&t.midi_route==="instrument")')
                if env.get('MTA_TEST_VSTI'):
                    page.evaluate('() => closeUtilityModal()')
                    page.evaluate('() => {current.tracks=current.tracks.filter(t=>t.kind==="midi");current.master_inserts=[]}')
                    page.evaluate('() => window.previewMaster()')
                    wait_for('() => window.playbackActuallyRunning() && playCursorMs>100')
                    page.evaluate('() => window.stopPlayback()')
                page.evaluate('() => closeUtilityModal()')
                page.evaluate('() => openAudioCapture()')
                page.locator('#captureName').wait_for(state='visible')
                page.locator('#captureName').fill('Browser live input')
                page.locator('#captureStart').click()
                wait_for('() => document.getElementById("captureStop")?.disabled===false',timeout=20)
                page.wait_for_timeout(500)
                page.locator('#captureStop').click()
                wait_for('() => current.tracks.some(t=>t.name==="Browser live input")',timeout=20)
                recorded=next(t for t in storage.load_project(project.id).tracks if t.name=='Browser live input')
                assert recorded.duration_ms>100 and storage.audio_path(project.id,recorded.filename).is_file()
                assert not errors,errors
                browser.close()
        finally:
            if proc.poll() is None:
                proc.terminate()
                try:proc.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    if os.name=='posix':os.killpg(proc.pid,signal.SIGKILL)
                    else:proc.kill()
                    proc.wait(timeout=5)
