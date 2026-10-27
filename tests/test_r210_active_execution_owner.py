"""Durable queue identity at dispatch; no worker or billing for stale contexts."""
from contextlib import contextmanager
import os
import sys
import subprocess
import threading

import pytest

from app import ai_arranger_runtime as queue,ai_global_execution as execution,auth
from test_r210_queue_identity_stem_metering import env as env  # noqa: F401

pytestmark=pytest.mark.skipif(sys.platform!='linux',reason='Linux server ownership/wait4 acceptance; native fallback is simulated, not installed-OS proof')


@contextmanager
def scope(job='active-owner',event=None):
    token=execution.current_job.set(job)
    cancel=execution.current_cancel.set(event)
    try:yield
    finally:
        execution.current_cancel.reset(cancel)
        execution.current_job.reset(token)


@pytest.fixture
def running(env):
    queue.start('project','worker:markers',None,job_id='active-owner',defer_spawn=True,
                payload={'schema_version':1,'actor_user_id':env,'kind':'markers'})
    assert queue._claim('active-owner')
    return env


@pytest.mark.parametrize('state',['queued','blocked','completed','failed','cancelled','interrupted'])
def test_terminal_or_unstarted_queue_context_never_dispatches(running,state):
    called=[]
    with queue._db() as c:c.execute('UPDATE jobs SET state=? WHERE job_id=?',(state,'active-owner'))
    with scope(),pytest.raises(ValueError,match='Authenticated active'):
        execution.execute(running,'markers',lambda _:called.append(True))
    assert not called


def test_missing_queue_context_does_not_become_a_new_permit(env):
    called=[]
    with scope('absent-job'),pytest.raises(ValueError,match='Authenticated active'):
        execution.execute(env,'markers',lambda _:called.append(True))
    assert not called


def test_nested_cross_owner_rejected_but_same_owner_keeps_one_slot(env):
    calls=[]
    def outer(cancelled):
        with pytest.raises(ValueError,match='owner mismatch'):
            execution.execute(env+1,'markers',lambda _:calls.append('foreign'))
        return execution.execute(env,'markers',lambda _:calls.append('owner') or 'ok')
    assert execution.execute(env,'whisper',outer)=='ok'
    assert calls==['owner']
    rows=queue.list_jobs()
    assert len(rows)==1 and rows[0]['state']=='completed' and rows[0]['actor_user_id']==env


@pytest.mark.parametrize('kind',['local','pull'])
def test_public_worker_rejects_foreign_owner_before_routing_or_ledger(running,monkeypatch,kind):
    from app import ai_metering_agent as agent,ai_pull_coordinator as pull
    calls=[]
    monkeypatch.setattr(pull,'mode',lambda:calls.append('route') or kind)
    with scope(),pytest.raises(ValueError,match='owner mismatch'):
        agent.execute_registered_worker(running+1,'markers',{})
    assert not calls
    with auth.db() as c:assert c.execute('SELECT count(*) FROM ai_compute_jobs').fetchone()[0]==0


@pytest.mark.parametrize('change',['runner_pid','runner_identity','missing_identity','missing_actor'])
def test_wrong_supervisor_or_unknown_identity_is_not_execution_authority(running,monkeypatch,change):
    if change=='missing_identity':
        monkeypatch.setattr(queue,'_process_identity',lambda _:None)
        with queue._db() as c:c.execute('UPDATE jobs SET runner_identity=NULL')
    else:
        with queue._db() as c:
            c.execute({'runner_pid':'UPDATE jobs SET runner_pid=-1',
                       'runner_identity':"UPDATE jobs SET runner_identity='different-instance'",
                       'missing_actor':'UPDATE jobs SET actor_user_id=NULL'}[change])
    with scope(),pytest.raises(ValueError,match='Authenticated active'):
        execution.active_owner(running)


@pytest.mark.parametrize('origin',['persisted','event','callback'])
def test_cancelled_context_rejects_new_stage_before_callback(running,origin):
    event=threading.Event();called=[]
    if origin=='event':event.set()
    if origin=='persisted':
        with queue._db() as c:c.execute('UPDATE jobs SET cancel_requested=1')
    with scope(event=event),pytest.raises(RuntimeError,match='cancelled before dispatch'):
        execution.execute(running,'markers',lambda _:called.append(True),cancel_check=lambda:origin=='callback')
    assert not called


def test_server_source_conversion_rejects_inactive_context(running,tmp_path):
    from app import ai_server_execution as server
    with queue._db() as c:c.execute("UPDATE jobs SET state='completed'")
    with scope(),pytest.raises(ValueError,match='Authenticated active'):
        server.infer('markers',tmp_path/'nonexistent-source.wav')


@pytest.mark.parametrize('uid',[0,-1,True,None,'1'])
def test_invalid_global_owner_never_creates_queue_job(env,uid):
    with pytest.raises(ValueError,match='Authenticated AI execution owner'):
        execution.execute(uid,'markers',lambda _:pytest.fail('invalid owner dispatched'))
    assert queue.list_jobs()==[]


def test_pre_cancelled_process_does_not_execute_actual_child(tmp_path):
    from app.ai_metering_agent import run_metered_process
    marker=tmp_path/'executed'
    code='from pathlib import Path;Path('+repr(str(marker))+').write_text("executed")'
    with pytest.raises(RuntimeError,match='cancelled before execution'):
        run_metered_process([sys.executable,'-c',code],cwd=str(tmp_path),cancel_check=lambda:True)
    assert not marker.exists()


def test_cancellation_probe_failure_does_not_spawn_child(tmp_path):
    from app.ai_metering_agent import run_metered_process
    marker=tmp_path/'executed'
    def broken():raise RuntimeError('owner heartbeat lost')
    with pytest.raises(RuntimeError,match='owner heartbeat lost'):
        run_metered_process([sys.executable,'-c','from pathlib import Path;Path('+repr(str(marker))+').touch()'],
                            cwd=str(tmp_path),cancel_check=broken)
    assert not marker.exists()


def test_native_fallback_pre_cancel_never_spawns(running,tmp_path,monkeypatch):
    from app import studio_compute,ai_worker_registry
    worker=tmp_path/'worker.py';worker.write_text('raise RuntimeError("must not run")')
    monkeypatch.setenv('MTA_NATIVE_SINGLE_USER','true')
    monkeypatch.delattr(os,'wait4',raising=False)
    monkeypatch.setattr(ai_worker_registry,'resolve_worker',lambda _:worker)
    monkeypatch.setattr(ai_worker_registry,'worker_python',lambda _:sys.executable)
    called=[]
    monkeypatch.setattr(studio_compute.subprocess,'Popen',lambda *a,**k:called.append(True))
    with pytest.raises(RuntimeError,match='cancelled before local worker'):
        studio_compute._compute(0,'vocal-harmony',{},cancelled=lambda:True)
    assert not called


@pytest.fixture
def ffmpeg_probe(tmp_path,monkeypatch):
    """An actual child executable; no mocked process/kill/wait implementation."""
    executable=tmp_path/'ffmpeg';marker=tmp_path/'converter-pid'
    monkeypatch.setenv('PATH',str(tmp_path)+os.pathsep+os.environ.get('PATH',''))
    def install(body):
        executable.write_text('#!'+sys.executable+'\nfrom pathlib import Path\nimport sys,os,time\n'+body)
        executable.chmod(0o700)
    return install,marker


def test_server_conversion_cancellation_reaps_child_and_never_enters_model(running,ffmpeg_probe,tmp_path,monkeypatch):
    from app import ai_server_execution as server,ai_metering_agent as agent
    install,marker=ffmpeg_probe
    install('Path('+repr(str(marker))+').write_text(str(os.getpid()))\nwhile True: time.sleep(.05)\n')
    monkeypatch.setattr(agent,'execute_registered_worker',lambda *a,**k:pytest.fail('cancelled preparation started inference'))
    with scope(),pytest.raises(RuntimeError,match='cancelled during execution'):
        server.infer('markers',tmp_path/'input.wav',cancel_check=marker.exists)
    assert marker.exists()
    with pytest.raises(ProcessLookupError):os.kill(int(marker.read_text()),0)
    with auth.db() as c:assert c.execute('SELECT count(*) FROM ai_compute_jobs').fetchone()[0]==0


@pytest.mark.parametrize('case',['cancelled','license_denied','engine_override'])
def test_server_rejects_before_source_process(running,ffmpeg_probe,tmp_path,case):
    from app import ai_server_execution as server
    install,marker=ffmpeg_probe
    install('Path('+repr(str(marker))+').touch()\n')
    with scope(),pytest.raises((RuntimeError,ValueError)):
        server.infer('unreviewed-engine' if case=='license_denied' else 'markers',tmp_path/'input.wav',
                     {'kind':'demucs'} if case=='engine_override' else {},cancel_check=lambda:case=='cancelled')
    assert not marker.exists()


@pytest.mark.parametrize('case',['failed','oversized','empty'])
def test_failed_or_unbounded_source_conversion_never_dispatches(running,ffmpeg_probe,tmp_path,monkeypatch,case):
    from app import ai_server_execution as server,ai_metering_agent as agent,ai_payload_limits as limits
    install,_=ffmpeg_probe
    monkeypatch.setattr(limits,'MAX_SOURCE_BYTES',64)
    install('sys.exit(2)\n' if case=='failed' else 'Path(sys.argv[-1]).write_bytes(b"x"*'+('80' if case=='oversized' else '0')+')\n')
    monkeypatch.setattr(agent,'execute_registered_worker',lambda *a,**k:pytest.fail('invalid source entered model'))
    with scope(),pytest.raises((RuntimeError,ValueError)):
        server.infer('markers',tmp_path/'input.wav')
    with auth.db() as c:assert c.execute('SELECT count(*) FROM ai_compute_jobs').fetchone()[0]==0


def test_source_preparation_uses_one_remaining_budget_and_preserves_bound_identity(running,ffmpeg_probe,tmp_path,monkeypatch):
    from app import ai_server_execution as server,ai_metering_agent as agent
    install,_=ffmpeg_probe
    install('Path(sys.argv[-1]).write_bytes(b"prepared")\n')
    calls=[]
    def worker(uid,kind,plan,**kwargs):
        calls.append((uid,kind,kwargs))
        raise RuntimeError('test stops at real worker admission boundary')
    monkeypatch.setattr(agent,'execute_registered_worker',worker)
    with scope(),pytest.raises(RuntimeError,match='test stops at real worker'):
        server.infer('markers',tmp_path/'input.wav',{'inference_timeout_seconds':60})
    assert len(calls)==1 and calls[0][:2]==(running,'markers')
    assert 1<=calls[0][2]['timeout_seconds']<60
    assert calls[0][2]['source_wav']==b'prepared'


def test_independent_process_cannot_reuse_live_parent_scheduler_identity(running):
    code='''from app.ai_global_execution import current_job,active_owner
current_job.set('active-owner')
try: active_owner()
except ValueError: print('blocked')
else: raise RuntimeError('foreign supervisor admitted')
'''
    result=subprocess.run([sys.executable,'-c',code],env={**os.environ,'MTA_AI_JOB_STATE_DIR':str(queue._ROOT)},
                          capture_output=True,text=True,timeout=10,check=True)
    assert result.stdout.strip()=='blocked'
    with queue._db() as c:
        assert c.execute('SELECT runner_pid FROM jobs WHERE job_id=?',('active-owner',)).fetchone()[0]==os.getpid()


@pytest.mark.parametrize('mode',['local','pull'])
def test_inner_dispatch_rechecks_owner_after_outer_admission(running,monkeypatch,mode):
    from app import ai_metering_agent as agent,ai_pull_coordinator as pull
    routed=[]
    monkeypatch.setattr(pull,'mode',lambda:routed.append(True) or mode)
    def next_stage(_):
        with queue._db() as c:c.execute('UPDATE jobs SET actor_user_id=actor_user_id+1')
        return agent._execute_registered_worker(running,'markers',{})
    with scope(),pytest.raises(ValueError,match='owner mismatch'):
        execution.execute(running,'markers',next_stage)
    assert not routed
