"""Independent track copies, per-tab refresh restoration and honest mount evidence."""
from pathlib import Path
import subprocess
import wave
import pytest
from app import main, storage
from app.models import Track, Clip, InsertPlugin
from app import ai_proxmox_gpu_agent_client as agent
from scripts.check_mta_gpu_agent_mount import classify

@pytest.fixture
def project(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, 'ROOT', tmp_path)
    p=storage.create_project('Test',target='DAW')
    source=storage.audio_path(p.id,'source.wav')
    with wave.open(str(source),'wb') as f:
        f.setnchannels(1);f.setsampwidth(2);f.setframerate(44100);f.writeframes(b'\0\0'*441)
    p.tracks=[Track(id='original',name='Orchestra',filename='source.wav',mta_slot=1,volume_db=-3,pan=.2,
        clips=[Clip(id='clip1',source_end_ms=10,timeline_start_ms=123)],
        inserts=[InsertPlugin(id='insert1',plugin='eq',params={'gain':2})])]
    storage.save_project(p)
    monkeypatch.setattr(main,'_project_for_actor',lambda req,pid: storage.load_project(pid))
    return p


def test_duplicate_has_independent_ids_and_audio(project):
    result=main.duplicate_track(project.id,'original',None)
    saved=storage.load_project(project.id)
    original,copy=saved.tracks
    assert copy.id==result['track_id'] and copy.id!=original.id
    assert copy.filename!=original.filename
    assert storage.audio_path(project.id,copy.filename).read_bytes()==storage.audio_path(project.id,original.filename).read_bytes()
    assert copy.clips[0].id!=original.clips[0].id
    assert copy.clips[0].timeline_start_ms==123
    assert copy.inserts[0].id!=original.inserts[0].id
    assert copy.inserts[0].params==original.inserts[0].params
    assert copy.mta_slot is None and original.mta_slot==1
    assert copy.volume_db==-3 and copy.pan==.2


@pytest.mark.parametrize('committed',[False,True])
def test_duplicate_failed_save_preserves_only_published_audio(project,monkeypatch,committed):
    save=main.save_project
    def failing(p):
        if committed: save(p)
        raise OSError('simulated storage failure')
    monkeypatch.setattr(main,'save_project',failing)
    with pytest.raises(OSError): main.duplicate_track(project.id,'original',None)
    saved=storage.load_project(project.id)
    assert len(saved.tracks)==(2 if committed else 1)
    assert all(storage.audio_path(project.id,t.filename).is_file() for t in saved.tracks)
    if not committed:
        assert not list(storage.pdir(project.id).joinpath('audio').glob('duplicate-*'))


def test_project_resume_uses_account_and_tab_storage_and_actual_init():
    source=(Path(__file__).resolve().parents[1]/'app/static/app.js').read_text()
    helpers=source[source.index('function activeWebProjectKey'):source.index('function recentProjectIds')]
    init=source[source.index('async function init(){'):source.index('\n',source.index('async function init(){'))]
    js='''const vm=require('vm'),assert=require('assert'),store=new Map();
const ctx={URLSearchParams,location:{search:''},currentUser:null,current:null,pluginInfo:null,autosaveEnabled:true,
sessionStorage:{getItem:k=>store.get(k)||null,setItem:(k,v)=>store.set(k,v),removeItem:k=>store.delete(k)},
MtaPreferences:{getItem:()=>null},restoreSidebarPanels(){},isMobileClient:()=>false,$:()=>null,
api:async url=>url==='/api/session'?{id:1,role:'user',native_single_user:false}:{},
refresh:async()=>{},openP:async id=>{ctx.current={id}},document:{body:{classList:{add(){}}}}};
vm.createContext(ctx);vm.runInContext(process.argv[1],ctx);vm.runInContext(process.argv[2],ctx);
(async()=>{
 ctx.currentUser={id:1};ctx.current={id:'project-1'};vm.runInContext('rememberActiveWebProject()',ctx);
 ctx.current=null;await vm.runInContext('init()',ctx);assert.equal(ctx.current.id,'project-1');
 ctx.location.search='?ai_project=project-2';ctx.current=null;await vm.runInContext('init()',ctx);assert.equal(ctx.current.id,'project-2');ctx.location.search='';
 ctx.currentUser={id:2};ctx.current=null;await vm.runInContext('restoreActiveWebProject()',ctx);assert.equal(ctx.current,null);
 ctx.currentUser={id:1};vm.runInContext('forgetActiveWebProject()',ctx);await vm.runInContext('restoreActiveWebProject()',ctx);assert.equal(ctx.current,null);
 ctx.currentUser={id:1,native_single_user:true};ctx.current={id:'native'};vm.runInContext('rememberActiveWebProject()',ctx);assert.equal(store.size,0);
})().catch(e=>{console.error(e);process.exitCode=1});'''
    run=subprocess.run(['node','-e',js,helpers,init],capture_output=True,text=True,timeout=10)
    assert run.returncode==0,run.stderr


def test_absent_socket_does_not_prove_absent_mount(monkeypatch):
    monkeypatch.delenv('MTA_AI_GPU_HOST_AGENT_SOCKET',raising=False)
    monkeypatch.setattr(agent.os.path,'exists',lambda p:False)
    monkeypatch.setattr(agent,'socket_visibility',lambda:{'mount_present':True,'directory_present':True,'access_denied':False})
    assert agent.snapshot()['reason']=='agent-socket-missing-in-mount'
    host={'directory':[10,20],'socket':True}
    assert classify(host,{'directory':[10,21],'socket':False})=='different-directory-or-stale-bind-mount'
    assert classify(host,dict(host))=='same-live-directory-and-socket-visible'


def test_agent_preserves_runtime_directory_across_upgrades():
    root=Path(__file__).resolve().parents[1]
    assert 'RuntimeDirectoryPreserve=yes' in (root/'packaging/proxmox-gpu-agent/build_deb.sh').read_text()
    assert 'RuntimeDirectoryPreserve=yes' in (root/'scripts/install_mta_proxmox_gpu_agent.sh').read_text()


def test_windows_journal_skips_only_posix_directory_open(tmp_path,monkeypatch):
    import os
    import json
    from types import SimpleNamespace
    from app import ai_upload_transaction, ai_media_identity
    fake=SimpleNamespace(**vars(os));fake.name='nt'
    fake.open=lambda *a,**k: pytest.fail('POSIX directory open on Windows')
    monkeypatch.setattr(ai_upload_transaction,'os',fake)
    ai_upload_transaction._sync_dir(tmp_path)
    monkeypatch.setattr(ai_media_identity,'os',fake)
    folder=tmp_path/'audio';folder.mkdir();media=folder/'copy.wav';media.write_bytes(b'audio')
    journal=tmp_path/'pending.json';journal.write_text(json.dumps({'identities':{}}))
    ai_media_identity.record(journal,media)
    assert 'audio/copy.wav' in json.loads(journal.read_text())['identities']


def test_duplicate_client_saves_before_request_and_selects_copy():
    text=(Path(__file__).resolve().parents[1]/'app/static/app.js').read_text()
    source=text[text.index('async function duplicateTrack(id){'):text.index('function openTrackContextMenuAt')]
    script='''const vm=require('vm'),assert=require('assert');let saved=false;
const ctx={current:{id:'project1'},selectedTrackId:null,selectedTrackIdSet:new Set(),
save:async()=>{saved=true},api:async(url,opt)=>{assert(saved);assert.equal(opt.method,'POST');assert(url.endsWith('/tracks/source/duplicate'));return {project:{id:'project1'},track_id:'copy'}},render(){},toast(){}};
vm.createContext(ctx);vm.runInContext(process.argv[1],ctx);
(async()=>{await vm.runInContext("duplicateTrack('source')",ctx);assert.equal(ctx.selectedTrackId,'copy');assert(ctx.selectedTrackIdSet.has('copy'))})().catch(e=>{console.error(e);process.exitCode=1});'''
    result=subprocess.run(['node','-e',script,source],capture_output=True,text=True,timeout=10)
    assert result.returncode==0,result.stderr
