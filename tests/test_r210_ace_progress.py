"""ACE progress is phase-based, optional and never a billing measurement."""
import json
from pathlib import Path
import subprocess
import threading
from types import SimpleNamespace

from fastapi import FastAPI, Header, HTTPException
from fastapi.testclient import TestClient
import pytest
from app import ace_task_progress as progress
from app.ace_task_control import TaskControl


def model_handler(hooks):
    class Turbo:
        __module__='acestep.models.modeling_acestep_v15_turbo'
    model=Turbo()
    def register(hook):
        hooks.append(hook)
        return SimpleNamespace(remove=lambda: hooks.remove(hook))
    model.decoder=SimpleNamespace(register_forward_hook=register)
    return SimpleNamespace(model=model)


def test_observed_evaluations_owner_thread_cleanup_and_no_completion_claim():
    controls=TaskControl();hooks=[];handler=model_handler(hooks)
    with progress.observe_decoder(controls,'task',handler,{'infer_steps':8}):
        other=threading.Thread(target=lambda:hooks[0]())
        other.start();other.join()
        assert controls.tasks=={}
        for n in range(8):
            hooks[0]()
            data=progress.safe_progress(controls.tasks['task']['progress'],'task')
            assert data['steps_completed']==n+1 and data['steps_total']==8
            assert data['progress_percent']<100 and data['progress_estimated'] is True
        # A time-based upstream callback must not overwrite counted DiT work.
        progress.update(controls,'task',.7)
        assert controls.tasks['task']['progress']['steps_completed']==8
    assert hooks==[]
    progress.update(controls,'task',1)
    assert controls.tasks['task']['progress']['progress_percent']==99
    assert 'gpu_seconds' not in controls.tasks['task']['progress']


@pytest.mark.parametrize('options',[{'sampler_mode':'heun'},{'timesteps':[1,.5]}, {'cover_noise_strength':.1},{'infer_steps':True}])
def test_unknown_step_semantics_fall_back_to_stage(options):
    hooks=[];control=TaskControl()
    with progress.observe_decoder(control,'task',model_handler(hooks),{'infer_steps':8,**options}):
        assert not hooks
    assert control.tasks=={}


def test_observer_overflow_invalidates_and_callback_failure_never_retries_audio():
    hooks=[];control=TaskControl()
    with progress.observe_decoder(control,'task',model_handler(hooks),{'infer_steps':1}):
        hooks[0]();hooks[0]()
        assert 'progress' not in control.tasks['task']
    class BadHook:
        def remove(self): raise RuntimeError('optional cleanup')
    handler=model_handler([])
    handler.model.decoder.register_forward_hook=lambda _:BadHook()
    with progress.observe_decoder(control,'task',handler,{'infer_steps':2}):
        pass


@pytest.mark.parametrize('changes',[{'task_id':'foreign'}, {'progress_percent':float('nan')},
    {'progress_percent':True},{'progress_percent':100},{'steps_completed':9,'steps_total':8},
    {'progress_source':'wall-clock'}])
def test_untrusted_progress_rejected(changes):
    record={'task_id':'task','progress_percent':60,'progress_source':'ace-stage-estimate',**changes}
    assert progress.safe_progress(record,'task')=={}


def test_callback_forwarded_once_and_authenticated_progress_route(monkeypatch):
    from app.ace_profile_server import install
    from app import ace_task_control
    monkeypatch.setenv('ACESTEP_QUEUE_WORKERS','1')
    # No torch needed: exercise the genuine wrapper's progress callback path.
    from contextlib import nullcontext
    monkeypatch.setattr(ace_task_control.TaskControl,'checkpoints',lambda *args:nullcontext())
    calls=[]
    def generate(*,progress):
        calls.append('audio');progress(.6,desc='never persisted secret');return b'audio'
    def upstream(*,job_id,generate_music_fn):
        return generate_music_fn(progress=lambda v,**kw:calls.append(v))
    async def auth(authorization: str | None=Header(None)):
        if authorization!='Bearer test':raise HTTPException(401)
    class Profiler:
        def wrap(self,fn):return fn
        def get(self,task):return None
    server=SimpleNamespace(app=FastAPI(),verify_api_key=auth,run_blocking_generate=upstream)
    install(server,Profiler());client=TestClient(server.app)
    assert server.run_blocking_generate(job_id='task',generate_music_fn=generate)==b'audio'
    assert calls==['audio',.6]
    path='/mta/tasks/task/progress'
    assert client.get(path).status_code==401
    data=client.get(path,headers={'Authorization':'Bearer test'}).json()
    assert data['progress_percent']==60 and data['progress_estimated'] is True
    assert 'secret' not in json.dumps(data)
    assert client.get('/mta/tasks/other/progress',headers={'Authorization':'Bearer test'}).status_code==404


def test_real_ui_terminal_cancel_has_no_waiting_hint_and_visible_metrics():
    source=(Path(__file__).parents[1]/'app/static/app.js').read_text()
    section=source[source.index('let aiArrangerWatchTimer=null;'):source.index('async function generateAndAddAiRemix()')]
    script=r'''const vm=require('vm'),assert=require('assert');
const ids=['aiRemixJobProgress','aiRemixGenerateButton','aiRemixJobLabel','aiRemixJobHint','aiRemixJobElapsed','aiMeterCpu','aiMeterGpu','aiMeterElapsed','aiMeterCpuNote','aiMeterGpuNote'];
const elements=Object.fromEntries(ids.map(id=>[id,{}]));elements.aiRemixJobProgress.querySelector=()=>null;
const job={state:'cancelled',cancel_requested:true,phase:'cancelled',job_id:'j',elapsed_seconds:10,cpu_seconds_estimated:8.6,gpu_seconds_estimated:7,gpu_metrics_source:'ace-torch-profiler'};
const ctx={tr:(en,it)=>it,current:{id:'p'},document:{getElementById:id=>elements[id]},setInterval(){},clearInterval(){}};
vm.createContext(ctx);vm.runInContext(process.argv[1],ctx);ctx.aiArrangerRenderProgress(job,true);
vm.runInContext('aiArrangerLastSnapshot='+JSON.stringify(job),ctx);ctx.aiArrangerRenderElapsed();
assert.match(elements.aiRemixJobHint.textContent,/Annullamento completato/);assert.doesNotMatch(elements.aiRemixJobHint.textContent,/waiting|attesa/);
assert.equal(elements.aiRemixGenerateButton.disabled,false);assert.equal(elements.aiMeterCpu.textContent,'~8.6 s');assert.equal(elements.aiMeterGpu.textContent,'~7.0 s');assert.match(elements.aiMeterGpuNote.textContent,/Stima diagnostica attendibile/);
'''
    result=subprocess.run(['node','-e',script,section],capture_output=True,text=True,timeout=10)
    assert result.returncode==0,result.stderr
