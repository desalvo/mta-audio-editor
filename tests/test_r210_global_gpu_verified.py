"""Software proof/settlement gates. Synthetic traces are NOT hardware certification."""
import copy
import json
import time
from pathlib import Path

import pytest
from app import ai_gpu_verified as gpu


def trace(work=True):
    events=[]
    for label,start in [('BEFORE',10),('AFTER',1000)]:
        events.append({'name':'MTA_GPU_CONTROL_'+label,'ph':'X','ts':start,'dur':100,'pid':7,'tid':8})
    jobs=[(1,20,30,10),(2,1010,1020,10)]
    if work:jobs += [(3,200,250,100),(4,300,300,100)]
    for correlation,launch,start,duration in jobs:
        events.append({'name':'hipLaunchKernel','ph':'X','cat':'cuda_runtime','ts':launch,'dur':1,'pid':7,'tid':8,'args':{'correlation':correlation}})
        events.append({'name':'kernel','ph':'X','cat':'kernel','ts':start,'dur':duration,'pid':0,'tid':1,'args':{'correlation':correlation,'device':0}})
    return {'traceEvents':events}


@pytest.fixture
def certificate(tmp_path,monkeypatch):
    root=tmp_path/'gpu';root.mkdir(mode=0o700)
    key=root/'key';key.write_bytes(bytes(range(32)));key.chmod(0o600)
    monkeypatch.setenv('MTA_GPU_BILLING_ROOT',str(root))
    monkeypatch.setenv('MTA_DATA_DIR',str(tmp_path/'data'))
    policy={'id':'calibration1','enabled':True,'method':gpu.METHOD,'implementation':gpu.implementation(),
            'fingerprint':{'device':'synthetic-test-only'},'expires_at':time.time()+1000}
    gpu.atomic_json(root/'policy.json',gpu.seal(policy))
    return policy


def evidence(certificate,task='job1',identity='evidence1',start=10):
    value={'id':identity,'task_id':task,'calibration_id':certificate['id'],'method':gpu.METHOD,
      'implementation':gpu.implementation(),'fingerprint':certificate['fingerprint'],'complete':True,
      'recorded_at':time.time(),'capture_start':start,'capture_end':start+1,'gpu_seconds':.2,
      'wall_seconds':1,'kernel_count':2,'device_id':0,'trace_sha256':'a'*64}
    return gpu.seal(value)


def test_union_excludes_controls_and_overlapping_kernels():
    assert gpu.intervals(trace(),1)==pytest.approx((.00015,2,0))
    assert gpu.intervals(trace(False),1)==(0,0,0)


@pytest.mark.parametrize('change', ['missing_control','missing_dispatch','missing_kernel','duplicate','graph','dropped','foreign_thread','unordered','multi_device','zero_control','nan'])
def test_incomplete_or_unattributed_trace_is_rejected(change):
    value=trace();events=value['traceEvents']
    if change=='missing_control':events.pop(0)
    elif change=='missing_dispatch':events.pop(2)
    elif change=='missing_kernel':events.pop(3)
    elif change=='duplicate':events.append(copy.deepcopy(events[-1]))
    elif change=='graph':events.append({'name':'hipGraphLaunch'})
    elif change=='dropped':value['dropped_events']=1
    elif change=='foreign_thread':events[2]['tid']=9
    elif change=='unordered':events[1]['ts']=0
    elif change=='multi_device':events[-1]['args']['device']=1
    elif change=='zero_control':events[3]['dur']=0
    else:events[2]['ts']=float('nan')
    with pytest.raises(ValueError):gpu.intervals(value,1)


def test_policy_signature_expiry_implementation_and_permissions(certificate):
    assert gpu.readiness()['ready']
    for field,new in [('expires_at',0),('implementation','changed'),('enabled',False)]:
        changed={**certificate,field:new};gpu.atomic_json(gpu.root()/'policy.json',gpu.seal(changed))
        assert not gpu.readiness()['ready']
    gpu.atomic_json(gpu.root()/'policy.json',gpu.seal(certificate))
    (gpu.root()/'key').chmod(0o644)
    assert not gpu.readiness()['ready']


def test_signed_evidence_settles_exactly_once_and_blocks_replay(certificate,tmp_path):
    folder=tmp_path/'report';folder.mkdir()
    report=evidence(certificate)
    gpu.append_report(folder,report,'job1')
    gpu.append_report(folder,report,'job1')
    assert gpu.consume_report('job1',folder,expected_segments=1)==.2
    assert gpu.consume_report('job1',folder,expected_segments=1)==.2
    gpu.require_evidence('job1',{'gpu_seconds':.2})
    with pytest.raises(ValueError):gpu.require_evidence('job1',{'gpu_seconds':.3})
    with pytest.raises(ValueError):gpu.consume_report('job2',folder,ace=True)
    with pytest.raises(ValueError):gpu.require_evidence('job1',{'gpu_seconds':.2,'gpu_energy_joules':0})


@pytest.mark.parametrize('field,value',[('complete',False),('recorded_at',0),('kernel_count',-1),('trace_sha256','bad'),('gpu_seconds',float('inf')),('device_id',True)])
def test_invalid_constituent_cannot_be_aggregated(certificate,tmp_path,field,value):
    record=evidence(certificate)['payload'];record[field]=value
    if field=='gpu_seconds':
        with pytest.raises(ValueError):gpu.seal(record)
        return
    folder=tmp_path/'report';folder.mkdir()
    gpu.append_report(folder,gpu.seal(record),'job1')
    with pytest.raises(ValueError):gpu.consume_report('job1',folder)


def test_segment_overlap_and_missing_singer_are_rejected(certificate,tmp_path):
    folder=tmp_path/'report';folder.mkdir()
    gpu.append_report(folder,evidence(certificate),'job1')
    with pytest.raises(ValueError):gpu.consume_report('job1',folder,expected_segments=2)
    gpu.append_report(folder,evidence(certificate,identity='evidence2',start=10.5),'job1')
    with pytest.raises(ValueError):gpu.consume_report('job1',folder)


def test_profiler_failure_does_not_retry_successful_inference(certificate,monkeypatch):
    import sys
    monkeypatch.setitem(sys.modules,'torch',object())
    monkeypatch.setattr(gpu,'fingerprint',lambda torch:certificate['fingerprint'])
    calls=[]
    def broken(torch,call):
        call()
        raise ValueError('Incomplete capture')
    monkeypatch.setattr(gpu,'capture',broken)
    assert gpu.measured('job1',lambda:calls.append(1) or 'audio',publish=lambda e:pytest.fail('Invalid evidence published'))=='audio'
    assert calls==[1]


def test_inference_exception_not_retried(certificate,monkeypatch):
    import sys
    monkeypatch.setitem(sys.modules,'torch',object())
    monkeypatch.setattr(gpu,'fingerprint',lambda torch:certificate['fingerprint'])
    monkeypatch.setattr(gpu,'capture',lambda torch,call:call())
    calls=[]
    def fail():
        calls.append(1)
        raise RuntimeError('inference failed')
    with pytest.raises(RuntimeError,match='inference failed'):gpu.measured('job1',fail,publish=lambda e:None)
    assert calls==[1]


def test_uncalibrated_status_cli_does_not_enable_billing(tmp_path,monkeypatch):
    import subprocess,sys
    monkeypatch.setenv('MTA_GPU_BILLING_ROOT',str(tmp_path/'absent'))
    result=subprocess.run([sys.executable,str(Path(__file__).parents[1]/'scripts/gpu_verified_billing.py'),'status'],capture_output=True,text=True)
    assert result.returncode==2 and json.loads(result.stdout)['ready'] is False
    assert not (tmp_path/'absent').exists()


def test_calibrated_kernel_usage_is_invoiced_once(certificate):
    from app import ai_billing as billing
    from app.auth import init_auth_db,db
    init_auth_db()
    with db() as con:
        con.execute("INSERT INTO users(username,email,password_hash,active,role,created_at,updated_at) VALUES('proofuser','proof@example.org','fake',1,'user',1,1)")
        user=con.execute("SELECT id FROM users WHERE username='proofuser'").fetchone()[0]
    billing.set_price('gpu_seconds',100,valid_from='2025-01-01')
    billing.set_price('cpu_seconds',10,valid_from='2025-01-01')
    job=billing.create_job(user,'ace-step',started_at=1760140800)
    with pytest.raises(ValueError):billing.finish_job(job,'done',{'gpu_seconds':.2},source='gpu-kernel-verified',finished_at=1760140810)
    gpu.persist(job,evidence(certificate,task=job),job)
    billing.finish_job_idempotent(job,'done',{'gpu_seconds':.2,'cpu_seconds':3},source='gpu-kernel-verified',finished_at=1760140810)
    billing.finish_job_idempotent(job,'done',{'gpu_seconds':.2,'cpu_seconds':3},source='gpu-kernel-verified',finished_at=1760140810)
    assert billing.close_period(user,'2025-10-11','2025-10-11')['total_micro']==50
    assert billing.close_period(user,'2025-10-11','2025-10-11')['total_micro']==50
