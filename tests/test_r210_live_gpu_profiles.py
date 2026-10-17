import json
from pathlib import Path
from types import SimpleNamespace
import threading

import pytest
from app.ace_gpu_profiler import TaskProfiler, parse_report


def runtime(hooks, profiles, *, device=0):
    class Profile:
        def start(self):
            profiles.append('start')
        def stop(self):
            profiles.append('stop')
        def export_chrome_trace(self, name):
            Path(name).write_text(json.dumps({'traceEvents': [
                {'ph': 'X', 'cat': 'kernel', 'ts': 0, 'dur': 100000, 'args': {'device': device}}]}))
    def register(hook):
        hooks.append(hook)
        return SimpleNamespace(remove=lambda: hooks.remove(hook))
    return SimpleNamespace(version=SimpleNamespace(hip='7'),
        cuda=SimpleNamespace(is_available=lambda: True, synchronize=lambda: None),
        nn=SimpleNamespace(modules=SimpleNamespace(module=SimpleNamespace(register_module_forward_pre_hook=register))),
        profiler=SimpleNamespace(ProfilerActivity=SimpleNamespace(CUDA=1),
                                 supported_activities=lambda: {1}, profile=lambda **kwargs: Profile()))


def test_live_windows_are_cumulative_and_removed_after_generation():
    hooks, profiles, seen = [], [], []
    clock = [0]
    collector = TaskProfiler(lambda: runtime(hooks, profiles), clock=lambda: clock[0])
    def generate(*, job_id):
        for stamp in (6, 12):
            clock[0] = stamp
            hooks[0](None, None)
            report = collector.get(job_id)
            seen.append(parse_report(report, job_id)['gpu_seconds_estimated'])
            assert report['status'] == 'profiling'
            assert report['billing_eligible'] is False
        clock[0] = 13
        return b'audio'
    assert collector.wrap(generate)(job_id='task') == b'audio'
    assert seen == [.1, .2]
    report = collector.get('task')
    assert report['gpu_active_seconds'] == .3
    assert report['status'] == 'profiled_kernels_diagnostic'
    assert hooks == [] and profiles == ['start', 'stop'] * 3
    assert 'gpu_seconds' not in parse_report(report, 'task')


def test_other_thread_cannot_stop_inference_capture():
    hooks, profiles = [], []
    clock = [0]
    collector = TaskProfiler(lambda: runtime(hooks, profiles), clock=lambda: clock[0])
    def generate(*, job_id):
        clock[0] = 6
        thread = threading.Thread(target=lambda: hooks[0](None, None))
        thread.start(); thread.join()
        assert profiles == ['start']
    collector.wrap(generate)(job_id='task')
    assert profiles == ['start', 'stop'] and not hooks


def test_checkpoint_failure_does_not_retry_or_break_audio():
    hooks, profiles = [], []
    clock = [0]
    torch = runtime(hooks, profiles)
    collector = TaskProfiler(lambda: torch, clock=lambda: clock[0])
    def generate(*, job_id):
        clock[0] = 6
        torch.cuda.synchronize = lambda: (_ for _ in ()).throw(RuntimeError('unsupported'))
        hooks[0](None, None)
        return 'audio once'
    assert collector.wrap(generate)(job_id='task') == 'audio once'
    assert profiles == ['start', 'stop'] and not hooks
    assert collector.get('task')['status'] == 'profiler_failed'


@pytest.mark.parametrize('field,value', [('gpu_active_seconds', float('nan')), ('wall_seconds', .01),
                                        ('device_id', -1), ('kernel_count', 0)])
def test_partial_report_has_same_evidence_gates_as_final(field, value):
    report = dict(task_id='task', source='ace-torch-profiler', billing_eligible=False,
                  status='profiling', gpu_active_seconds=.2, wall_seconds=1, kernel_count=2, device_id=0)
    report[field] = value
    with pytest.raises(ValueError):
        parse_report(report, 'task')


def test_general_worker_sequential_reports_accumulate_without_billing(tmp_path, monkeypatch):
    from app import ai_torch_diagnostics as diagnostics
    monkeypatch.setenv('MTA_AI_TORCH_PROFILER', 'true')
    hooks, profiles = [], []
    torch = runtime(hooks, profiles)
    monkeypatch.setattr(TaskProfiler, '_torch', staticmethod(lambda: torch))
    # A real duration long enough for the fake 100ms event, without blocking.
    ticks = iter([0, 0, 1, 1] * 2)
    original = diagnostics.TaskProfiler
    monkeypatch.setattr(diagnostics, 'TaskProfiler', lambda **kw: original(clock=lambda: next(ticks), **kw))
    for _ in range(2):
        assert diagnostics.profile_call(tmp_path, 'task', lambda: b'audio') == b'audio'
    result = diagnostics.read_report(tmp_path, 'task')
    assert result['gpu_seconds_estimated'] == .2
    assert result['gpu_metrics_source'] == 'torch-profiler'
    assert 'gpu_seconds' not in result
    assert diagnostics.read_report(tmp_path, 'other-task') == {}
    assert sorted(p.name for p in tmp_path.iterdir()) == ['gpu-profile.json']


def test_adapter_reports_partial_profiler_not_idle_host(monkeypatch):
    from app import ace_step_http_worker as worker
    monkeypatch.setattr(worker, '_profile_result', lambda *args:
        {'gpu_seconds_estimated': .2, 'gpu_metrics_status': 'profiling', 'gpu_metrics_source': 'ace-torch-profiler'})
    result = worker._task_telemetry(SimpleNamespace(sample=lambda:
        {'cpu_seconds_estimated': 10, 'gpu_metrics_status': 'zero_counter_unverified'}), 'base', 'task')
    assert result['gpu_seconds_estimated'] == .2
    assert result['gpu_metrics_source'] == 'ace-torch-profiler'
    assert result['cpu_seconds_estimated'] == 10


def test_diagnostic_endpoint_requires_administrator(monkeypatch):
    from app import ai_billing_routes as routes
    from fastapi import HTTPException
    def deny(request):
        raise HTTPException(403)
    monkeypatch.setattr(routes, 'require_admin', deny)
    with pytest.raises(HTTPException) as exc:
        routes.gpu_profiler_reports(None)
    assert exc.value.status_code == 403


def test_diagnostic_storage_does_not_update_billing(tmp_path, monkeypatch):
    from app import ai_torch_diagnostics as diagnostics
    from app.auth import init_auth_db, db
    monkeypatch.setenv('MTA_DATA_DIR', str(tmp_path))
    init_auth_db()
    diagnostics.store_report('task', {'gpu_seconds_estimated': .2, 'gpu_metrics_status': 'profiling'})
    assert diagnostics.recent_reports()[0]['billing_eligible'] is False
    with db() as con:
        assert con.execute("SELECT 1 FROM sqlite_master WHERE name='ai_compute_jobs'").fetchone() is None


def test_demucs_and_sam_commands_profile_actual_child(monkeypatch, tmp_path):
    from app.ai_unified_adapter import _backend_command
    monkeypatch.setenv('MTA_AI_TORCH_PROFILER', 'true')
    for backend in ('demucs', 'sam-audio'):
        command = _backend_command({'gpu_profile_task_id': 'task'}, tmp_path, backend, ['--model', 'm'])
        assert command[1].endswith('ai_profiled_backend.py')
        assert backend in command and 'task' in command
        assert command[-3:] == ['--', '--model', 'm']


def test_hook_registration_failure_keeps_final_capture():
    hooks, profiles = [], []
    torch = runtime(hooks, profiles)
    torch.nn.modules.module.register_module_forward_pre_hook = lambda callback: (_ for _ in ()).throw(TypeError())
    ticks = iter([0, 0, 1, 1])
    collector = TaskProfiler(lambda: torch, clock=lambda: next(ticks))
    assert collector.wrap(lambda *, job_id: 'audio')(job_id='task') == 'audio'
    assert profiles == ['start', 'stop']


def test_compiler_capture_skips_live_control_but_retains_final_result():
    hooks, profiles = [], []
    torch = runtime(hooks, profiles)
    torch.compiler = SimpleNamespace(is_compiling=lambda: True)
    clock = [0]
    collector = TaskProfiler(lambda: torch, clock=lambda: clock[0])
    def generate(*, job_id):
        clock[0] = 6
        hooks[0](None, None)
        assert profiles == ['start']
        return 'audio'
    assert collector.wrap(generate)(job_id='task') == 'audio'
    assert profiles == ['start', 'stop'] and not hooks


def test_actual_worker_diagnostic_identity_and_gpu_billing_gate(tmp_path, monkeypatch):
    from app import ai_metering_agent, ai_torch_diagnostics
    from app.auth import init_auth_db, db
    monkeypatch.setenv('MTA_DATA_DIR', str(tmp_path / 'data'))
    monkeypatch.setenv('MTA_AI_WORKER_ENABLED', 'true')
    monkeypatch.setenv('MTA_AI_TORCH_PROFILER', 'true')
    monkeypatch.delenv('MTA_AI_CGROUP_PARENT', raising=False)
    init_auth_db()
    with db() as con:
        con.execute("INSERT INTO users(username,email,password_hash,active,role,created_at,updated_at) VALUES('gpu_worker','gpu@example.org','fake',1,'user',1,1)")
        uid = con.execute("SELECT id FROM users WHERE username='gpu_worker'").fetchone()[0]
    worker = tmp_path / 'worker.py'
    worker.write_text('''import argparse,json,pathlib,wave
p=argparse.ArgumentParser();p.add_argument('--request');p.add_argument('--output');a=p.parse_args()
request=json.loads(pathlib.Path(a.request).read_text())
assert request['gpu_profile_task_id'] != 'forged'
with wave.open(a.output,'wb') as f:
 f.setnchannels(1);f.setsampwidth(2);f.setframerate(44100);f.writeframes(bytes(512))
report={'task_id':request['gpu_profile_task_id'],'source':'torch-profiler','billing_eligible':False,
 'status':'profiled_kernels_diagnostic','gpu_active_seconds':.2,'wall_seconds':1,'kernel_count':2,'device_id':0}
(pathlib.Path(a.output).parent/'gpu-profile.json').write_text(json.dumps(report))
''')
    worker.chmod(0o700)
    monkeypatch.setenv('MTA_AI_WORKER_WHISPER_EXECUTABLE', str(worker))
    def cancel_check():
        with db() as con:
            if con.execute("SELECT 1 FROM sqlite_master WHERE name='ai_compute_jobs'").fetchone():
                row=con.execute("SELECT status FROM ai_compute_jobs WHERE kind='whisper'").fetchone()
                assert row is None or row[0] == 'running'
        return False
    audio, meta = ai_metering_agent.execute_registered_worker(uid, 'whisper',
        {'kind': 'whisper', 'gpu_profile_task_id': 'forged'}, cancel_check=cancel_check)
    assert audio[:4] == b'RIFF'
    assert meta['gpu_diagnostics']['torch_profile']['gpu_seconds_estimated'] == .2
    assert meta['gpu_metered'] is False and 'gpu_seconds' not in meta['usage']
    reports = ai_torch_diagnostics.recent_reports()
    assert reports[0]['job_id'] == meta['job_id'] and reports[0]['job_status'] == 'done'
    with db() as con:
        usage = json.loads(con.execute('SELECT usage_json FROM ai_compute_jobs WHERE id=?',
                                      (meta['job_id'],)).fetchone()[0])
    assert 'gpu_seconds' not in usage


def test_live_adapter_delivers_partial_before_completion(tmp_path, monkeypatch):
    import io
    import wave
    from app import ace_step_http_worker as worker
    data = io.BytesIO()
    with wave.open(data, 'wb') as wav:
        wav.setnchannels(1); wav.setsampwidth(2); wav.setframerate(44100); wav.writeframes(bytes(512))
    audio = data.getvalue()
    (tmp_path / 'inputs').mkdir()
    (tmp_path / 'inputs/source.wav').write_bytes(audio)
    plan = tmp_path / 'request.json'
    plan.write_text(json.dumps(dict(model_id='ace-step-1.5', prompt='orchestral',
                                   source_audio=[{'filename': 'inputs/source.wav'}])))
    queries = [0]
    snapshots = []
    def request(url, *args, **kwargs):
        if url.endswith('/release_task'):
            return b'{"data":{"task_id":"task"}}'
        if url.endswith('/query_result'):
            queries[0] += 1
            return json.dumps({'data': [{'task_id': 'task', 'status': 0 if queries[0] == 1 else 1,
                               'result': [{'file': '/v1/audio?test=1'}]}]}).encode()
        if '/mta/telemetry/' in url:
            return json.dumps(dict(task_id='task', source='ace-torch-profiler', billing_eligible=False,
                status='profiling' if queries[0] == 1 else 'profiled_kernels_diagnostic',
                gpu_active_seconds=.1 if queries[0] == 1 else .2,
                kernel_count=2, wall_seconds=1, device_id=0)).encode()
        return audio
    monkeypatch.setenv('MTA_ACE_STEP_URL', 'http://127.0.0.1:8001')
    monkeypatch.setattr(worker, '_request', request)
    monkeypatch.setattr(worker, 'AceProcessMeter', lambda *args: SimpleNamespace(sample=lambda: {}))
    monkeypatch.setattr(worker.time, 'sleep', lambda *args: None)
    monkeypatch.setattr(worker, '_progress', lambda *args, **kwargs:
                        snapshots.append((args, kwargs)))
    worker.run(plan, tmp_path / 'output.wav')
    assert any(args[0] == 'inference' and args[3].get('gpu_seconds_estimated') == .1
               for args, kwargs in snapshots)
    final = snapshots[-1][0][3]
    assert final['gpu_seconds_estimated'] == .2 and 'gpu_seconds' not in final


def test_live_ui_marks_partial_and_retains_final_result_on_reopen():
    import subprocess
    source = (Path(__file__).resolve().parents[1] / 'app/static/app.js').read_text()
    section = source[source.index('let aiArrangerWatchTimer=null;'):source.index('async function generateAndAddAiRemix()')]
    script = r'''const vm=require('vm'),assert=require('assert');
const elements={aiRemixJobProgress:{querySelector:()=>null},aiRemixGenerateButton:{},
aiRemixJobLabel:{},aiRemixJobHint:{},aiRemixJobElapsed:{},aiRemixPlanResult:{}};
let reply={job_id:'j',state:'running',gpu_metrics_source:'ace-torch-profiler',gpu_metrics_status:'profiling',gpu_seconds_estimated:.2};
const ctx={tr:(en,it)=>en,current:{id:'p'},document:{getElementById:id=>elements[id]},api:async()=>reply,
setTimeout:()=>1,clearTimeout(){},setInterval:()=>1,clearInterval(){}};
vm.createContext(ctx);vm.runInContext(process.argv[1],ctx);
(async()=>{
await vm.runInContext('aiArrangerWatchActive()',ctx);
assert.match(elements.aiRemixJobElapsed.textContent,/GPU: ~0.2.*parziali.*non fatturabile/);
reply={...reply,state:'completed',gpu_metrics_status:'profiled_kernels_diagnostic',gpu_seconds_estimated:.4};
await vm.runInContext('aiArrangerWatchActive()',ctx);
assert.equal(elements.aiRemixJobProgress.hidden,false);
assert.match(elements.aiRemixJobElapsed.textContent,/GPU: ~0.4/);
assert.doesNotMatch(elements.aiRemixJobElapsed.textContent,/parziali/);
})().catch(e=>{console.error(e);process.exitCode=1});'''
    result = subprocess.run(['node', '-e', script, section], capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize('exit_code', [0, 3])
def test_profiled_child_cli_runs_fixed_demucs_entrypoint_once(tmp_path, exit_code):
    import os
    import subprocess
    import sys
    package = tmp_path / 'demucs'
    package.mkdir()
    (package / '__init__.py').write_text('')
    (package / 'separate.py').write_text("from pathlib import Path\nPath('called').write_text('once')\nraise SystemExit("+str(exit_code)+")\n")
    (tmp_path / 'torch.py').write_text('''class version: hip=None
class profiler:
 class ProfilerActivity: CUDA=1
''')
    wrapper = Path(__file__).resolve().parents[1] / 'app/ai_profiled_backend.py'
    result = subprocess.run([sys.executable, str(wrapper), '--backend', 'demucs',
        '--task-id', 'task', '--report-dir', str(tmp_path), '--', '--name', 'm'],
        cwd=tmp_path, env={**os.environ, 'PYTHONPATH': str(tmp_path), 'MTA_AI_TORCH_PROFILER': 'true'},
        capture_output=True, text=True, timeout=20)
    assert result.returncode == exit_code, result.stderr
    assert (tmp_path / 'called').read_text() == 'once'
    report = json.loads((tmp_path / 'gpu-profile.json').read_text())
    assert report['task_id'] == 'task' and report['billing_eligible'] is False
