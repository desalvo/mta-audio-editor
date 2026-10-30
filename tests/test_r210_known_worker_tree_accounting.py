"""Fixed multi-process routes cannot gain wait4 isolation from missed samples."""
import json
import sys
import time
from pathlib import Path

import pytest
from app import ai_metering_agent as agent, ai_billing
from test_r208_unified_adapter_billing_e2e import operator as operator, source_audio  # noqa: F401

ROUTES=[('demucs',{'model':'htdemucs'}),('sam-audio',{'model':'sam-audio-small'}),
        ('singer-separation',{'model':'sam-audio-small'}),
        ('backing-vocals',{'model':'ffmpeg-center-side'}),
        ('backing-vocals',{}),('drumsep',{'model':'sam-audio-small'})]


@pytest.fixture(autouse=True)
def isolated_queue(tmp_path,monkeypatch):
    from app import ai_arranger_runtime as queue
    monkeypatch.setattr(queue,'_ROOT',tmp_path/'queue')
    original=queue.worker_thread;threads=[]
    def create(*args,**kwargs):
        thread=original(*args,**kwargs);threads.append(thread);return thread
    monkeypatch.setattr(queue,'worker_thread',create)
    with queue._MUTEX:prior=set(queue._LOCAL)
    yield
    deadline=time.monotonic()+5
    for thread in threads:thread.join(max(0,deadline-time.monotonic()))
    with queue._MUTEX:remaining=set(queue._LOCAL)-prior
    assert not remaining and all(not thread.is_alive() for thread in threads), 'Original worker thread must finish before queue path restoration'


@pytest.mark.parametrize('kind,plan',ROUTES)
@pytest.mark.parametrize('outcome',['complete','cancelled'])
def test_known_tree_retains_original_owner_even_when_wait4_samples_look_isolated(
        operator,monkeypatch,kind,plan,outcome):
    monkeypatch.delenv('MTA_AI_WORKER_'+kind.upper().replace('-','_')+'_EXECUTABLE')
    monkeypatch.setenv('MTA_AI_UNIFIED_WORKERS_ENABLED','true')
    monkeypatch.setenv('MTA_AI_WORKER_'+kind.upper().replace('-','_')+'_PYTHON',sys.executable)
    monkeypatch.setenv('MTA_LEAD_BACKING_DEFAULT_MODEL','ffmpeg-center-side')
    monkeypatch.delenv('MTA_LEAD_BACKING_COMMAND',raising=False)
    called=[]
    def measured(args,**kwargs):
        assert Path(args[1]).name=='ai_unified_adapter.py'
        called.append(args)
        measurement=agent.Measurement(0,.1,{'cpu_seconds':.05},'worker',True)
        if outcome=='cancelled':raise agent.WorkerInterrupted(measurement)
        return measurement
    monkeypatch.setattr(agent,'run_supervised_process',measured)
    monkeypatch.setattr('app.ai_worker_artifacts.package_artifacts',lambda *a,**kw:pytest.fail('Unverified tree published artifacts'))
    with pytest.raises(agent.WorkerUncertain) as error:
        agent.execute_registered_worker(operator,kind,plan,source_wav=source_audio())
    assert len(called)==1 and error.value.job_id
    with ai_billing.db() as c:
        row=c.execute('SELECT status,resource_source,usage_json FROM ai_compute_jobs WHERE id=?',(error.value.job_id,)).fetchone()
        assert tuple(row)[:2]==('running','unmetered') and json.loads(row['usage_json'])=={}
        claim=c.execute('SELECT state FROM regime_worker_claims WHERE operation_id=?',('job:ledger:'+error.value.job_id,)).fetchone()
        assert claim['state']=='running'


def test_known_tree_keeps_cgroup_runner_contract(operator,monkeypatch):
    """Synthetic cgroup result tests routing/settlement,not a real kernel proof."""
    monkeypatch.delenv('MTA_AI_WORKER_BACKING_VOCALS_EXECUTABLE')
    monkeypatch.setenv('MTA_AI_UNIFIED_WORKERS_ENABLED','true')
    monkeypatch.setenv('MTA_AI_WORKER_BACKING_VOCALS_PYTHON',sys.executable)
    monkeypatch.setenv('MTA_AI_CGROUP_PARENT','/synthetic-cgroup-fixture')
    monkeypatch.delenv('MTA_LEAD_BACKING_COMMAND',raising=False)
    monkeypatch.setattr(agent,'run_supervised_process',lambda *a,**kw:pytest.fail('Cgroup route fell back to wait4'))
    called=[]
    def grouped(args,**kwargs):
        called.append(kwargs['owner_receipt']['job_id'])
        Path(args[args.index('--output')+1]).write_bytes(source_audio())
        return agent.Measurement(0,.1,{'cpu_seconds':.05},'cgroup',True)
    monkeypatch.setattr('app.ai_cgroup_metering.run_cgroup_process',grouped)
    payload,metadata=agent.execute_registered_worker(operator,'backing-vocals',
        {'model':'ffmpeg-center-side'},source_wav=source_audio())
    assert payload[:4]==b'RIFF' and metadata['process_tree_metered']
    assert metadata['metering_source']=='cgroup' and called==[metadata['job_id']]
    with ai_billing.db() as c:
        row=c.execute('SELECT status,resource_source FROM ai_compute_jobs WHERE id=?',(metadata['job_id'],)).fetchone()
        assert tuple(row)==('done','cgroup')
