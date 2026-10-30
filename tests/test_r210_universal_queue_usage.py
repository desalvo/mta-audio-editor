"""Resource projection across all adapters, without changing ledger settlement."""
import json
import os
import sys
import pytest
from app import auth, ai_billing, ai_arranger_runtime as queue, ai_queue_admin
from app.ai_queue_usage import enrich, CpuProgress


@pytest.fixture
def ledger(tmp_path, monkeypatch):
    monkeypatch.setattr(auth, 'DATA_ROOT', tmp_path/'auth')
    monkeypatch.setattr(queue, '_ROOT', tmp_path/'queue')
    monkeypatch.setenv('MTA_ADMIN_PASSWORD', 'administrator-password')
    auth.init_auth_db()
    uid = auth.find_user('admin')['id']
    with auth.db() as con:
        ai_billing._init(con)
        con.execute('CREATE TABLE ai_verified_gpu_evidence(job_id TEXT PRIMARY KEY, seconds REAL)')
    with queue._db() as con:
        con.execute("INSERT INTO jobs(job_id,project_id,operation,state,rank,created_at,started_at,completed_at,phase,message,actor_user_id) VALUES('job','project','worker:stems','completed',1,1,1,2,'done','',?)", (uid,))
    return uid


def add(uid, *, ident='ledger', kind='demucs', source='cgroup', status='done', usage=None, evidence=None, queue_id='job'):
    with auth.db() as con:
        con.execute('INSERT INTO ai_compute_jobs(id,user_id,kind,status,started_at,usage_json,resource_source,queue_job_id) VALUES(?,?,?,?,?,?,?,?)',
                    (ident, uid, kind, status, 1, json.dumps(usage or {}), source, queue_id))
        if evidence is not None:
            con.execute('INSERT INTO ai_verified_gpu_evidence VALUES(?,?)', (ident, evidence))


@pytest.mark.parametrize('kind', ['whisper','chords-ml','markers','demucs','sam-audio','backing-vocals','singer-separation','future-adapter'])
def test_historical_all_adapters_in_queue_and_admin(ledger, kind):
    add(ledger, kind=kind, source='gpu-kernel-verified', usage={'cpu_seconds':12.5,'gpu_seconds':3.25}, evidence=3.25)
    before = auth.db_path().read_bytes()
    for value in (queue.get('job'), ai_queue_admin.query()['jobs'][0]):
        assert value['cpu_seconds'] == 12.5
        assert value['gpu_seconds'] == 3.25
    # Administrative query may initialize its own tables; projection itself is read-only.
    before = auth.db_path().read_bytes()
    assert enrich({'actor_user_id':ledger,'job_id':'job'})['gpu_seconds'] == 3.25
    assert auth.db_path().read_bytes() == before


@pytest.mark.parametrize('source,evidence', [('worker',None),('cgroup',None),('unmetered',None),('gpu-kernel-verified',None),('gpu-kernel-verified',8)])
def test_unverified_gpu_never_promoted(ledger, source, evidence):
    add(ledger, source=source, usage={'cpu_seconds':2,'gpu_seconds':4}, evidence=evidence)
    result = queue.get('job')
    assert result['gpu_seconds'] is None
    assert result['cpu_seconds'] == (None if source=='unmetered' else 2)


def test_zero_distinct_from_missing_and_owner_isolation(ledger):
    add(ledger, usage={'cpu_seconds':0})
    result = queue.get('job')
    assert result['cpu_seconds'] == 0 and result['gpu_seconds'] is None
    assert enrich({'actor_user_id':ledger+1,'job_id':'job'}) == {'actor_user_id':ledger+1,'job_id':'job'}
    assert enrich({'actor_user_id':ledger,'job_id':'different'})['actor_username'] == 'admin'


def test_multiple_components_and_running_diagnostics(ledger):
    from app.ai_compute_diagnostics import store
    add(ledger, usage={'cpu_seconds':2})
    add(ledger, ident='stage2', status='running', usage={'cpu_seconds':999,'gpu_seconds':999})
    store('stage2', {'cpu_seconds_estimated':1.5,'gpu_seconds_estimated':.8})
    result = queue.get('job')
    assert result['cpu_seconds'] is None
    assert result['cpu_seconds_estimated'] == 3.5
    assert result['gpu_seconds'] is None and result['gpu_seconds_estimated'] == .8
    assert result['resource_metrics_partial']


def test_ace_verified_values_preserved(ledger):
    add(ledger, usage={'cpu_seconds':2})
    result = enrich({'actor_user_id':ledger,'job_id':'job','cpu_seconds':7,'gpu_seconds':5})
    assert result['cpu_seconds'] == 7 and result['gpu_seconds'] == 5


@pytest.mark.parametrize('bad', [float('nan'),float('inf'),-1,True,'2'])
def test_live_cpu_rejects_bad_values(tmp_path,bad):
    path=tmp_path/'progress.json'
    sampler=CpuProgress({'MTA_AI_PROGRESS_FILE':str(path)})
    sampler.publish(lambda:bad)
    assert not path.exists()


def test_live_cpu_preserves_progress_and_ace_backend(tmp_path):
    path=tmp_path/'progress.json'
    path.write_text(json.dumps({'phase':'inference','gpu_seconds_estimated':3}))
    sampler=CpuProgress({'MTA_AI_PROGRESS_FILE':str(path)})
    sampler.publish(lambda:2)
    sampler.publish(lambda:99)
    assert json.loads(path.read_text()) == {'phase':'inference','gpu_seconds_estimated':3,'cpu_seconds_estimated':2}
    CpuProgress({'MTA_AI_PROGRESS_FILE':str(path),'MTA_AI_SUPERVISOR_CPU_PROGRESS':'0'}).publish(lambda:99)
    assert json.loads(path.read_text())['cpu_seconds_estimated'] == 2


@pytest.mark.skipif(os.name!='posix' or not hasattr(os,'wait4'),reason='Unix process accounting')
def test_real_worker_live_and_final_cpu(tmp_path, monkeypatch):
    from app.ai_metering_agent import run_metered_process
    path=tmp_path/'progress.json'
    # The test sandbox may expose procfs from a different PID namespace.
    # Keep the real subprocess/wait4 accounting and inject only its live probe;
    # the procfs parser has a separate deterministic regression below.
    monkeypatch.setattr('app.ai_queue_usage.process_cpu',lambda pid:.125)
    measured=run_metered_process([sys.executable,'-c','import time; end=time.monotonic()+1.3\nwhile time.monotonic()<end: sum(range(1000))'], cwd=str(tmp_path),timeout_seconds=10,env={**os.environ,'MTA_AI_PROGRESS_FILE':str(path)})
    live=json.loads(path.read_text())['cpu_seconds_estimated']
    assert measured.exit_code == 0 and measured.isolated
    assert live > 0 and measured.usage['cpu_seconds'] > 0
    assert 'gpu_seconds' not in measured.usage


def test_process_cpu_uses_only_utime_and_stime(monkeypatch):
    from pathlib import Path
    from app.ai_queue_usage import process_cpu
    from app import linux_proc_view
    monkeypatch.setattr(linux_proc_view,'directory',lambda pid:Path('/proc')/str(pid))
    fields=['S']+['999']*10+['120','30']+['999']*20
    monkeypatch.setattr(Path,'read_text',lambda self:'123 (worker with ) name) '+' '.join(fields))
    monkeypatch.setattr(os,'sysconf',lambda name:100)
    assert process_cpu(123) == 1.5


def test_worker_checkpoint_keeps_cpu_and_gpu_together(ledger, tmp_path, monkeypatch):
    from app import ai_metering_agent as agent, ai_global_execution
    from app.ai_compute_diagnostics import read
    worker=tmp_path/'worker.py'
    worker.write_text('')
    monkeypatch.setattr('app.ai_worker_registry.resolve_worker',lambda kind:worker)
    monkeypatch.setattr('app.ai_worker_registry.worker_python',lambda kind:sys.executable)
    monkeypatch.setattr('app.ai_gpu_slot_accounting.slot_enabled_for_kind',lambda kind:False)
    monkeypatch.setattr('app.ai_gpu_verified.readiness',lambda:{'ready':False})
    monkeypatch.setattr('app.ai_torch_diagnostics.read_report',lambda folder,jid:{'gpu_seconds_estimated':3,'gpu_metrics_status':'profiled_kernels_diagnostic','gpu_metrics_source':'torch-profiler'})
    monkeypatch.setattr('app.ai_worker_artifacts.package_artifacts',lambda folder,**kw:(b'artifact','application/zip'))
    def measured(argv,**kw):
        from pathlib import Path
        Path(kw['env']['MTA_AI_PROGRESS_FILE']).write_text(json.dumps({'cpu_seconds_estimated':2,'phase':'inference'}))
        kw['cancel_check']()
        return agent.Measurement(0,1,{'cpu_seconds':2.5},'worker',True)
    monkeypatch.setattr(agent,'run_supervised_process',measured)
    monkeypatch.delenv('MTA_AI_CGROUP_PARENT',raising=False)
    # A historical completed row is not an execution permit. This live worker
    # fixture must acquire the same real scheduler identity as production.
    with queue._db() as c:
        c.execute("UPDATE jobs SET state='queued',completed_at=NULL,runner_pid=?,runner_identity=? WHERE job_id='job'",
                  (os.getpid(),queue._process_identity(os.getpid())))
    assert queue._claim('job')
    token=ai_global_execution.current_job.set('job')
    try:
        agent._execute_registered_worker(ledger,'whisper',{})
    finally:
        ai_global_execution.current_job.reset(token)
    with queue._db() as c:
        c.execute("UPDATE jobs SET state='completed',completed_at=2 WHERE job_id='job'")
    with auth.db() as con:
        diagnostics=list(read(con,ledger).values())
    assert diagnostics == [{'cpu_seconds_estimated':2,'gpu_seconds_estimated':3}]
    value=queue.get('job')
    assert value['cpu_seconds']==2.5 and value['resources_accounted']
    assert value['gpu_seconds']==3 and value['gpu_metrics_status']=='accounted'


def test_queue_ui_labels_missing_zero_and_diagnostic():
    import shutil
    import subprocess
    from pathlib import Path
    if not shutil.which('node'):
        pytest.skip('Node unavailable')
    source=(Path(__file__).parents[1]/'app/static/ai_jobs.js').read_text()
    metrics=next(line for line in source.splitlines() if line.startswith('function metrics('))
    code="const esc=String;const seconds=v=>v+'s';"+metrics+'''
    const assert=require('assert');
    assert(metrics({cpu_seconds:0}).includes('CPU 0s'));
    assert(metrics({}).includes('non disponibile'));
    assert(metrics({cpu_seconds_estimated:2,gpu_seconds_estimated:3}).includes('in elaborazione'));
    assert(metrics({cpu_seconds:2,gpu_seconds:3,resources_accounted:true}).includes('contabilizzato'));
    assert(!metrics({cpu_seconds:2,gpu_seconds:3,resources_accounted:true}).includes('verificata'));
    assert(metrics({cpu_seconds:2,resource_metrics_partial:true}).includes('in corso'));
    '''
    subprocess.run(['node','-e',code],check=True)


def test_live_sidecar_does_not_replace_multistage_sum(ledger):
    from app.ai_compute_diagnostics import store
    add(ledger,usage={'cpu_seconds':2})
    add(ledger,ident='stage2',status='running')
    store('stage2',{'cpu_seconds_estimated':1})
    path=queue._ROOT/'job.progress.json'
    path.write_text(json.dumps({'cpu_seconds_estimated':1}))
    value=enrich({'actor_user_id':ledger,'job_id':'job','state':'running'})
    assert queue._with_live_progress(value)['cpu_seconds_estimated']==3
