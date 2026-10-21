#!/usr/bin/env python3
"""Authenticated real-browser regression for audible transport seek priority."""
# ruff: noqa: S101 -- assertions are regression checks, not production guards
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


def probe(engine, report):
    import httpx
    from playwright.sync_api import sync_playwright
    with socket.socket() as listener:
        listener.bind(('127.0.0.1', 0))
        port = listener.getsockname()[1]
    with tempfile.TemporaryDirectory(prefix='mta-transport-probe-') as folder:
        base = Path(folder)
        config = base / 'config.json'
        env = {**os.environ, 'MTA_DATA_DIR': str(base / 'data'),
               'MTA_AI_JOB_STATE_DIR': str(base / 'jobs'),
               'MTA_ADMIN_PASSWORD': secrets.token_urlsafe(32),
               'MTA_LAYOUT_CONFIG': str(config), 'PYTHONPATH': str(ROOT),
               'OPENBLAS_NUM_THREADS': '1', 'MTA_NATIVE_SINGLE_USER': 'false',
               'MTA_ALLOW_INSECURE_NO_AUTH': 'false',
               'MTA_LAYOUT_PROBE_CPP': '1' if engine == 'cpp' else '0'}
        with (base / 'server.log').open('wb') as log:
            server = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), '--serve', str(port)],
                                      cwd=ROOT, env=env, stdout=log, stderr=log,
                                      start_new_session=os.name == 'posix')
            try:
                url = f'http://127.0.0.1:{port}'
                deadline = time.monotonic() + 90
                while time.monotonic() < deadline:
                    if server.poll() is not None:
                        raise RuntimeError((base / 'server.log').read_text()[-3000:])
                    try:
                        if httpx.get(url + '/api/health', trust_env=False, timeout=.3).status_code == 200:
                            break
                    except httpx.HTTPError:
                        pass
                    time.sleep(.1)
                else:
                    raise RuntimeError('Local server startup timeout')
                fixture = json.loads(config.read_text())
                result = {'engine': engine, 'positions': {}, 'javascript_errors': []}
                with sync_playwright() as p:
                    browser = p.chromium.launch(headless=True, args=['--no-sandbox', '--autoplay-policy=no-user-gesture-required'])
                    page = browser.new_page(user_agent='testclient', viewport={'width': 1440, 'height': 1000})
                    page.context.add_cookies([{'name': 'mta_session', 'value': fixture['cookie'], 'url': url}])
                    page.on('pageerror', lambda error: result['javascript_errors'].append(str(error)))
                    page.goto(url, wait_until='networkidle')
                    page.evaluate('(id)=>openP(id)', fixture['project'])
                    page.wait_for_selector('#ruler')
                    page.evaluate('async()=>{setZoom(25);current.follow_playback_enabled=false;await flushAutosave(true);goToTimestamp(1000)}')

                    # Delay the first preparation, then change position while its
                    # original start offset is already captured by the engine.
                    delayed = '**/vst3-live' if engine == 'cpp' else '**/audio/source-*.wav*'
                    def hold(route):
                        time.sleep(.3)
                        route.continue_()
                    page.route(delayed, hold)
                    page.evaluate('()=>{setTimeout(()=>goToTimestamp(6000),80);window.firstPlay=previewMaster()}')
                    page.evaluate('()=>window.firstPlay')
                    page.unroute(delayed, hold)

                    def check_position(name, expected):
                        page.wait_for_function('(target)=>playbackActuallyRunning()&&playCursorMs>=target+100&&playCursorMs<target+1500', arg=expected, timeout=20000)
                        result['positions'][name] = page.evaluate('playCursorMs')
                        if engine == 'current':
                            assert abs(page.evaluate('waStartCursorMs') - expected) < 2
                        else:
                            assert page.evaluate('mtaServerVst3.stats().mode') == 'worklet'
                        page.evaluate('()=>pausePlayback()')
                    check_position('during_preparation', 6000)

                    def click_time(selector, ms):
                        point = page.evaluate('''({selector,ms})=>{const pane=document.getElementById('timelinePane'),r=document.querySelector(selector).getBoundingClientRect(),p=pane.getBoundingClientRect();return {x:p.left+ms/1000*pxPerSec-pane.scrollLeft,y:r.top+Math.min(10,r.height/2)}}''', {'selector': selector, 'ms': ms})
                        page.mouse.click(point['x'], point['y'])
                    click_time('#ruler', 9000)
                    page.locator('#playMaster').click()
                    check_position('ruler_click_after_pause', 9000)

                    page.locator('#transportTime').fill('0:14.000')
                    page.locator('#transportTime').press('Enter')
                    page.locator('#playMaster').click()
                    check_position('numeric_input_after_pause', 14000)

                    page.evaluate('()=>{selectedTimelineSegments.clear();document.activeElement.blur();document.body.focus()}')
                    before = page.evaluate('playCursorMs')
                    page.keyboard.press('ArrowRight')
                    requested = before + 160  # 4 px at 25 px/s
                    page.locator('#playMaster').click()
                    check_position('keyboard_arrow_after_pause', requested)

                    page.evaluate("setTimelineTool('select')")
                    click_time('.lane[data-track="t0"]', 21000)
                    page.locator('#playMaster').click()
                    check_position('clip_click_after_pause', 21000)

                    page.evaluate('()=>stopPlayback()')
                    click_time('#ruler', 4000)
                    page.locator('#playMaster').click()
                    check_position('click_after_stop', 4000)
                    page.evaluate('()=>stopPlayback()')
                    assert not result['javascript_errors'], result['javascript_errors']
                    browser.close()
                report.parent.mkdir(parents=True, exist_ok=True)
                report.write_text(json.dumps(result, indent=2) + '\n')
                print(json.dumps(result))
            except BaseException:
                print((base / 'server.log').read_text()[-5000:], file=sys.stderr)
                raise
            finally:
                if server.poll() is None:
                    if os.name == 'posix':
                        os.killpg(server.pid, signal.SIGTERM)
                    else:
                        server.terminate()
                    try:
                        server.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        if os.name == 'posix':
                            os.killpg(server.pid, signal.SIGKILL)
                        else:
                            server.kill()
                        server.wait(timeout=5)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--serve', type=int)
    parser.add_argument('--engine', choices=['current', 'cpp'], default='current')
    parser.add_argument('--report', type=Path, default=ROOT / 'validation/r210-transport-browser.json')
    args = parser.parse_args()
    if args.serve:
        from scripts.validate_editor_layout import serve
        serve(args.serve)
    else:
        probe(args.engine, args.report)
