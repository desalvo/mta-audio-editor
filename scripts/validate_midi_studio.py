#!/usr/bin/env python3
"""Authenticated browser regression of the real MIDI editor and DB preferences."""
# ruff: noqa: S101 -- test assertions, not security checks
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

ROOT = Path(__file__).resolve().parents[1]


def probe(report):
    import httpx
    from playwright.sync_api import sync_playwright
    with socket.socket() as listener:
        listener.bind(('127.0.0.1', 0))
        port = listener.getsockname()[1]
    with tempfile.TemporaryDirectory(prefix='mta-midi-ui-') as folder:
        base = Path(folder)
        config = base/'fixture.json'
        env = {**os.environ, 'MTA_DATA_DIR': str(base/'data'), 'MTA_AI_JOB_STATE_DIR': str(base/'jobs'),
               'MTA_ADMIN_PASSWORD': secrets.token_urlsafe(32), 'MTA_LAYOUT_CONFIG': str(config),
               'PYTHONPATH': str(ROOT), 'OPENBLAS_NUM_THREADS': '1',
               'MTA_NATIVE_SINGLE_USER': 'false', 'MTA_ALLOW_INSECURE_NO_AUTH': 'false'}
        with (base/'server.log').open('wb') as log:
            server = subprocess.Popen([sys.executable, str(ROOT/'scripts/validate_editor_layout.py'), '--serve', str(port)],
                                      cwd=ROOT, env=env, stdout=log, stderr=log, start_new_session=os.name == 'posix')
            try:
                url = f'http://127.0.0.1:{port}'
                deadline = time.monotonic()+90
                while time.monotonic() < deadline:
                    if server.poll() is not None:
                        raise RuntimeError((base/'server.log').read_text()[-4000:])
                    try:
                        if httpx.get(url+'/api/health', timeout=.3, trust_env=False).status_code == 200:
                            break
                    except httpx.HTTPError:
                        pass
                    time.sleep(.1)
                else:
                    raise RuntimeError('Browser fixture startup timeout')
                fixture = json.loads(config.read_text())
                result = {}
                with sync_playwright() as p:
                    browser = p.chromium.launch(headless=True, args=['--no-sandbox'])
                    page = browser.new_page(user_agent='testclient', viewport={'width': 1100, 'height': 760})
                    page.context.add_cookies([{'name': 'mta_session', 'value': fixture['cookie'], 'url': url}])
                    errors = []
                    page.on('pageerror', lambda error: errors.append(str(error)))
                    page.goto(url, wait_until='networkidle')
                    assert page.locator('#midiToolsPanel').evaluate('(e)=>e.classList.contains("collapsed")')
                    page.evaluate('(id)=>openP(id)', fixture['project'])
                    page.evaluate('()=>createMidiTrack()')
                    page.wait_for_selector('#midiAdvanced')
                    page.evaluate('''()=>{mtaMidiEditor.mutate(d=>{d.midi_notes=[{id:'one',start_ms:100,duration_ms:400,pitch:60,velocity:100,channel:0},{id:'two',start_ms:800,duration_ms:300,pitch:64,velocity:90,channel:0}];d.duration_ms=3600000});mtaMidiEditor.select(['one','two'])}''')
                    page.locator('#midiAdvanced details').first.evaluate('(e)=>e.open=true')
                    page.fill('#midiTransformValue', '2')
                    page.click('[data-midi-transform=transpose]')
                    assert page.evaluate('mtaMidiEditor.getDraft().midi_notes.map(n=>n.pitch)') == [62, 66]
                    page.click('#midiUndo')
                    assert page.evaluate('mtaMidiEditor.getDraft().midi_notes.map(n=>n.pitch)') == [60, 64]
                    page.click('#midiRedo')
                    assert page.evaluate('mtaMidiEditor.getDraft().midi_notes.map(n=>n.pitch)') == [62, 66]
                    page.locator('#midiControlLane').evaluate('(e)=>e.open=true')
                    page.fill('#midiControlTime','500')
                    page.fill('#midiControlValue','100')
                    page.click('#midiControlAdd')
                    assert page.evaluate('mtaMidiEditor.getDraft().midi_controls[0].data')==[176,1,100]
                    page.locator('#midiControlCanvas').press('ArrowUp')
                    assert page.evaluate('mtaMidiEditor.getDraft().midi_controls[0].data')==[176,1,101]
                    page.click('#midiUndo')
                    assert page.evaluate('mtaMidiEditor.getDraft().midi_controls[0].data')==[176,1,100]
                    page.select_option('#midiControlKind','224')
                    page.fill('#midiControlValue','16383')
                    page.click('#midiControlAdd')
                    assert page.evaluate('mtaMidiEditor.getDraft().midi_controls[1].data')==[224,127,127]
                    page.locator('#midiControlCanvas').press('Delete')
                    assert page.evaluate('mtaMidiEditor.getDraft().midi_controls.length')==1
                    result['controller_cc_bend_keyboard_undo_delete']=True
                    page.select_option('#midiControlKind','176')
                    if os.getenv('MTA_STUDIO_SCREENSHOT_DIR'):
                        image_root=Path(os.environ['MTA_STUDIO_SCREENSHOT_DIR']);image_root.mkdir(parents=True,exist_ok=True)
                        page.locator('#midiControlLane').screenshot(path=str(image_root/'midi-controller-lanes.png'))
                    page.evaluate("mtaMidiEditor.zoom(8)")
                    assert page.locator('#midiRoll').evaluate('(e)=>e.width') <= 4096
                    assert page.locator('#midiRollStage').evaluate('(e)=>e.scrollWidth') > 100000
                    result['group_edit_undo_redo_and_large_canvas'] = True
                    page.evaluate('()=>mtaMidiEditor.save()')
                    tid = page.evaluate('mtaMidiEditor.getDraft().id')
                    page.evaluate('closeUtilityModal()')
                    page.evaluate('(tid)=>openMidiEditor(tid)', tid)
                    assert page.evaluate('mtaMidiEditor.getDraft().midi_notes.map(n=>n.pitch)') == [62, 66]
                    assert page.evaluate('mtaMidiEditor.getDraft().midi_controls[0].data')==[176,1,100]
                    result['persisted_midi_notes_after_reopen'] = True
                    page.evaluate('closeUtilityModal()')
                    page.evaluate("()=>{toggleMidiToolsPanel();MtaPreferences.setItem('mta.test.lazy','db-value')}")
                    page.wait_for_timeout(1400)
                    prefs = page.evaluate('async()=>await (await fetch("/api/account/preferences")).json()')
                    assert prefs['values']['mta.test.lazy'] == 'db-value'
                    page.reload(wait_until='networkidle')
                    assert page.evaluate("MtaPreferences.getItem('mta.test.lazy')") == 'db-value'
                    assert not page.locator('#midiToolsPanel').evaluate('(e)=>e.classList.contains("collapsed")')
                    result['lazy_db_preferences_and_sidebar_reload'] = True
                    page.evaluate('()=>openMetronomeGraph()')
                    page.wait_for_selector('#metronomeGraph')
                    assert page.locator('#metronomeGraph').evaluate('(e)=>e.width') > 100
                    before = page.evaluate('metronomeZoneDescriptors()[0].bpm')
                    for _ in range(3):
                        page.locator('#metronomeGraph').press('ArrowUp')
                    page.wait_for_function('(target)=>Math.abs(metronomeZoneDescriptors()[0].bpm-target)<.001',arg=before+.3)
                    result['tempo_graph_repeated_keys_applied'] = True
                    height = page.locator('.lane[data-track]').first.evaluate('(e)=>e.clientHeight')
                    page.select_option('#metronomeGraphMode','overlay')
                    page.wait_for_selector('#metronomeOverlay')
                    assert page.locator('.lane[data-track]').first.evaluate('(e)=>e.clientHeight') == height
                    result['tempo_overlay_keeps_track_geometry'] = True
                    result['tempo_graph_opened'] = True
                    page.evaluate('closeUtilityModal()')
                    page.evaluate("()=>openAiStudio('vocal-harmony')")
                    page.wait_for_selector('#studioRun')
                    assert page.locator('[data-studio-tab=source]').get_attribute('aria-selected')=='true'
                    page.click('[data-studio-tab=singers]')
                    assert page.locator('[data-studio-panel=singers]').is_visible()
                    page.click('[data-studio-tab=execution]')
                    if os.getenv('MTA_STUDIO_SCREENSHOT_DIR'):
                        page.locator('.ai-studio').screenshot(path=str(image_root/'ai-vocal-midi-workflow.png'))
                    assert page.locator('#studioCPU').inner_text()=='—'
                    page.evaluate('closeUtilityModal()')
                    page.evaluate("()=>openAiStudio('audio-to-midi')")
                    page.wait_for_selector('#studioOnset',state='attached')
                    assert page.locator('[data-studio-tab=singers]').count()==0
                    page.click('[data-studio-tab=execution]')
                    assert page.locator('#studioModels').evaluate('(e)=>{const s=getComputedStyle(e);return s.color!==s.backgroundColor&&s.backgroundColor!=="rgb(239, 239, 239)"}')
                    page.click('#studioModels')
                    page.wait_for_selector('#studioInstall')
                    assert page.locator('#studioLicense').is_visible()
                    result['studio_tabs_models_and_close_without_job']=True
                    assert not errors, errors
                    result['javascript_errors'] = errors
                    browser.close()
                report.parent.mkdir(parents=True, exist_ok=True)
                report.write_text(json.dumps(result, indent=2))
                print(json.dumps(result))
            finally:
                if os.name == 'posix':
                    os.killpg(server.pid, signal.SIGTERM)
                else:
                    server.terminate()
                try:
                    server.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    server.kill()
                    server.wait()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--report', type=Path, required=True)
    probe(parser.parse_args().report)
