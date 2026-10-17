"""Native engine page zoom, durable preferences and browser-safe controls."""
import json
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest
from native import ui_zoom


@pytest.mark.parametrize('value', [None, True, False, '80', 49, 201, 80.5, {}])
def test_invalid_zoom_is_rejected_without_writing(tmp_path, value):
    with pytest.raises(ValueError): ui_zoom.save_zoom(tmp_path, value)
    assert not (tmp_path / 'native-ui-zoom.json').exists()


def test_zoom_persistence_and_corrupt_preference_fallback(tmp_path):
    assert ui_zoom.load_zoom(tmp_path) == 100
    ui_zoom.save_zoom(tmp_path, 80)
    assert ui_zoom.load_zoom(tmp_path) == 80
    assert not list(tmp_path.glob('.ui-zoom-*'))
    (tmp_path / 'native-ui-zoom.json').write_text('{broken')
    assert ui_zoom.load_zoom(tmp_path) == 100
    (tmp_path / 'native-ui-zoom.json').write_text(json.dumps({'zoom_percent': 999}))
    assert ui_zoom.load_zoom(tmp_path) == 100


def test_symlink_preference_is_not_followed(tmp_path):
    outside = tmp_path / 'outside.json'; outside.write_text('{"zoom_percent":80}')
    (tmp_path / 'native-ui-zoom.json').symlink_to(outside)
    assert ui_zoom.load_zoom(tmp_path) == 100
    ui_zoom.save_zoom(tmp_path, 90)
    assert outside.read_text() == '{"zoom_percent":80}'
    assert ui_zoom.load_zoom(tmp_path) == 90


@pytest.mark.parametrize('method', ['setPageZoom_', 'set_zoom_level', 'setZoomFactor'])
def test_web_engine_factor_uses_full_page_api(method):
    seen=[];engine=SimpleNamespace(**{method:seen.append})
    ui_zoom._set_engine_zoom(engine, 0.8)
    assert seen == [0.8]


def test_windows_zoom_runs_through_ui_dispatch(monkeypatch):
    state={'gui':False};seen=[]
    class Engine:
        CoreWebView2 = SimpleNamespace(Settings=SimpleNamespace(IsZoomControlEnabled=True))
        @property
        def ZoomFactor(self):return 1
        @ZoomFactor.setter
        def ZoomFactor(self, value):
            assert state['gui'];seen.append(value)
    def invoke(callback):
        state['gui']=True
        try:callback()
        finally:state['gui']=False
    monkeypatch.setitem(sys.modules, 'System', SimpleNamespace(Action=lambda callback:callback))
    window=SimpleNamespace(native=SimpleNamespace(webview=Engine(),InvokeRequired=True,Invoke=invoke))
    assert ui_zoom.apply_zoom(window,80)==80 and seen==[0.8]
    assert window.native.webview.CoreWebView2.Settings.IsZoomControlEnabled is False


def test_macos_zoom_runs_on_scheduled_gui_thread(monkeypatch):
    seen=[];scheduled=[]
    monkeypatch.setattr(ui_zoom.sys,'platform','darwin')
    monkeypatch.setitem(sys.modules,'Foundation',SimpleNamespace(NSThread=SimpleNamespace(isMainThread=lambda:False)))
    def call_after(callback):scheduled.append(True);callback()
    monkeypatch.setitem(sys.modules,'PyObjCTools',SimpleNamespace(AppHelper=SimpleNamespace(callAfter=call_after)))
    engine=SimpleNamespace(setPageZoom_=seen.append)
    backend=SimpleNamespace(BrowserView=SimpleNamespace(instances={'main':SimpleNamespace(webview=engine)}))
    window=SimpleNamespace(native=SimpleNamespace(),gui=backend,uid='main')
    assert ui_zoom.apply_zoom(window,125)==125
    assert scheduled==[True] and seen==[1.25]


def test_missing_native_window_is_reported():
    with pytest.raises(RuntimeError,match='not ready'):ui_zoom.apply_zoom(None,80)


def test_native_bridge_restores_saved_zoom_and_keeps_it_on_failure(tmp_path,monkeypatch):
    from native import mta_audio_editor_native as launcher
    monkeypatch.setattr(launcher,'_data_root',lambda:tmp_path)
    seen=[]
    monkeypatch.setattr(ui_zoom,'apply_zoom',lambda window,value:seen.append(value) or value)
    api=launcher.NativeApi()
    assert api.set_ui_zoom(80)=={'ok':True,'zoom_percent':80}
    restored=launcher.NativeApi()
    assert restored.restore_ui_zoom()=={'ok':True,'zoom_percent':80}
    assert seen==[80,80]
    def fail(*args):raise RuntimeError('fixture engine failed')
    monkeypatch.setattr(ui_zoom,'apply_zoom',fail)
    with pytest.raises(RuntimeError):restored.set_ui_zoom(90)
    assert ui_zoom.load_zoom(tmp_path)==80


def test_native_zoom_shortcuts_serialize_changes_and_web_stays_inert():
    source=Path('app/static/native_ui_zoom.js').read_text()
    script=r'''
const vm=require('vm'),assert=require('assert');let keyboard,prevented=0,stopped=0,changes=[],notices=[];
const buttons={};const host={hidden:true,setAttribute(){},querySelector:s=>buttons[s]||(buttons[s]={})};
const document={getElementById:()=>host,addEventListener:(name,fn)=>{assert.equal(name,'keydown');keyboard=fn}};
const ctx={document,window:{requestAnimationFrame:fn=>fn(),dispatchEvent:()=>{}},Event:function(type){this.type=type}};
vm.createContext(ctx);vm.runInContext(process.argv[1],ctx);const zoom=ctx.window.mtaNativeZoom;
const key=(k,meta=false)=>({key:k,ctrlKey:!meta,metaKey:meta,altKey:false,preventDefault:()=>prevented++,stopImmediatePropagation:()=>stopped++});
(async()=>{assert.equal(await zoom.init(null),false);assert.equal(host.hidden,true);assert.equal(keyboard,undefined);
let fail=false;const api={restore_ui_zoom:async()=>({ok:true,zoom_percent:80}),set_ui_zoom:async n=>{if(fail)throw Error('fixture');changes.push(n);return {ok:true,zoom_percent:n}}};
assert.equal(await zoom.init(api,{language:()=> 'en',notify:x=>notices.push(x)}),true);assert.equal(host.hidden,false);assert.equal(zoom.percent,80);
keyboard(key('+'));keyboard(key('=',true));await zoom.step(-1);assert.deepEqual(changes,[90,100,90]);
keyboard(key('0',true));await zoom.step(0);assert.equal(zoom.percent,100);assert.equal(prevented,3);assert.equal(stopped,3);
keyboard(key('s'));assert.equal(prevented,3);fail=true;await zoom.step(1);assert.equal(zoom.percent,100);assert.equal(notices.length,1);
fail=false;for(let i=0;i<15;i++)await zoom.step(1);assert.equal(zoom.percent,200);for(let i=0;i<25;i++)await zoom.step(-1);assert.equal(zoom.percent,50);
assert.ok(host.innerHTML.includes('50%'));assert.ok(!process.argv[1].includes('style.zoom'));
})().catch(e=>{console.error(e);process.exitCode=1});
'''
    result=subprocess.run(['node','-e',script,source],capture_output=True,text=True,timeout=10)
    assert result.returncode==0,result.stderr


def test_controls_hidden_until_confirmed_native_bridge_and_loaded_before_app():
    html=Path('app/templates/index.html').read_text()
    assert 'id="nativeUiZoomControls" class="native-ui-zoom" role="group" hidden' in html
    assert html.index('/static/native_ui_zoom.js')<html.index('/static/app.js')
    js=Path('app/static/app.js').read_text()
    assert 'window.mtaNativeZoom.init(nativeBridge,{language:()=>uiLanguage,notify:toast})' in js
    css=Path('app/static/app.css').read_text()
    assert '.native-ui-zoom-buttons' in css
