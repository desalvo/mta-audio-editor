"""Position requests must win over old clocks and asynchronous bridge responses."""
import json
import re
from pathlib import Path
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize('engine', ['web', 'native', 'server'])
def test_manual_transport_position_priority(engine):
    node = shutil.which('node')
    if not node:
        pytest.skip('Node required for production JavaScript transport regression')
    result = subprocess.run(
        [node, str(ROOT / 'tests/js/transport_position.cjs'), engine],
        cwd=ROOT, check=True, capture_output=True, text=True, timeout=30,
    )
    report = json.loads(result.stdout)
    assert report['mode'] == engine
    assert len(report['cases']) >= 4


@pytest.mark.parametrize('locale', ['it', 'en'])
@pytest.mark.parametrize('color_scheme', ['light', 'dark'])
def test_zone_grid_buttons_are_readable_and_dispatch_actions(locale, color_scheme):
    api = pytest.importorskip('playwright.sync_api')
    js = (ROOT / 'app/static/app.js').read_text()
    dialog = js[js.index('async function editMetronomeZoneBpm('):js.index('async function applyMetronomeZoneGrid(')]
    with api.sync_playwright() as p:
        try:
            browser = p.chromium.launch(headless=True, args=['--no-sandbox'])
        except api.Error as exc:
            pytest.skip('Chromium unavailable: ' + str(exc)[:160])
        page = browser.new_page(color_scheme=color_scheme, viewport={'width': 420, 'height': 700})
        page.set_content('<style>' + (ROOT / 'app/static/app.css').read_text() + '</style><main class="utility-body" id="dialog"></main>')
        page.evaluate('''locale=>{
          window.tr=(en,it)=>locale==='it'?it:en;
          window.metronomeZoneDescriptors=()=>[{start:6000,end:18000,bpm:112.5,signature:'4/4'}];
          window.fmtTime=String;window.metronomeSignatureOptions=()=>'<option>4/4</option>';
          window.showUtilityModal=(title,html)=>document.getElementById('dialog').innerHTML=html;
          window.actions=[];window.applyMetronomeZoneGrid=(start,reset)=>actions.push([start,reset]);
        }''', locale)
        page.add_script_tag(content=dialog)
        page.evaluate('editMetronomeZoneBpm(6000)')
        buttons = page.locator('#dialog button')
        assert buttons.all_text_contents() == (
            ['Applica e rigenera zona', 'Riporta in Auto'] if locale == 'it'
            else ['Apply and regenerate zone', 'Return to Auto']
        )
        for button in buttons.all():
            style = button.evaluate('''e=>{const s=getComputedStyle(e),r=e.getBoundingClientRect();return {foreground:s.webkitTextFillColor,background:s.backgroundColor,opacity:s.opacity,width:r.width,right:r.right}}''')
            def luminance(rgb):
                values = [int(x) / 255 for x in re.findall(r'\d+', rgb)[:3]]
                linear = [v / 12.92 if v <= .04045 else ((v + .055) / 1.055) ** 2.4 for v in values]
                return sum(a * b for a, b in zip(linear, [.2126, .7152, .0722], strict=True))
            fg, bg = luminance(style['foreground']), luminance(style['background'])
            assert (max(fg, bg) + .05) / (min(fg, bg) + .05) >= 4.5
            assert style['opacity'] == '1'
            assert style['width'] > 0 and style['right'] <= 420
            button.click()
        assert page.evaluate('actions') == [[6000, False], [6000, True]]
        browser.close()


@pytest.mark.parametrize('reuse', [False, True])
def test_native_prepare_remains_silent_until_latest_position_is_applied(tmp_path, monkeypatch, reuse):
    from app import native_transport as nt, storage, audio_engine, main, vst3_live
    from app.models import Project
    commands = []

    class Device:
        def __init__(self, *args):
            self.position = 0
            self.playing = reuse

        def update(self, project):
            return {'requires_prepare': False}

        def control(self, action, value=0):
            commands.append((action, value))
            if action == 'seek':
                self.position = value
            if action in ('play', 'pause'):
                self.playing = action == 'play'
            return self.status()

        def status(self):
            return {'position_ms': self.position, 'playing': self.playing}

        def close(self):
            pass

    monkeypatch.setattr(nt, '_DEVICE', Device() if reuse else None)
    monkeypatch.setattr(nt, '_SCRATCH', None)
    monkeypatch.setattr(nt, '_PROJECT', 'probe' if reuse else None)
    monkeypatch.setattr(nt, '_CANCEL_EPOCH', 0)
    monkeypatch.setattr(nt, '_guard', lambda: None)
    monkeypatch.setattr(nt, 'Device', Device)
    monkeypatch.setattr(storage, 'load_project', lambda pid: Project(id=pid, title='Probe'))
    monkeypatch.setattr(main, 'validate_project_files', lambda project: None)
    monkeypatch.setattr(audio_engine, 'render_mix', lambda *a, **kw: None)
    monkeypatch.setattr(vst3_live, 'available', lambda: False)
    try:
        status = nt.prepare_play('probe', 2000, start_playing=False)
        assert not status['playing'] and status['position_ms'] == 2000
        assert 'play' not in [action for action, value in commands]
        nt.control('seek', 9000)
        assert not nt._DEVICE.status()['playing']
        assert nt.control('play')['position_ms'] == 9000
    finally:
        nt.stop()


def test_native_bridge_forwards_prepare_playback_state(monkeypatch):
    from app import native_transport as nt
    from native.mta_audio_editor_native import NativeApi
    calls = []
    monkeypatch.setattr(nt, 'prepare_play', lambda *a, **kw: calls.append((a, kw)))
    NativeApi.transport_prepare_play(object(), 'project', 1250, {'route': 'midi'}, False)
    assert calls == [(('project', 1250), {'midi_options': {'route': 'midi'}, 'start_playing': False})]
