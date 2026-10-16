"""Long ACE budgets, actual diffusion-thread instrumentation and user cancellation."""
import json
from pathlib import Path
import subprocess
import sys
import threading
from types import SimpleNamespace

import pytest

from app.ace_task_control import TaskControl, TaskStopped, SERVICE_GUARD_SECONDS


class RecordingProfiler:
    def __init__(self):
        self.threads = []
    def wrap(self, fn):
        def run(*a, **kw):
            self.threads.append(threading.get_ident())
            return fn(*a, **kw)
        return run
    def get(self, task):
        return None


def fake_hooks(monkeypatch):
    hooks = []
    def register(fn):
        hooks.append(fn)
        return SimpleNamespace(remove=lambda: hooks.remove(fn))
    monkeypatch.setitem(sys.modules, 'torch', SimpleNamespace(nn=SimpleNamespace(modules=
        SimpleNamespace(module=SimpleNamespace(register_module_forward_pre_hook=register)))))
    return hooks


def test_long_generation_passes_600_seconds_and_profiles_gpu_thread(monkeypatch):
    hooks = fake_hooks(monkeypatch)
    clock = [0]
    controls = TaskControl(clock=lambda: clock[0])
    profiler = RecordingProfiler()
    controls.configure('long', timeout_seconds=3600)
    gpu_thread = []
    class Handler:
        def service_generate(self):
            gpu_thread.append(threading.get_ident())
            clock[0] = 660
            for hook in list(hooks):
                hook(None, None)
            return b'full-song'
    handler = Handler()
    def upstream(*, job_id, selected_handler):
        result = []
        child = threading.Thread(target=lambda: result.append(selected_handler.service_generate()))
        child.start(); child.join(2)
        assert not child.is_alive()
        return result[0]
    assert controls.wrap(upstream, profiler)(job_id='long', selected_handler=handler) == b'full-song'
    assert profiler.threads == gpu_thread
    assert profiler.threads[0] != threading.get_ident()
    assert controls.configure('long')['state'] == 'completed'
    assert not hooks and 'service_generate' not in handler.__dict__


@pytest.mark.parametrize('cancel', [True, False])
def test_checkpoint_stops_child_for_cancel_or_selected_budget(monkeypatch, cancel):
    hooks = fake_hooks(monkeypatch)
    clock = [0]
    controls = TaskControl(clock=lambda: clock[0])
    controls.configure('task', timeout_seconds=60)
    result = []
    handler = SimpleNamespace()
    def service():
        if cancel:
            controls.configure('task', cancel=True)
        else:
            clock[0] = 61
        for hook in list(hooks):
            hook(None, None)
        pytest.fail('cancelled model must not continue')
    handler.service_generate = service
    def upstream(*, job_id, selected_handler):
        def gpu():
            try:
                selected_handler.service_generate()
            except Exception as exc:
                result.append(exc)
        child = threading.Thread(target=gpu)
        child.start(); child.join(2)
        assert not child.is_alive()
        # Upstream catches the GPU exception; the outer check must still reject.
        return b'output that must never be published'
    with pytest.raises(TaskStopped, match='cancelled' if cancel else 'timeout'):
        controls.wrap(upstream, RecordingProfiler())(job_id='task', selected_handler=handler)
    assert isinstance(result[0], TaskStopped)
    assert handler.service_generate is service and not hooks
    assert controls.configure('task')['state'] == ('cancelled' if cancel else 'failed')


@pytest.mark.parametrize('value', [True, 59, 14401, '3600'])
def test_budget_is_bounded_and_cannot_be_extended(value):
    controls = TaskControl()
    with pytest.raises(ValueError):
        controls.configure('task', timeout_seconds=value)
    controls.configure('task', timeout_seconds=3600)
    assert controls.configure('task', timeout_seconds=3600)['timeout_seconds'] == 3600
    with pytest.raises(ValueError):
        controls.configure('task', timeout_seconds=7200)


def test_cancel_before_execution_does_not_start_model():
    controls = TaskControl()
    controls.configure('queued', cancel=True)
    calls = []
    with pytest.raises(TaskStopped):
        controls.wrap(lambda **kw: calls.append(1), RecordingProfiler())(job_id='queued')
    assert calls == []


def test_runtime_control_auth_ceiling_and_fixed_task_scope(monkeypatch):
    from fastapi import FastAPI, Header, HTTPException
    from fastapi.testclient import TestClient
    from app.ace_profile_server import install
    monkeypatch.setenv('ACESTEP_QUEUE_WORKERS', '1')
    module = SimpleNamespace(_DEFAULT_GENERATION_TIMEOUT=600)
    monkeypatch.setitem(sys.modules, 'acestep.core.generation.handler.generate_music_execute', module)
    async def auth(authorization: str | None = Header(None)):
        if authorization != 'Bearer test':
            raise HTTPException(401)
    def generate(*, job_id):
        return b'audio'
    server = SimpleNamespace(app=FastAPI(), verify_api_key=auth, run_blocking_generate=generate)
    install(server, RecordingProfiler())
    client = TestClient(server.app)
    path = '/mta/tasks/real-task/control'
    assert client.post(path, json={'cancel': True}).status_code == 401
    assert client.get('/mta/runtime').status_code == 401
    headers = {'Authorization': 'Bearer test'}
    assert client.get('/mta/runtime', headers=headers).json()['task_control'] is True
    assert module._DEFAULT_GENERATION_TIMEOUT == SERVICE_GUARD_SECONDS > 14400
    assert client.post(path, headers=headers, json={'timeout_seconds': 3600}).status_code == 200
    for body in ({'timeout_seconds': 0}, {'cancel': 'yes'}, {'pid': 1}, {'timeout_seconds': 7200}):
        assert client.post(path, headers=headers, json=body).status_code == 422
    report = client.post(path, headers=headers, json={'cancel': True}).json()
    assert report['cancel_requested'] is True and report['billing_eligible'] is False


def test_adapter_forwards_budget_and_cancels_backend_after_failure(monkeypatch, tmp_path):
    from app import ace_step_http_worker as worker
    source = tmp_path / 'source.wav'; source.write_bytes(b'staged-source')
    plan = tmp_path / 'request.json'
    plan.write_text(json.dumps({'model_id': 'ace-step-1.5', 'prompt': 'orchestra', 'inference_timeout_seconds': 7200}))
    calls = []
    def request(url, data=None, *a, **kw):
        calls.append((url, json.loads(data) if data and '/control' in url else None))
        if url.endswith('/release_task'):
            return b'{"data":{"task_id":"ace-task"}}'
        if url.endswith('/control'):
            return b'{"task_id":"ace-task","state":"running","cancel_requested":true}'
        if url.endswith('/query_result'):
            return json.dumps({'data': [{'task_id': 'ace-task', 'status': 2,
                'result': '[{"error":"Music generation timed out after 600 seconds secret=DO_NOT_COPY"}]'}]}).encode()
        return b'{}'
    monkeypatch.setattr(worker, '_request', request)
    monkeypatch.setattr(worker, '_source_path', lambda *a: source)
    monkeypatch.setattr(worker, 'AceProcessMeter', lambda *a: SimpleNamespace(sample=lambda: {}))
    progress = tmp_path / 'progress.json'
    monkeypatch.setenv('MTA_AI_PROGRESS_FILE', str(progress))
    with pytest.raises(RuntimeError, match='backend generation timeout') as exc:
        worker.run(plan, tmp_path / 'output.wav')
    assert 'DO_NOT_COPY' not in str(exc.value)
    controls = [body for url, body in calls if url.endswith('/control')]
    assert controls == [{'cancel': False, 'timeout_seconds': 7200}, {'cancel': True}]
    assert json.loads(progress.read_text())['_ace_task_id'] == 'ace-task'
    assert not (tmp_path / 'output.wav').exists()


def test_supervisor_delivers_cancel_even_after_adapter_is_killed(monkeypatch, tmp_path):
    from app.ai_worker_protocol import _ace_remote_cleanup
    from app import ace_step_http_worker as worker
    path = tmp_path / 'private-progress.json'
    path.write_text(json.dumps({'_ace_task_id': 'known-task'}))
    seen = []
    monkeypatch.setattr(worker, '_control_task', lambda *a, **kw: seen.append((a, kw)) or True)
    with pytest.raises(RuntimeError, match='worker killed'):
        with _ace_remote_cleanup({'model_id': 'ace-step-1.5'}, lambda: path):
            raise RuntimeError('worker killed')
    assert seen[0][0][1] == 'known-task' and seen[0][1] == {'cancel': True}
    with pytest.raises(RuntimeError):
        with _ace_remote_cleanup({'model_id': 'other'}, lambda: path):
            raise RuntimeError()
    assert len(seen) == 1


def test_project_cancel_route_authorizes_before_job_and_rejects_other_project(monkeypatch):
    from fastapi import HTTPException
    from app import main
    seen = []
    def deny(*a):
        raise HTTPException(404)
    monkeypatch.setattr(main, '_project_for_actor', deny)
    monkeypatch.setattr(main.ai_arranger_runtime, 'cancel', lambda job: seen.append(job) or {'state': 'cancelled'})
    with pytest.raises(HTTPException):
        main.ai_arranger_cancel_generation('p', 'job', None)
    assert seen == []
    monkeypatch.setattr(main, '_project_for_actor', lambda *a: None)
    monkeypatch.setattr(main.ai_arranger_runtime, 'get', lambda job: {'project_id': 'other', 'operation': 'arranger'})
    with pytest.raises(HTTPException) as exc:
        main.ai_arranger_cancel_generation('p', 'job', None)
    assert exc.value.status_code == 404 and seen == []
    monkeypatch.setattr(main.ai_arranger_runtime, 'get', lambda job: {'project_id': 'p', 'operation': 'arranger'})
    assert main.ai_arranger_cancel_generation('p', 'job', None)['state'] == 'cancelled'
    assert seen == ['job']


def test_generate_button_cancels_reopened_job_instead_of_submitting_again():
    root = Path(__file__).resolve().parents[1]
    source = (root / 'app/static/app.js').read_text()
    section = source[source.index('let aiArrangerWatchTimer=null;'):source.index('// r193: native-only')]
    js = r'''
const vm=require('vm'),assert=require('assert');let next,posts=[],newJobs=0;
let reply={job_id:'job',state:'running',phase:'inference'};
const elements={aiRemixGenerateButton:{},aiRemixPlanResult:{},aiRemixJobLabel:{},aiRemixJobHint:{},
aiRemixJobProgress:{querySelector:()=>null},aiRemixJobElapsed:{}};
const ctx={current:{id:'p'},document:{getElementById:id=>elements[id]},
api:async(url,options)=>{if(options){posts.push(url);reply={...reply,cancel_requested:true};return reply}return reply},
planAiRemix:async()=>{newJobs++},setTimeout:f=>{next=f;return 1},clearTimeout(){},setInterval:()=>1,clearInterval(){}};
vm.createContext(ctx);vm.runInContext(process.argv[1],ctx);
(async()=>{
await ctx.aiArrangerWatchActive();
const button=elements.aiRemixGenerateButton;
assert.equal(button.disabled,false);assert.match(button.textContent,/Cancel job/);
await ctx.generateAndAddAiRemix();
assert.equal(newJobs,0);assert.equal(posts[0],'/api/projects/p/ai-arranger/generations/job/cancel');
assert.equal(button.disabled,true);assert.match(button.textContent,/Cancelling/);
await ctx.generateAndAddAiRemix();assert.equal(posts.length,1);
reply={job_id:'job',state:'cancelled'};await next();
assert.equal(button.disabled,false);assert.match(button.textContent,/Generate/);
await ctx.generateAndAddAiRemix();assert.equal(newJobs,1);
})().catch(e=>{console.error(e);process.exitCode=1});
'''
    result = subprocess.run(['node', '-e', js, section], capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr


def test_running_queue_cancellation_is_not_hidden_by_worker_progress(monkeypatch, tmp_path):
    from app import ai_arranger_runtime as runtime
    import time
    monkeypatch.setattr(runtime, '_ROOT', tmp_path)
    entered, finish = threading.Event(), threading.Event()
    def work(progress, stop):
        progress.write_text(json.dumps({'phase': 'inference', 'message': 'still rendering'}))
        entered.set()
        finish.wait(5)
    try:
        _, job = runtime.start('project-cancel', 'arranger', work, cancellable=True)
        assert entered.wait(2)
        status = runtime.cancel(job['job_id'])
        assert status['state'] == 'running' and status['phase'] == 'cancelling'
        assert status['cancel_requested'] is True
        finish.set()
        for _ in range(100):
            status = runtime.get(job['job_id'])
            if status['state'] == 'cancelled':
                break
            time.sleep(.02)
        assert status['state'] == 'cancelled'
        assert status['cpu_seconds'] is None and status['gpu_seconds'] is None
    finally:
        finish.set()


def test_failure_classification_survives_redacted_zip_without_secret(monkeypatch, tmp_path):
    import logging
    from app import diagnostic_bundle as diag
    from app.ai_cgroup_metering import _worker_failure
    monkeypatch.setattr(diag, 'BASE', tmp_path)
    monkeypatch.setenv('MTA_DIAGNOSTICS_ENABLED', 'true')
    handler = diag.SafeEvents()
    record = logging.LogRecord('worker', logging.ERROR, __file__, 1,
        'ACE-Step adapter error: secret=DO_NOT_COPY', (), None)
    record.mta_worker_failure = _worker_failure('ACE-Step backend generation timeout secret=DO_NOT_COPY', 1)
    handler.emit(record)
    event = json.loads((diag.directory() / 'events.jsonl').read_text().splitlines()[-1])
    assert event['worker_failure']['category'] == 'ace_backend_timeout'
    assert event['worker_failure']['metering_valid'] is False
    assert 'DO_NOT_COPY' not in json.dumps(event)


def test_project_cancel_http_auth_csrf_and_access(monkeypatch):
    from fastapi.testclient import TestClient
    from app import main, auth
    from app.models import Project
    identity = [None]
    monkeypatch.setattr(main, 'session_user', lambda request: identity[0])
    monkeypatch.setattr(auth, 'session_user', lambda request: identity[0])
    monkeypatch.setattr(main, 'check_basic_auth', lambda request: False)
    monkeypatch.setattr(main, 'public_user', lambda user: user)
    monkeypatch.setattr(main, 'load_project', lambda pid: Project(id=pid, title='Test', owner_user_id=7))
    monkeypatch.setattr(main.ai_arranger_runtime, 'get', lambda job: {'project_id': 'p', 'operation': 'arranger'})
    cancelled = []
    monkeypatch.setattr(main.ai_arranger_runtime, 'cancel', lambda job: cancelled.append(job) or {'state': 'cancelled'})
    client = TestClient(main.app)
    path = '/api/projects/p/ai-arranger/generations/job/cancel'
    headers = {'x-mta-request': '1'}
    assert client.post(path, headers=headers).status_code == 401
    identity[0] = {'id': 7, 'role': 'user'}
    assert client.post(path).status_code == 403
    identity[0] = {'id': 8, 'role': 'user'}
    assert client.post(path, headers=headers).status_code == 404
    identity[0] = {'id': 7, 'role': 'user'}
    assert client.post(path, headers=headers).status_code == 200
    assert cancelled == ['job']


@pytest.mark.skipif(sys.platform != 'linux', reason='Production Linux wait4 supervisor')
def test_real_adapter_termination_delivers_http_cancel(monkeypatch, tmp_path):
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    import time
    import wave
    from app import ai_worker_protocol as protocol, audio_engine
    from app.models import Project, Track
    received = []
    class API(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass
        def do_POST(self):
            received.append((self.path, json.loads(self.rfile.read(int(self.headers['Content-Length'])))))
            body = b'{"task_id":"remote-task","state":"running","cancel_requested":true}'
            self.send_response(200); self.send_header('Content-Length', str(len(body))); self.end_headers()
            self.wfile.write(body)
    server = ThreadingHTTPServer(('127.0.0.1', 0), API)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True); server_thread.start()
    worker = tmp_path / 'adapter.py'
    worker.write_text('''import json,os,pathlib,time
pathlib.Path(os.environ['MTA_AI_PROGRESS_FILE']).write_text(json.dumps({'_ace_task_id':'remote-task'}))
while True: time.sleep(.05)
''')
    progress = tmp_path / 'progress.json'
    stop = threading.Event()
    def request_cancel():
        for _ in range(200):
            if progress.exists():
                stop.set()
                return
            time.sleep(.01)
    trigger = threading.Thread(target=request_cancel, daemon=True)
    def render(project, resolver, target, **kw):
        with wave.open(str(target), 'wb') as stream:
            stream.setnchannels(1);stream.setsampwidth(2);stream.setframerate(44100)
            stream.writeframes(b'\0\0' * 441)
    monkeypatch.setattr(protocol, 'configured_worker', lambda: worker)
    monkeypatch.setattr(audio_engine, 'render_mix', render)
    monkeypatch.delenv('MTA_AI_CGROUP_PARENT', raising=False)
    monkeypatch.setenv('MTA_ACE_STEP_URL', f'http://127.0.0.1:{server.server_port}')
    try:
        trigger.start()
        project = Project(id='p', title='Test', tracks=[Track(id='t', name='Source', filename='source.wav')])
        with pytest.raises(protocol.WorkerUnavailable, match='cancelled'):
            protocol.run_worker_with_project_audio({'model_id': 'ace-step-1.5', 'input_source': 'master'},
                project, lambda *a: None, cancel_event=stop, progress_file=progress)
        assert received == [('/mta/tasks/remote-task/control', {'cancel': True})]
    finally:
        stop.set();trigger.join(3)
        server.shutdown();server.server_close();server_thread.join(3)


def test_cancellation_of_pending_ace_task_is_not_expired_before_execution():
    clock = [0]
    controls = TaskControl(clock=lambda: clock[0])
    controls.configure('queued', timeout_seconds=3600, cancel=True)
    clock[0] = SERVICE_GUARD_SECONDS + 1
    controls.configure('another-task', timeout_seconds=60)
    calls = []
    with pytest.raises(TaskStopped, match='cancelled'):
        controls.wrap(lambda **kw: calls.append(1), RecordingProfiler())(job_id='queued')
    assert calls == []
