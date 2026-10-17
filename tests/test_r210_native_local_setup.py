"""Native setup orchestration, frozen Python bridge and localized Arranger UX."""
import json
import subprocess
import sys
import threading
import time
from pathlib import Path
from types import SimpleNamespace
import pytest
from app import ace_step_desktop_manager as manager


@pytest.fixture
def local(tmp_path,monkeypatch):
    monkeypatch.setenv('MTA_ACE_STEP_DESKTOP_DIR',str(tmp_path/'ace'))
    monkeypatch.setenv('MTA_NATIVE_SINGLE_USER','true')
    for key in ('MTA_AI_WORKER_EXECUTABLE','MTA_AI_WORKER_ENABLED','MTA_ACE_STEP_URL','MTA_ACE_STEP_TOKEN','MTA_ACE_STEP_TRUSTED_HOST'):
        monkeypatch.delenv(key,raising=False)
    monkeypatch.setattr(manager,'_TASK',{'state':'idle'})
    monkeypatch.setattr(manager,'_PROCESS',None)
    monkeypatch.setattr(manager,'_READY',False)
    monkeypatch.setattr(manager,'_SETUP_ACTIVE',False)
    monkeypatch.setattr(manager,'_SETUP_EPOCH',0)
    return tmp_path


def wait_setup():
    for _ in range(200):
        if not manager._SETUP_ACTIVE:return
        time.sleep(.01)
    raise AssertionError('setup did not terminate')


def test_select_local_installs_starts_and_waits_for_http_readiness(local,monkeypatch):
    manager.configure_connection(mode='local')
    events=[];ready=threading.Event()
    def install():
        events.append('install');root=manager.home()/'source';root.mkdir(parents=True)
        (root/'pyproject.toml').write_text('test');(root/'.venv').mkdir()
        manager._TASK={'state':'installed'}
    def start(**kw):
        events.append('start');manager._PROCESS=SimpleNamespace(poll=lambda:None)
        manager._TASK={'state':'starting_server'}
        return manager.status()
    monkeypatch.setattr(manager,'_tool',lambda _:sys.executable)
    monkeypatch.setattr(manager,'_perform_install',install);monkeypatch.setattr(manager,'start_server',start)
    monkeypatch.setattr(manager,'_health_ready',lambda:ready.is_set())
    # Avoid a real one-second poll wait, while still exercising the state machine.
    original_sleep=time.sleep
    monkeypatch.setattr(manager.time,'sleep',lambda _:original_sleep(.005))
    manager.ensure_local(confirmed=True)
    for _ in range(100):
        if 'start' in events:break
        original_sleep(.005)
    assert events==['install','start'] and manager.status()['server_ready'] is False
    manager.ensure_local(confirmed=True);assert events==['install','start']
    ready.set();wait_setup()
    assert manager.status()['server_ready'] is True
    assert manager.status()['task']['state']=='ready'
    assert manager._previous_consent() is True


def test_missing_runtime_reports_failure_and_does_not_start_server(local,monkeypatch):
    manager.configure_connection(mode='local')
    monkeypatch.setattr(manager,'_tool',lambda _:None)
    manager.ensure_local(confirmed=True);wait_setup()
    assert manager.status()['task']['state']=='failed'
    assert manager.status()['server_ready'] is False
    assert manager._PROCESS is None


def test_native_adapter_uses_managed_python_and_not_frozen_gui_executable(local,monkeypatch):
    folder=manager.home()/'source'/'.venv'/'bin';folder.mkdir(parents=True)
    python=folder/'python';python.symlink_to(sys.executable)
    manager._activate_adapter()
    from app.ai_worker_protocol import configured_worker,worker_command
    worker=configured_worker();assert worker is not None
    monkeypatch.setattr(sys,'frozen',True,raising=False)
    argv=worker_command(worker)
    assert argv[0]==str(python)
    result=subprocess.run(argv+['--capabilities'],capture_output=True,text=True,timeout=10)
    assert result.returncode==0,result.stderr
    assert json.loads(result.stdout)['supports_audio_input'] is True
    assert all((manager.home()/'adapter'/name).is_file() for name in manager._ADAPTER_FILES)


def test_selecting_local_preserves_an_already_running_adapter(local,monkeypatch):
    manager._activate_adapter()
    monkeypatch.setattr(manager,'_PROCESS',SimpleNamespace(poll=lambda:None))
    manager.configure_connection(mode='local')
    from app.ai_worker_protocol import configured_worker
    assert configured_worker() is not None


def test_installer_watchdog_handles_silent_process(local):
    started=time.monotonic()
    with pytest.raises(subprocess.TimeoutExpired):
        manager._run_with_progress([sys.executable,'-c','import time;time.sleep(30)'],cwd=None,timeout=1,phase='dependencies')
    assert time.monotonic()-started<5


def test_no_install_without_selection_consent(local):
    with pytest.raises(ValueError):manager.ensure_local(confirmed=False)
    assert manager._PROCESS is None


def test_help_and_native_setup_markup_are_in_one_current_language():
    source=(Path(__file__).parents[1]/'app/static/app.js').read_text()
    section=source[source.index('async function openAiRemixPanel('):source.index('function aiArrangerTab(')]
    script=r'''const vm=require('vm'),assert=require('assert');let html='',language='it';
const ctx={current:{id:'p',tracks:[]},currentUser:{native_single_user:true},uiLanguage:'it',esc:String,
tr:(en,it)=>language==='it'?it:en,api:async()=>({presets:[],models:[]}),showUtilityModal:(title,body)=>html=body,aiArrangerTab(){},aiAceRefresh(){},aiArrangerWatchActive(){}};
vm.createContext(ctx);vm.runInContext(process.argv[1],ctx);
(async()=>{await ctx.openAiRemixPanel();assert.ok(html.includes('aiIntensityHelp'));assert.ok(html.includes('aiAceSummary'));assert.ok(html.includes('I modelli possono essere scaricati'));assert.ok(!html.includes('Local / Locale'));assert.ok(!html.includes('Input audio / Sorgente'));
language='en';ctx.uiLanguage='en';await ctx.openAiRemixPanel();assert.ok(html.includes('Choosing Local installs'));assert.ok(html.includes('Intensity'));assert.ok(!html.includes('Selezionando Locale'));assert.ok(html.includes('aria-expanded="false"'));
})().catch(e=>{console.error(e);process.exitCode=1});'''
    result=subprocess.run(['node','-e',script,section],capture_output=True,text=True,timeout=10)
    assert result.returncode==0,result.stderr


def test_ready_status_notification_follows_backend_readiness_even_without_dialog():
    source=(Path(__file__).parents[1]/'app/static/app.js').read_text()
    section=source[source.index('let aiAcePollTimer='):source.index('async function aiAceSaveConnection()')]
    script=r'''const vm=require('vm'),assert=require('assert');let ready=false,toasts=[],timer;
const ctx={currentUser:{native_single_user:true},document:{getElementById:()=>null},tr:(en,it)=>en,
api:async()=>({desktop:{task:{state:ready?'ready':'starting_server'},connection:{mode:'local'},server_running:true,server_ready:ready,installed:true}}),toast:text=>toasts.push(text),setInterval:f=>{timer=f;return 1},clearInterval(){}};
vm.createContext(ctx);vm.runInContext(process.argv[1],ctx);
(async()=>{await ctx.aiAceRefresh();assert.equal(toasts.length,0);ready=true;await timer();assert.equal(toasts.length,1);assert.match(toasts[0],/ready/);await ctx.aiAceRefresh();assert.equal(toasts.length,1)})().catch(e=>{console.error(e);process.exitCode=1});'''
    result=subprocess.run(['node','-e',script,section],capture_output=True,text=True,timeout=10)
    assert result.returncode==0,result.stderr


def test_mac_supervisor_does_not_depend_on_linux_proc_or_fabricate_tree_metering(local,monkeypatch):
    import wave
    from app import ai_worker_protocol as protocol,ai_metering_agent,audio_engine
    from app.models import Project,Track
    # Preserve the source checkout's interpreter in this isolated Unix test.
    monkeypatch.delenv('MTA_NATIVE_SINGLE_USER')
    worker=local/'worker.py'
    worker.write_text('import argparse,wave\np=argparse.ArgumentParser();p.add_argument("--request");p.add_argument("--output");a=p.parse_args()\nwith wave.open(a.output,"wb") as w:\n w.setnchannels(1);w.setsampwidth(2);w.setframerate(44100);w.writeframes(bytes(882))\n')
    worker.chmod(0o700)
    monkeypatch.setenv('MTA_AI_WORKER_ENABLED','true');monkeypatch.setenv('MTA_AI_WORKER_EXECUTABLE',str(worker))
    def render(project,resolve,path,**kw):
        with wave.open(str(path),'wb') as wav:
            wav.setnchannels(1);wav.setsampwidth(2);wav.setframerate(44100);wav.writeframes(bytes(882))
    monkeypatch.setattr(audio_engine,'render_mix',render)
    monkeypatch.setattr(sys,'platform','darwin')
    monkeypatch.setattr(ai_metering_agent,'_descendants',lambda _:pytest.fail('Linux /proc used on Mac'))
    audio,meta=protocol.run_worker_with_project_audio({'input_source':'master'},Project(id='p',title='Test',tracks=[Track(id='t',name='Source',filename='source.wav')]),lambda *a:None,timeout_seconds=5)
    assert audio.startswith(b'RIFF') and '_trusted_worker_usage' not in meta


@pytest.mark.parametrize('member',['../../escape','/absolute/file'])
def test_source_archive_rejects_unsafe_members(local,monkeypatch,member):
    import io,zipfile
    raw=io.BytesIO()
    with zipfile.ZipFile(raw,'w') as z:z.writestr(member,b'bad')
    class Response(io.BytesIO):
        headers={'Content-Length':str(len(raw.getvalue()))}
    monkeypatch.setattr(manager,'build_opener',lambda *a:SimpleNamespace(open=lambda *a,**k:Response(raw.getvalue())))
    manager.home().mkdir(parents=True)
    with pytest.raises(RuntimeError,match='UNSAFE'):manager._download_source(manager.home()/'source')
    assert not (manager.home()/'source').exists()
