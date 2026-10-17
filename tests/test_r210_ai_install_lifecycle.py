"""Full AI install coverage, committed results, safe close and notification ordering."""
import importlib.util
import io
from pathlib import Path
import subprocess
from types import SimpleNamespace
import wave

import pytest
from fastapi import HTTPException

ROOT = Path(__file__).parents[1]


def installer():
    spec = importlib.util.spec_from_file_location('all_ai_installer', ROOT / 'scripts/install_ai_engines.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_install_catalog_covers_every_builtin_and_rejects_missing_future_engine(monkeypatch):
    from app import ai_install_catalog as catalog, ai_worker_registry as registry
    assert set(catalog.validate_coverage()) == registry.WORKER_KINDS
    monkeypatch.setattr(registry, 'WORKER_KINDS', registry.WORKER_KINDS | {'future-engine'})
    with pytest.raises(ValueError, match='future-engine'):
        catalog.validate_coverage()


@pytest.mark.parametrize('device', ['cpu', 'rocm', 'cuda'])
def test_install_dry_run_is_complete_and_never_runs_subprocess(device, tmp_path, monkeypatch):
    module = installer()
    monkeypatch.setattr(module, 'run', lambda *a, **k: pytest.fail('dry run mutated the host'))
    plan = module.install(SimpleNamespace(device=device, dry_run=True))
    assert {'whisper', 'chords-ml', 'markers', 'demucs', 'backing-vocals', 'drumsep', 'sam-audio', 'singer-separation', 'ace-step'} <= plan['engines'].keys()
    assert plan['device'] == device and plan['gpu_billing_activated'] is False


def test_installer_commits_bindings_only_after_both_environments_pass(tmp_path, monkeypatch):
    module = installer()
    config = tmp_path / 'mta.env'
    original = 'SMTP_PASSWORD=keep\nMTA_ACE_STEP_URL=http://127.0.0.1:8001\n'
    config.write_text(original)
    monkeypatch.setattr(module, 'system_dependencies', lambda: None)
    calls = []
    def install_group(python, folder, device, group):
        calls.append(group)
        assert config.read_text() == original
        binary = folder / 'bin/python'
        binary.parent.mkdir(parents=True)
        binary.write_text('#!/bin/sh\nexit 0\n')
        binary.chmod(0o755)
        return binary
    monkeypatch.setattr(module, 'install_group', install_group)
    args = SimpleNamespace(device='cpu', dry_run=False, env_file=str(config), base=str(tmp_path / 'runtimes'), python='python3')
    module.install(args)
    result = config.read_text()
    assert calls == ['audio', 'sam']
    assert original.strip() in result
    for kind, group in module.ENGINE_GROUPS.items():
        if group != 'ace':
            assert 'MTA_AI_WORKER_' + kind.upper().replace('-', '_') + '_PYTHON=' in result
    assert config.stat().st_mode & 0o777 == 0o600
    # Second run verifies cached environments and does not reinstall packages.
    calls.clear()
    monkeypatch.setattr(module, 'verify', lambda binary, group, device: calls.append('verify:' + group))
    module.install(args)
    assert calls == ['verify:audio', 'verify:sam']


def test_failed_ai_install_preserves_live_configuration(tmp_path, monkeypatch):
    module = installer()
    config = tmp_path / 'mta.env';config.write_text('SMTP_PASSWORD=unchanged\n')
    monkeypatch.setattr(module, 'system_dependencies', lambda: None)
    def fail(*args):
        raise RuntimeError('dependency conflict')
    monkeypatch.setattr(module, 'install_group', fail)
    with pytest.raises(RuntimeError, match='dependency conflict'):
        module.install(SimpleNamespace(device='rocm', dry_run=False, env_file=str(config), base=str(tmp_path / 'runtime'), python='python3'))
    assert config.read_text() == 'SMTP_PASSWORD=unchanged\n'


def test_setup_path_installs_complete_ai_before_service_restart():
    wizard = (ROOT / 'scripts/install_mta_native_wizard.sh').read_text()
    assert wizard.index('"$ai_installer"') < wizard.index('if ! systemctl restart mta-server.service')
    assert '--env-file "$work"' in wizard
    for name in ('build_deb.sh', 'build_rpm.sh'):
        script = (ROOT / 'scripts/server_packages' / name).read_text()
        for filename in ('install_ai_engines.py', 'requirements-stems.txt', 'requirements-lyrics.txt', 'requirements-chords.txt', 'requirements-roformer-compat.txt'):
            assert filename in script


def test_committed_ai_wav_cannot_be_removed_by_stale_put(tmp_path, monkeypatch):
    from app import storage, main, ai_arranger_runtime as queue
    import time
    deadline = time.monotonic() + 5
    while storage._GC_ACTIVE and time.monotonic() < deadline:
        time.sleep(.02)
    assert not storage._GC_ACTIVE
    monkeypatch.setattr(storage, 'ROOT', tmp_path / 'projects')
    monkeypatch.setattr(storage, 'SHARED_MEDIA_ROOT', tmp_path / 'shared')
    monkeypatch.setattr(storage, 'SHARED_AUDIO_ROOT', tmp_path / 'shared/audio')
    monkeypatch.setattr(storage, 'SHARED_INDEX_PATH', tmp_path / 'shared/index.json')
    monkeypatch.setattr(queue, '_ROOT', tmp_path / 'queue')
    project = storage.create_project('AI publication race')
    stale = project.model_copy(deep=True)
    monkeypatch.setattr(main, '_project_for_actor', lambda request, pid: storage.load_project(pid))
    stream = io.BytesIO()
    with wave.open(stream, 'wb') as wav:
        wav.setnchannels(1);wav.setsampwidth(2);wav.setframerate(44100);wav.writeframes(bytes(882))
    audio = stream.getvalue()
    main._publish_durable_generated_audio('publish-race', project.id, audio,
        {'wav': {'frames': 441, 'sample_rate': 44100, 'channels': 1}, 'mode': 'arranger', 'input_source': 'master'})
    with pytest.raises(HTTPException) as caught:
        main.project_put(project.id, stale, object())
    assert caught.value.status_code == 409 and caught.value.detail == 'PROJECT_AI_RESULTS_CHANGED'
    reopened = storage.load_project(project.id)
    assert len(reopened.tracks) == 1 and reopened.ai_publication_token
    assert storage.audio_path(project.id, reopened.tracks[0].filename).read_bytes() == audio
    # A fresh snapshot can still explicitly delete a generated track.
    reopened.tracks.clear()
    main.project_put(project.id, reopened, object())
    assert not storage.load_project(project.id).tracks


def test_queued_annotation_save_rotates_publication_token(tmp_path, monkeypatch):
    from app import storage
    from app.ai_global_execution import current_job
    monkeypatch.setattr(storage, 'ROOT', tmp_path)
    project = storage.create_project('Annotations')
    token = current_job.set('marker-job')
    try:
        storage.save_project(project)
    finally:
        current_job.reset(token)
    assert project.ai_publication_token and storage.load_project(project.id).ai_publication_token == project.ai_publication_token


def node(script, section):
    result = subprocess.run(['node', '-e', script, section], capture_output=True, text=True, timeout=15)
    assert result.returncode == 0, result.stderr


def test_js_close_save_discard_cancel_and_save_failure():
    source = (ROOT / 'app/static/app.js').read_text()
    section = source[source.index('async function prepareProjectLeave(){'):source.index('window.mtaRequestNativeClose=')]
    node(r'''
const vm=require('vm'),assert=require('assert');let answer='cancel',saves=0,asks=0;
const ctx={current:{id:'p'},projectDirty:true,autosaveBusy:false,autosaveEnabled:false,projectLeavePending:null,
autosaveTimer:1,clearTimeout(){},hasUnsavedProjectChanges:()=>ctx.projectDirty,askProjectSave:async()=>{asks++;return answer},save:async()=>{saves++;ctx.projectDirty=false}};
vm.createContext(ctx);vm.runInContext(process.argv[1],ctx);
(async()=>{
assert.equal(await ctx.prepareProjectLeave(),false);assert.equal(saves,0);
answer='discard';assert.equal(await ctx.prepareProjectLeave(),true);assert.equal(saves,0);
answer='save';assert.equal(await ctx.prepareProjectLeave(),true);assert.equal(saves,1);
ctx.projectDirty=true;ctx.autosaveEnabled=true;const before=asks;
assert.equal(await ctx.prepareProjectLeave(),true);assert.equal(asks,before);assert.equal(saves,2);
ctx.projectDirty=true;ctx.save=async()=>{throw Error('disk full')};
assert.equal(await ctx.prepareProjectLeave(),false);assert.equal(ctx.current.id,'p');assert.equal(ctx.projectDirty,true);
})().catch(e=>{console.error(e);process.exitCode=1});
''', section)


def test_js_merge_preserves_local_edits_new_tracks_and_explicit_deletion():
    source = (ROOT / 'app/static/app.js').read_text()
    section = source[source.index('function mergeAiProjectResults('):source.index('let aiReconcilePending=')]
    node(r'''
const vm=require('vm'),assert=require('assert');const ctx={tr:x=>x};vm.createContext(ctx);vm.runInContext(process.argv[1],ctx);
const base={id:'p',tracks:[{id:'old',name:'old'}],clip_library:[],lyrics:[],chords:[],markers:[]};
const local={...structuredClone(base),title:'unsaved title',tracks:[]};
const remote={...structuredClone(base),tracks:[...base.tracks,{id:'ai',filename:'ai.wav'}],markers:[{time_ms:10,label:'AI'}],ai_publication_token:'new'};
const merged=ctx.mergeAiProjectResults(local,remote,base);
assert.equal(merged.title,'unsaved title');assert.equal(merged.tracks.length,1);assert.equal(merged.tracks[0].id,'ai');assert.equal(merged.markers[0].label,'AI');assert.equal(merged.ai_publication_token,'new');
local.markers=[{time_ms:20,label:'manual'}];assert.throws(()=>ctx.mergeAiProjectResults(local,remote,base),/conflict/);
assert.equal(local.markers[0].label,'manual');assert.equal(remote.tracks.length,2);
''', section)


def test_native_os_close_waits_for_editor_guard(monkeypatch):
    from native.mta_audio_editor_native import NativeApi
    import native.mta_audio_editor_native as native_module
    class ImmediateThread:
        def __init__(self, target, **kwargs):self.target=target
        def start(self):self.target()
    monkeypatch.setattr(native_module.threading, 'Thread', ImmediateThread)
    calls = []
    api = NativeApi.__new__(NativeApi)
    api.window = SimpleNamespace(evaluate_js=lambda script: calls.append(script) or True, destroy=lambda: calls.append('destroy'))
    assert api._guard_project_close() is False
    assert any('mtaRequestNativeClose();' in call for call in calls)
    assert 'destroy' not in calls
    api.confirm_project_close()
    assert calls[-1] == 'destroy' and api._guard_project_close() is True


def test_js_stale_autosave_reconciles_and_retries_without_deadlock():
    source = (ROOT / 'app/static/app.js').read_text()
    merge = source[source.index('function mergeAiProjectResults('):source.index('function askProjectSave(')]
    persist = source[source.index('async function persistCurrentProject('):source.index('async function restoreHistorySnapshot(')]
    node(r'''
const vm=require('vm'),assert=require('assert');let writes=0;
const base={id:'p',title:'before',tracks:[{id:'original'}],clip_library:[],lyrics:[],markers:[],chords:[],ai_publication_token:''};
const remote={...structuredClone(base),tracks:[...base.tracks,{id:'ai'}],ai_publication_token:'published'};
const ctx={current:{...structuredClone(base),title:'local edit'},persistedProjectSnapshot:base,projectDirty:true,autosaveBusy:true,projectMutationSerial:1,
tr:x=>x,collect(){},render(){},hasUnsavedProjectChanges:()=>ctx.projectDirty,syncNativeProjectFile:async()=>{},projectSnapshot(){return structuredClone(ctx.current)},$:()=>({}),
api:async(url,options)=>{if(options?.method==='PUT'){writes++;if(writes===1)throw Error('PROJECT_AI_RESULTS_CHANGED');const saved=JSON.parse(options.body);assert.equal(saved.tracks.length,2);assert.equal(saved.title,'local edit');return saved;}return structuredClone(remote)}};
vm.createContext(ctx);vm.runInContext(process.argv[1],ctx);
(async()=>{await ctx.persistCurrentProject();assert.equal(writes,2);assert.equal(ctx.projectDirty,false);assert.equal(ctx.current.tracks[1].id,'ai');})().catch(e=>{console.error(e);process.exitCode=1});
''', merge + '\n' + persist)


@pytest.mark.parametrize('visible', [True, False])
def test_job_notice_waits_for_project_and_only_appears_after_origin_closed(visible):
    script = r'''
const vm=require('vm'),assert=require('assert');
class Element{constructor(){this.dataset={};this.children=[];this.classList={toggle(){}};this.hidden=false;this.value='all';}set innerHTML(s){this.html=s}append(...items){this.children.push(...items);for(const i of items)i.parent=this}setAttribute(){}addEventListener(){}querySelectorAll(){return []}focus(){}remove(){if(this.parent)this.parent.children=this.parent.children.filter(c=>c!==this)}}
const nodes={},root=new Element();root.querySelector=selector=>nodes[selector.slice(1)]||=(new Element());
const document={readyState:'complete',getElementById:()=>null,createElement:tag=>tag==='section'?root:new Element(),body:new Element()};
const callbacks={};let tick,completed=false,release,prepared=false,acks=0;
const job={job_id:'new',project_id:'p',operation:'arranger',state:'running',created_at:1};
const ctx={document,URLSearchParams,console,Date,Set,Map,Number,String,Error,JSON,location:{},localStorage:{getItem(){},setItem(){}},setTimeout:f=>{tick=f;return 1},clearTimeout(){},CustomEvent:class{constructor(type,init){this.type=type;this.detail=init.detail}},fetch:async(url,options)=>{if(options.method==='POST'){assert.ok(prepared,'ack before reconciliation');acks++;return {ok:true,json:async()=>({ok:true})}}const row={...job,state:completed?'completed':'running'};return {ok:true,json:async()=>({actor_id:1,jobs:[row],active_count:completed?0:1,total:1,notifications:completed?[row]:[]})}}};
ctx.window={addEventListener:(type,fn)=>(callbacks[type]||=[]).push(fn),dispatchEvent(){},mtaPrepareAiTerminal:async()=>{await new Promise(resolve=>release=resolve);prepared=true}};
vm.createContext(ctx);vm.runInContext(process.argv[1],ctx);
const settle=()=>new Promise(resolve=>setImmediate(resolve));
(async()=>{await settle();const visible=process.argv[2]==='true';const origin={isConnected:true,closest:()=>visible?null:{}};
for(const cb of callbacks['mta:ai-job-accepted'])cb({detail:{...job,origin}});
await settle();completed=true;const promise=tick();await settle();
assert.equal((nodes['aj-notices']?.children.length||0),0);assert.equal(acks,0);release();await promise;
assert.equal(acks,1);assert.equal((nodes['aj-notices']?.children.length||0),visible?0:1);
})().catch(e=>{console.error(e);process.exitCode=1});
'''
    result = subprocess.run(['node', '-e', script, (ROOT / 'app/static/ai_jobs.js').read_text(), str(visible).lower()], capture_output=True, text=True, timeout=15)
    assert result.returncode == 0, result.stderr


def test_unsaved_snapshot_changes_are_detected_without_dirty_flag():
    source = (ROOT / 'app/static/app.js').read_text()
    section = source[source.index('function hasUnsavedProjectChanges(){'):source.index('async function prepareProjectLeave(){')]
    node(r'''
const vm=require('vm'),assert=require('assert');const ctx={current:{id:'p',title:'saved'},persistedProjectSnapshot:{id:'p',title:'saved'},projectDirty:false};vm.createContext(ctx);vm.runInContext(process.argv[1],ctx);
assert.equal(ctx.hasUnsavedProjectChanges(),false);ctx.current.title='not saved';assert.equal(ctx.hasUnsavedProjectChanges(),true);ctx.current=null;assert.equal(ctx.hasUnsavedProjectChanges(),false);
''', section)


def test_native_bound_file_sync_failure_blocks_close_and_closed_job_syncs():
    source = (ROOT / 'app/static/app.js').read_text()
    sync = source[source.index('async function syncNativeProjectFile('):source.index('async function flushAutosave(')]
    node(r'''
const vm=require('vm'),assert=require('assert');let synced=[];const ctx={current:{id:'p'},currentUser:{native_single_user:true},projectDirty:false,tr:x=>x,console,
window:{pywebview:{api:{sync_project:async pid=>{synced.push(pid);throw Error('disk full')}}}}};vm.createContext(ctx);vm.runInContext(process.argv[1],ctx);
(async()=>{await assert.rejects(()=>ctx.syncNativeProjectFile('p',true),/disk full/);assert.equal(ctx.projectDirty,true);
ctx.current=null;ctx.window.pywebview.api.sync_project=async pid=>{synced.push(pid);return {ok:true,bound:true}};
await ctx.syncNativeProjectFile('closed-project',true);assert.equal(synced.at(-1),'closed-project');
ctx.window.pywebview.api.sync_project=async()=>({ok:false,bound:false});await ctx.syncNativeProjectFile('unbound',true);
})().catch(e=>{console.error(e);process.exitCode=1});
''', sync)


def test_default_drumsep_uses_verified_native_checkpoint_download(tmp_path, monkeypatch):
    from app import main, ai_unified_adapter as adapter, drumsep_onnx_worker
    source = tmp_path / 'source.wav';source.write_bytes(b'source')
    model = tmp_path / 'drumsep.onnx'
    calls = []
    monkeypatch.delenv('MTA_AI_DRUMSEP_MODEL', raising=False)
    monkeypatch.setattr(main, '_DRUMSEP_PATH', model)
    def download():
        calls.append('verified-download')
        model.write_bytes(b'checkpoint')
    def infer(source, chosen, folder):
        assert chosen == model and chosen.read_bytes() == b'checkpoint'
        calls.append('infer')
        result = folder / 'kick.wav';result.write_bytes(b'result')
        return [result]
    monkeypatch.setattr(main, '_download_drumsep_model', download)
    monkeypatch.setattr(drumsep_onnx_worker, 'infer', infer)
    monkeypatch.setattr(adapter, '_artifacts', lambda *args: None)
    adapter.infer({'kind': 'drumsep', 'source_audio': str(source)}, tmp_path / 'output.wav')
    assert calls == ['verified-download', 'infer']


@pytest.mark.parametrize('kind,model_id', [('whisper', 'tiny'), ('chords-ml', 'madmom-deep-chroma-crf')])
def test_server_model_download_uses_installed_ai_interpreter(tmp_path, monkeypatch, kind, model_id):
    from app import ai_models
    python = tmp_path / 'python';python.write_text('#!/bin/sh\nexit 0\n');python.chmod(0o755)
    monkeypatch.setenv('MTA_AI_UNIFIED_WORKERS_ENABLED', 'true')
    monkeypatch.setenv('MTA_AI_WORKER_' + kind.upper().replace('-', '_') + '_PYTHON', str(python))
    calls = []
    def download(chosen, selected, model):
        calls.append((chosen, selected, model))
        return {'id': model, 'installed': True}
    monkeypatch.setattr(ai_models, '_isolated_model_download', download)
    call = ai_models.download_lyrics_model if kind == 'whisper' else ai_models.download_chord_model
    assert call(model_id, native=False)['installed'] is True
    assert calls == [(str(python), kind, model_id)]
    with pytest.raises(ValueError):
        call('../unsafe', native=False)
    assert len(calls) == 1


def test_isolated_model_worker_does_not_recursively_spawn_itself(monkeypatch):
    import sys
    from app import ai_models
    monkeypatch.setenv('MTA_AI_UNIFIED_WORKERS_ENABLED', 'true')
    monkeypatch.setenv('MTA_AI_WORKER_WHISPER_PYTHON', sys.executable)
    assert ai_models._isolated_model_python('whisper') is None


def test_server_lyrics_catalog_and_delete_see_isolated_checkpoint(tmp_path, monkeypatch):
    from app import ai_models
    python = tmp_path / 'python';python.write_text('#!/bin/sh\nexit 0\n');python.chmod(0o755)
    monkeypatch.setenv('MTA_AI_UNIFIED_WORKERS_ENABLED', 'true')
    monkeypatch.setenv('MTA_AI_WORKER_WHISPER_PYTHON', str(python))
    monkeypatch.setenv('MTA_LYRICS_MODEL_DIR', str(tmp_path / 'models'))
    folder = tmp_path / 'models';folder.mkdir()
    model = folder / 'large-v3-turbo.pt';model.write_bytes(b'checkpoint')
    catalog = ai_models.lyrics_catalog(native=False)
    assert next(item for item in catalog['models'] if item['id'] == 'turbo')['installed'] is True
    assert ai_models.delete_lyrics_model('turbo', native=False)['removed'] is True
    assert not model.exists()


def test_native_closing_callback_returns_before_webview_javascript(monkeypatch):
    import native.mta_audio_editor_native as module
    queued = [];calls = []
    class DeferredThread:
        def __init__(self, target, **kwargs):self.target=target
        def start(self):queued.append(self.target)
    monkeypatch.setattr(module.threading, 'Thread', DeferredThread)
    api = module.NativeApi.__new__(module.NativeApi)
    api.window = SimpleNamespace(evaluate_js=lambda code: calls.append(code) or False, destroy=lambda: calls.append('destroy'))
    assert api._guard_project_close() is False
    assert calls == [] and len(queued) == 1
    assert api._guard_project_close() is False and len(queued) == 1
    queued[0]()
    assert calls[-1] == 'destroy' and api._guard_project_close() is True
