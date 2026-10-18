"""Cold bridge exposure, Windows STA dialogs, zoom dispatch and one-click creation."""
import inspect
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
import pytest
from native import gui_dialogs,ui_zoom,mta_audio_editor_native as launcher
from test_r210_decimal_bpm_shortcuts import function


def test_bridge_introspection_never_touches_window_or_paths(tmp_path,monkeypatch):
    monkeypatch.setattr(launcher,'_data_root',lambda:tmp_path)
    class Hostile:
        def __getattribute__(self,name):raise AssertionError('GUI introspection: '+name)
    api=launcher.NativeApi();api.window=Hostile();api.project_paths=Hostile();api.startup_project_path=Hostile()
    exported={name:getattr(api,name) for name in dir(api) if not name.startswith('_')}
    assert {'choose_project_save_path','open_project','restore_ui_zoom','bind_project_path'}<=exported.keys()
    assert not {'window','project_paths','startup_project_path'}&exported.keys()
    assert all(inspect.ismethod(value) or inspect.isfunction(value) for value in exported.values())


def test_fresh_zoom_restore_does_not_touch_cold_webview(tmp_path,monkeypatch):
    monkeypatch.setattr(launcher,'_data_root',lambda:tmp_path)
    monkeypatch.setattr(ui_zoom,'apply_zoom',lambda *a:pytest.fail('Default zoom must not initialize the engine'))
    assert launcher.NativeApi().restore_ui_zoom()=={'ok':True,'zoom_percent':100}


def test_dialog_marshals_to_gui_and_preserves_cancellation(monkeypatch):
    monkeypatch.setattr(gui_dialogs.sys,'platform','win32')
    monkeypatch.setitem(sys.modules,'System',SimpleNamespace(Action=lambda callback:callback))
    state={'gui':False};calls=[]
    def dispatch(callback):
        state['gui']=True
        try:callback()
        finally:state['gui']=False
    def dialog(kind,**opts):
        assert state['gui'];calls.append((kind,opts));return None
    window=SimpleNamespace(native=SimpleNamespace(InvokeRequired=True,BeginInvoke=dispatch,Invoke=lambda *a:pytest.fail('Synchronous Invoke')),create_file_dialog=dialog)
    assert gui_dialogs.file_dialog(window,'save',save_filename='example.maeprojz') is None
    assert calls==[('save',{'save_filename':'example.maeprojz'})]


def test_queued_dialog_times_out_and_cannot_open_late(monkeypatch):
    monkeypatch.setattr(gui_dialogs.sys,'platform','win32')
    monkeypatch.setitem(sys.modules,'System',SimpleNamespace(Action=lambda callback:callback))
    queued=[];window=SimpleNamespace(native=SimpleNamespace(InvokeRequired=True,BeginInvoke=queued.append),create_file_dialog=lambda *a,**k:pytest.fail('Late dialog'))
    with pytest.raises(RuntimeError,match='could not start'):gui_dialogs.file_dialog(window,'save',start_timeout=.001)
    queued[0]()


def test_project_picker_uses_gui_adapter_and_absolute_initial_directory(tmp_path,monkeypatch):
    monkeypatch.setattr(launcher,'_data_root',lambda:tmp_path)
    monkeypatch.setitem(sys.modules,'webview',SimpleNamespace(FileDialog=SimpleNamespace(SAVE='save')))
    seen=[]
    monkeypatch.setattr(gui_dialogs,'file_dialog',lambda w,k,**opts:seen.append(opts) or [str(tmp_path/'project.maeprojz')])
    api=launcher.NativeApi();api.window=object();result=api.choose_project_save_path('New project')
    assert result['ok'] and result['path'].endswith('.maeprojz')
    assert Path(seen[0]['directory']).is_absolute() and seen[0]['save_filename']=='New project.maeprojz'


def test_actual_native_create_path_cancel_and_reentry():
    setup=r'''const assert=require('assert/strict');let projectCreationPending=false,pendingNewProjectPath=null,current=null,currentUser={native_single_user:true},selectedTrackId=null;const button={disabled:false,isConnected:true};const elements={'#newProjectTitle':{value:'Example'},'#newProjectTarget':{value:'DAW'},'#newProjectSampleRate':{value:'48000'},'#createProjectButton':button};const $=id=>elements[id];let choices=[],apiCalls=[],bound=[],notices=[],open=[],release,block=false;const bridge={choose_project_save_path:async title=>{choices.push(title);if(block)await new Promise(r=>release=r);return {ok:!cancel,path:'/Example.maeprojz'}},bind_project_path:async(id,path)=>{bound.push([id,path]);return {ok:true}}};let cancel=true;
async function waitForNativeApi(){return bridge}async function prepareProjectLeave(){return true}function tr(en){return en}function toast(s){notices.push(s)}function appDisplayPreference(){return false}function closeUtilityModal(){}function rememberRecentProject(id){open.push(id)}function resetProjectUiForOpen(){}function resetSessionHistory(){}function render(){}async function refresh(){}function schedulePlaybackPrewarm(){}function focusProjectWorkspace(){}
async function api(url,opt){apiCalls.push([url,opt]);if(opt?.method==='POST')return {id:'new'};return {id:'new',tracks:[]}}
'''
    check=r'''(async()=>{await createProjectFromDialog();assert.equal(apiCalls.length,0);assert.equal(current,null);assert.equal(button.disabled,false);assert.equal(projectCreationPending,false);
cancel=false;block=true;const first=createProjectFromDialog();for(let i=0;i<3;i++)await new Promise(setImmediate);assert.equal(button.disabled,true);await createProjectFromDialog();assert.equal(choices.length,2);release();await first;assert.equal(apiCalls.filter(x=>x[1]?.method==='POST').length,1);assert.ok(apiCalls[0][0].includes('sample_rate=48000'));assert.deepEqual(bound,[['new','/Example.maeprojz']]);assert.deepEqual(open,['new']);assert.equal(current.id,'new');assert.equal(button.disabled,false);assert.equal(pendingNewProjectPath,null)})().catch(e=>{console.error(e);process.exitCode=1});'''
    subprocess.run(['node','-e',setup+'\n'+function('createProjectFromDialog')+'\n'+check],check=True)


def test_visible_modal_is_not_cancelled_by_start_timeout(monkeypatch):
    import threading
    monkeypatch.setattr(gui_dialogs.sys,'platform','win32')
    monkeypatch.setitem(sys.modules,'System',SimpleNamespace(Action=lambda callback:callback))
    shown=threading.Event();dismiss=threading.Event();results=[]
    def choose(*a,**k):shown.set();assert dismiss.wait(2);return ('chosen.maeprojz',)
    def dispatch(callback):threading.Thread(target=callback,daemon=True).start()
    window=SimpleNamespace(native=SimpleNamespace(InvokeRequired=True,BeginInvoke=dispatch),create_file_dialog=choose)
    worker=threading.Thread(target=lambda:results.append(gui_dialogs.file_dialog(window,'save',start_timeout=.01)),daemon=True)
    worker.start();assert shown.wait(1);assert worker.is_alive();dismiss.set();worker.join(2)
    assert results==[('chosen.maeprojz',)]


def test_zoom_timed_out_callback_cannot_change_engine_later(monkeypatch):
    queued=[]
    monkeypatch.setitem(sys.modules,'System',SimpleNamespace(Action=lambda callback:callback))
    native=SimpleNamespace(InvokeRequired=True,BeginInvoke=queued.append)
    window=SimpleNamespace(native=native)
    with pytest.raises(RuntimeError,match='timed out'):ui_zoom.apply_zoom(window,80,timeout=.001)
    native.webview=SimpleNamespace(ZoomFactor=1)
    queued[0]();assert native.webview.ZoomFactor==1


def test_shared_translation_avoids_repeated_work_and_preserves_language():
    script=r'''
const fs=require('fs'),vm=require('vm'),assert=require('assert');
let ready,observer,langWrites=0,walks=0,reads=0,lang;
const queue=[];
const html={get lang(){return lang},set lang(v){langWrites++;lang=v}};
const text={nodeType:3,nodeValue:'Save project',isConnected:true,parentElement:{closest(){return false}}};
const root={nodeType:1,isConnected:true,querySelectorAll(){return []},texts:[text]};text.parentNode=root;
const doc={readyState:'loading',documentElement:html,body:root,addEventListener(name,cb){ready=cb},createTreeWalker(node){walks++;let i=0;return {nextNode(){this.currentNode=(node.texts||[])[i++];return !!this.currentNode}}},querySelectorAll(){return []}};
doc.texts=[text];
const pairs={};Object.defineProperty(pairs,'Save project',{enumerable:true,get(){reads++;return 'Salva progetto'}});
const context={window:{MTA_TRANSLATIONS:pairs,MTA_LOCALE:{choice:'it'},dispatchEvent(){}},navigator:{languages:['en']},document:doc,NodeFilter:{SHOW_TEXT:4},CustomEvent:class{},queueMicrotask:cb=>queue.push(cb),MutationObserver:class{constructor(cb){observer=cb}observe(){}}};
vm.createContext(context);vm.runInContext(fs.readFileSync('app/static/localization.js','utf8'),context);ready();
assert.equal(text.nodeValue,'Salva progetto');assert.equal(langWrites,1);
const t=context.window.MtaLocale;const before=reads;
for(let n=0;n<2000;n++)assert.equal(t.translate('Save project'),'Salva progetto');assert.equal(reads,before);
const beforeWalks=walks;observer([{type:'childList',addedNodes:[root,text]}]);queue.shift()();assert.equal(walks,beforeWalks+1);assert.equal(langWrites,1);
t.setChoice('en');assert.equal(t.translate('Salva progetto'),'Save project');assert.equal(langWrites,2);
'''
    subprocess.run(['node','-e',script],check=True)
