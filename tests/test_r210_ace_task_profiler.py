"""Actual ACE hook, bounded job reports and kernel interval union; never billing."""
import json
from pathlib import Path
from types import SimpleNamespace
import pytest
from app.ace_gpu_profiler import TaskProfiler, kernel_activity, parse_report


def event(start,duration,device=0,category='kernel'):
    return {'ph':'X','cat':category,'ts':start,'dur':duration,'args':{'device':device}}


def test_kernel_union_ignores_api_time_and_overlapping_streams():
    trace={'traceEvents':[event(0,200_000),event(100_000,200_000),event(500_000,100_000),
                          event(0,9_000_000,category='hip_runtime')]}
    assert kernel_activity(trace,1)==(.4,3,0)


@pytest.mark.parametrize('events',[ [event(0,1,0),event(0,1,1)], [event(0,float('nan'))],
    [event(-1,5)], [event(0,9_000_000)], [event(0,1,device=None)] ])
def test_invalid_ambiguous_or_impossible_intervals(events):
    with pytest.raises(ValueError): kernel_activity({'traceEvents':events},1)


def fake_torch(trace, *, start_fails=False, stop_fails=False):
    class Profile:
        def start(self):
            if start_fails: raise RuntimeError('unsupported collector')
        def stop(self):
            if stop_fails: raise RuntimeError('trace collection failed')
        def export_chrome_trace(self,name):Path(name).write_text(json.dumps(trace))
    profiler=SimpleNamespace(ProfilerActivity=SimpleNamespace(CUDA='gpu'),
        supported_activities=lambda:{'gpu'},profile=lambda **kw:Profile())
    return SimpleNamespace(profiler=profiler,version=SimpleNamespace(hip='7.2'),
                           cuda=SimpleNamespace(is_available=lambda:True,synchronize=lambda:None))


def test_capture_is_task_bound_and_never_exposes_trace(tmp_path,monkeypatch):
    monkeypatch.setattr('tempfile.tempdir',str(tmp_path))
    torch=fake_torch({'traceEvents':[event(10,100_000)]})
    collector=TaskProfiler(lambda:torch,clock=lambda:1)
    # Use an interval within timing tolerance of a nonzero measured capture.
    ticks=iter([0,0,1,1]);collector._clock=lambda:next(ticks)
    calls=[]
    def original(*,job_id):calls.append(job_id);return {'audio':'actual-result'}
    assert collector.wrap(original)(job_id='ace-task')=={'audio':'actual-result'}
    collector._clock=lambda:1
    report=collector.get('ace-task')
    assert report['status']=='profiled_kernels_diagnostic'
    assert calls==['ace-task'] and report['billing_eligible'] is False
    normalized=parse_report(report,'ace-task')
    assert normalized['gpu_seconds_estimated']==.1 and 'gpu_seconds' not in normalized
    assert 'traceEvents' not in report and not list(tmp_path.iterdir())
    with pytest.raises(ValueError):parse_report(report,'different-task')


@pytest.mark.parametrize('start,stop,status',[(True,False,'profiler_unavailable'),(False,True,'profiler_failed')])
def test_profiler_failure_keeps_successful_audio(start,stop,status):
    torch=fake_torch({},start_fails=start,stop_fails=stop)
    collector=TaskProfiler(lambda:torch)
    calls=[]
    def original(**kw):calls.append(1);return b'audio'
    assert collector.wrap(original)(job_id='task')==b'audio'
    assert calls==[1] and collector.get('task')['status']==status


def test_original_failure_not_hidden_or_retried():
    collector=TaskProfiler(lambda:fake_torch({'traceEvents':[]}))
    def original(**kw):raise ValueError('generation failed')
    with pytest.raises(ValueError,match='generation failed'):collector.wrap(original)(job_id='task')
    assert collector.get('task')['status']=='profiler_no_gpu_events'


def test_reports_expire_and_storage_is_bounded():
    clock=[0];collector=TaskProfiler(clock=lambda:clock[0])
    for n in range(140):collector._save(str(n),{'task_id':str(n)})
    assert len(collector._records)==128 and collector.get('0') is None
    clock[0]=3601
    assert collector.get('139') is None


def test_endpoint_uses_upstream_auth_and_exact_task_identity(monkeypatch):
    from fastapi import FastAPI,Header,HTTPException
    from fastapi.testclient import TestClient
    from app.ace_profile_server import install
    monkeypatch.setenv('ACESTEP_QUEUE_WORKERS','1')
    async def auth(authorization: str | None=Header(None)):
        if authorization!='Bearer secret':raise HTTPException(401)
    def original(*,job_id):return b'audio'
    server=SimpleNamespace(app=FastAPI(),verify_api_key=auth,run_blocking_generate=original)
    collector=TaskProfiler(lambda:fake_torch({'traceEvents':[]}))
    install(server,collector);server.run_blocking_generate(job_id='real-task')
    with TestClient(server.app) as client:
        assert client.get('/mta/telemetry/real-task').status_code==401
        response=client.get('/mta/telemetry/real-task',headers={'Authorization':'Bearer secret'})
        assert response.status_code==200 and response.json()['billing_eligible'] is False
        assert client.get('/mta/telemetry/other',headers={'Authorization':'Bearer secret'}).status_code==404
    monkeypatch.setenv('ACESTEP_QUEUE_WORKERS','2')
    with pytest.raises(RuntimeError):install(server)


def test_worker_missing_or_bad_report_cannot_break_generation(monkeypatch):
    from app import ace_step_http_worker as worker
    monkeypatch.setattr(worker,'_request',lambda *a,**kw:b'{"status":[]}')
    assert worker._profile_result('http://127.0.0.1:8001','task')=={}
    monkeypatch.setattr(worker,'_request',lambda *a,**kw: (_ for _ in ()).throw(OSError('no endpoint')))
    assert worker._profile_result('http://127.0.0.1:8001','task')=={}
    assert worker._profile_result('http://127.0.0.1:8001','../escape')=={}


def test_opt_in_override_is_reversible_and_preserves_base_unit(tmp_path):
    from app.configure_ace_gpu_profiler import configure
    base=tmp_path/'base';python=base/'venv-ace-step/bin/python';python.parent.mkdir(parents=True);python.write_text('test executable')
    wrapper=tmp_path/'ace_profile_server.py';wrapper.write_text('wrapper')
    units=tmp_path/'systemd';units.mkdir();original=units/'mta-ace-step.service';original.write_text('original service')
    target=configure(base=base,wrapper=wrapper,unit_root=units)
    assert 'ACESTEP_QUEUE_WORKERS=1' in target.read_text() and ' --no-init' in target.read_text()
    assert original.read_text()=='original service'
    configure(base=base,wrapper=wrapper,unit_root=units,enabled=False)
    assert not target.exists() and original.read_text()=='original service'


def test_installed_launcher_patches_canonical_api_module(tmp_path):
    import os
    import subprocess
    import sys
    package=tmp_path/'acestep';package.mkdir();(package/'__init__.py').write_text('')
    (package/'api_server.py').write_text('''
from fastapi import FastAPI
app=FastAPI()
async def verify_api_key():pass
def run_blocking_generate(*,job_id):return 'original-audio'
def main():
    import sys
    assert sys.modules['acestep.api_server'].run_blocking_generate is run_blocking_generate
    assert hasattr(run_blocking_generate,'__wrapped__')
    assert run_blocking_generate(job_id='installed-task')=='original-audio'
    assert '/mta/telemetry/{task_id}' in [route.path for route in app.routes]
    print('instrumented canonical ACE server')
''')
    root=Path(__file__).resolve().parents[1]
    result=subprocess.run([sys.executable,str(root/'app/ace_profile_server.py'),'--no-init'],
        cwd=tmp_path,env={**os.environ,'PYTHONPATH':str(tmp_path),'ACESTEP_QUEUE_WORKERS':'1'},
        capture_output=True,text=True,timeout=15)
    assert result.returncode==0,result.stderr
    assert 'instrumented canonical ACE server' in result.stdout


def test_profiler_source_and_status_survive_queue_metadata_filter():
    from app.ai_arranger_runtime import _gpu_metadata
    assert _gpu_metadata({'gpu_metrics_source':'ace-torch-profiler',
        'gpu_metrics_status':'profiled_kernels_diagnostic'})=={
        'gpu_metrics_source':'ace-torch-profiler','gpu_metrics_status':'profiled_kernels_diagnostic'}


@pytest.mark.parametrize('changes',[{'status':[]},{'billing_eligible':True},
    {'gpu_active_seconds':0},{'gpu_active_seconds':float('inf')},
    {'kernel_count':True},{'device_id':-1},{'gpu_active_seconds':99}])
def test_malformed_reports_never_become_gpu_seconds(changes):
    report={'task_id':'task','source':'ace-torch-profiler','status':'profiled_kernels_diagnostic',
        'gpu_active_seconds':.1,'wall_seconds':1,'kernel_count':1,'device_id':0,'billing_eligible':False}
    report.update(changes)
    with pytest.raises(ValueError):parse_report(report,'task')


@pytest.mark.parametrize('available',[True,False])
def test_failed_profiler_never_relabels_host_estimates(monkeypatch,available):
    from app import ace_step_http_worker as worker
    host={'gpu_metrics_source':'proxmox-host-drm','gpu_metrics_status':'sampled_process'}
    if available:host['gpu_seconds_estimated']=.5
    monkeypatch.setattr(worker,'_profile_result',lambda *a:{'gpu_metrics_source':'ace-torch-profiler','gpu_metrics_status':'profiler_unavailable'})
    result=worker._task_telemetry(SimpleNamespace(sample=lambda:dict(host)),'base','task')
    if available:
        assert result==host
    else:
        assert 'gpu_seconds_estimated' not in result and result['gpu_metrics_status']=='profiler_unavailable'


def test_profiler_stops_even_when_final_device_sync_fails():
    calls=[];syncs=[]
    class Profile:
        def start(self):calls.append('start')
        def stop(self):calls.append('stop')
    torch=fake_torch({})
    torch.profiler.profile=lambda **kw:Profile()
    def synchronize():
        syncs.append(1)
        if len(syncs)>1:raise RuntimeError('device synchronization failed')
    torch.cuda.synchronize=synchronize
    collector=TaskProfiler(lambda:torch)
    assert collector.wrap(lambda **kw:b'audio')(job_id='task')==b'audio'
    assert calls==['start','stop'] and collector.get('task')['status']=='profiler_failed'
