"""Regression checks for visible native zoom and recovery from a cold engine.

Backend contracts are explicit test doubles; they are not Windows/macOS/device
execution. The actual injected Android viewport JavaScript is executed by Node.
"""
import json
from pathlib import Path
import re
import subprocess
import sys
from types import SimpleNamespace

import pytest

from native import ui_zoom


@pytest.mark.parametrize('field', ['browser', 'webview', 'web_view'])
def test_nested_windows_wrapper_resolves_control_on_gui_thread(monkeypatch, field):
    state = {'gui': False}
    engine = SimpleNamespace(ZoomFactor=1)
    wrapper = SimpleNamespace(**{field: SimpleNamespace(webview=engine)})
    def dispatch(callback):
        state['gui'] = True
        try:
            callback()
        finally:
            state['gui'] = False
    class Native:
        InvokeRequired = True
        BeginInvoke = staticmethod(dispatch)
        @property
        def browser(self):
            assert state['gui'], 'Backend inspection must happen on GUI thread'
            return wrapper
    monkeypatch.setitem(sys.modules, 'System', SimpleNamespace(Action=lambda callback: callback))
    assert ui_zoom.apply_zoom(SimpleNamespace(native=Native()), 125) == 125
    assert engine.ZoomFactor == 1.25


def test_missing_backend_is_actionable_runtime_error():
    with pytest.raises(RuntimeError, match='not ready'):
        ui_zoom.apply_zoom(SimpleNamespace(native=object()), 125)


def test_gtk_dispatch_is_one_shot_on_main_loop(monkeypatch):
    seen = []
    def idle(callback):
        seen.append(callback())
    glib = SimpleNamespace(MainContext=SimpleNamespace(default=lambda:SimpleNamespace(is_owner=lambda:False)), idle_add=idle)
    monkeypatch.setitem(sys.modules, 'gi', SimpleNamespace())
    monkeypatch.setitem(sys.modules, 'gi.repository', SimpleNamespace(GLib=glib))
    engine = SimpleNamespace(set_zoom_level=lambda factor:seen.append(factor))
    assert ui_zoom.apply_zoom(SimpleNamespace(native=SimpleNamespace(webview=engine)), 80) == 80
    assert seen == [0.8, False]


def test_restore_failure_keeps_visible_controls_for_reset_and_numpad():
    source = Path('app/static/native_ui_zoom.js').read_text()
    script = r'''
const vm=require('vm'),assert=require('assert/strict');let key,changes=[],notices=[];
const buttons={};const host={hidden:true,setAttribute(){},querySelector:s=>buttons[s]||(buttons[s]={})};
const document={getElementById:()=>host,addEventListener:(name,fn)=>{key=fn}};
const ctx={document,window:{requestAnimationFrame:fn=>fn(),dispatchEvent(){}},Event:function(){}};
vm.createContext(ctx);vm.runInContext(process.argv[1],ctx);const zoom=ctx.window.mtaNativeZoom;
let invalid=false;
const api={restore_ui_zoom:async()=>{throw Error('Engine not ready')},set_ui_zoom:async n=>{changes.push(n);return {ok:true,zoom_percent:invalid?999:n}}};
(async()=>{
assert.equal(await zoom.init(api,{notify:m=>notices.push(m)}),true);
assert.equal(host.hidden,false);assert.equal(notices.length,1);
await zoom.reset();assert.deepEqual(changes,[100]);
key({ctrlKey:true,code:'NumpadAdd',key:'Unidentified',preventDefault(){},stopImmediatePropagation(){}});
await zoom.step(1);assert.equal(zoom.percent,125);
invalid=true;assert.equal(await zoom.step(1),false);assert.equal(zoom.percent,125);
invalid=false;await zoom.step(-1);assert.equal(zoom.percent,110);
})().catch(e=>{console.error(e);process.exitCode=1});
'''
    subprocess.run(['node','-e',script,source],check=True,timeout=15)


def test_controls_are_in_topbar_outside_collapsed_view_panel():
    html=Path('app/templates/index.html').read_text()
    assert html.index('id="nativeUiZoomControls"') < html.index('</header>')
    assert html.count('id="nativeUiZoomControls"') == 1


def test_android_viewport_allows_full_page_zoom_preserving_device_width():
    java=Path('mobile/android/app/src/main/java/com/desalvo/mtaaudioeditor/mobile/MainActivity.java').read_text()
    match=re.search(r'String viewport = (".*");',java)
    script=json.loads(match.group(1))
    check=r'''
const vm=require('vm'),assert=require('assert/strict');
const meta={content:'width=device-width,initial-scale=1,maximum-scale=1,user-scalable=no,viewport-fit=cover'};
const document={querySelector:()=>meta};
vm.runInNewContext(process.argv[1],{document});
assert.ok(meta.content.includes('width=device-width'));
assert.ok(meta.content.includes('viewport-fit=cover'));
assert.ok(meta.content.includes('minimum-scale=0.5'));
assert.ok(meta.content.includes('maximum-scale=2'));
assert.ok(meta.content.includes('user-scalable=yes'));
assert.ok(!meta.content.includes('user-scalable=no'));
'''
    subprocess.run(['node','-e',check,script],check=True,timeout=15)
    # Source contracts only: actual Android SDK/device coverage is separate.
    assert 'webView.zoomBy(' in java and '.setTextZoom(' not in java
    assert 'PREF_INTERFACE_ZOOM' in java and 'MENU_INTERFACE_ZOOM' in java
    assert 'generation != zoomChangeGeneration' in java
    swift=Path('mobile/ios/MTAEditorMobile/MobileWebViewController.swift').read_text()
    assert 'webView.pageZoom = Double(value) / 100' in swift
    assert 'UserDefaults.standard.set(value, forKey: Defaults.interfaceZoom)' in swift
    assert 'didFinish navigation: WKNavigation!' in swift


def test_webview2_waits_for_core_without_changing_or_claiming_scale():
    engine = SimpleNamespace(ZoomFactor=1, CoreWebView2=None)
    with pytest.raises(RuntimeError, match='core is not ready'):
        ui_zoom._set_engine_zoom(engine, 1.25)
    assert engine.ZoomFactor == 1
    engine.CoreWebView2 = SimpleNamespace(Settings=SimpleNamespace(IsZoomControlEnabled=True))
    ui_zoom._set_engine_zoom(engine, 1.25)
    assert engine.ZoomFactor == 1.25
    assert engine.CoreWebView2.Settings.IsZoomControlEnabled is False


def test_default_scale_sync_waits_for_bridge_and_paint_then_serializes_user_choice():
    source = Path('app/static/native_ui_zoom.js').read_text()
    script = r'''
const vm=require('vm'),assert=require('assert/strict');let frames=[],calls=[],restored=false,key;
const buttons={};const host={hidden:true,setAttribute(){},querySelector:s=>buttons[s]||(buttons[s]={})};
const document={getElementById:()=>host,addEventListener:(name,fn)=>{key=fn}};
const ctx={document,window:{requestAnimationFrame:fn=>frames.push(fn),dispatchEvent(){}},Event:function(){}};
vm.createContext(ctx);vm.runInContext(process.argv[1],ctx);const zoom=ctx.window.mtaNativeZoom;
const api={restore_ui_zoom:async()=>{restored=true;return {ok:true,zoom_percent:100}},set_ui_zoom:async n=>{assert.ok(restored);calls.push(n);return {ok:true,zoom_percent:n}}};
(async()=>{
assert.equal(await zoom.init(null),false);assert.equal(calls.length,0);
const initialization=zoom.init(api);await new Promise(setImmediate);
assert.equal(host.hidden,false);assert.equal(typeof key,'function');
assert.deepEqual(calls,[]);assert.equal(frames.length,1);
const manual=zoom.step(1);frames.shift()();
await initialization;await manual;
assert.deepEqual(calls,[100,110]);assert.equal(zoom.percent,110);
await zoom.init(api);assert.deepEqual(calls,[100,110]);
})().catch(e=>{console.error(e);process.exitCode=1});
'''
    subprocess.run(['node','-e',script,source],check=True,timeout=15)


def test_default_sync_failure_does_not_hide_manual_recovery():
    source = Path('app/static/native_ui_zoom.js').read_text()
    script = r'''
const vm=require('vm'),assert=require('assert/strict');let calls=0,notices=[];
const buttons={};const host={hidden:true,setAttribute(){},querySelector:s=>buttons[s]||(buttons[s]={})};
const document={getElementById:()=>host,addEventListener(){}};
const ctx={document,window:{requestAnimationFrame:fn=>fn(),dispatchEvent(){}},Event:function(){}};
vm.createContext(ctx);vm.runInContext(process.argv[1],ctx);const zoom=ctx.window.mtaNativeZoom;
const api={restore_ui_zoom:async()=>({ok:true,zoom_percent:100}),set_ui_zoom:async n=>{if(++calls===1)throw Error('Core still starting');return {ok:true,zoom_percent:n}}};
(async()=>{
assert.equal(await zoom.init(api,{notify:s=>notices.push(s)}),true);
assert.equal(host.hidden,false);assert.equal(zoom.percent,100);assert.equal(notices.length,1);
assert.equal(await zoom.reset(),true);assert.equal(calls,2);assert.equal(zoom.percent,100);
})().catch(e=>{console.error(e);process.exitCode=1});
'''
    subprocess.run(['node','-e',script,source],check=True,timeout=15)
