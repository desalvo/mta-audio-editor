"""Authenticated immutable reviewed checkpoint contract, not hostile-host/TEE proof."""
import base64
import copy
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import wave

import numpy as np
import pytest

from app import ai_model_attestation as att, ai_pull_coordinator as central, auth
from app.model_license_policy import LicenseDenied, authorize_remote_execution
from app.regime_operation_fence import FenceBlocked
from test_r208_unified_adapter_billing_e2e import operator as operator  # noqa: F401
from test_r210_pull_coordinator import authority as authority, economic, task, outcome  # noqa: F401
from test_r210_pull_lifecycle import api as api  # noqa: F401
from test_r210_pull_transport import https as https, cli  # noqa: F401

KIND='audio-to-midi-basic-pitch'


@pytest.fixture
def reviewed(authority,monkeypatch):
    monkeypatch.setenv('MTA_PULL_MODEL_ATTESTATION',att.VERIFIED_MODE)
    node=central.register('reviewed-checkpoint-node',[KIND])
    monkeypatch.setenv('MTA_AI_WORKER_AUDIO_TO_MIDI_BASIC_PITCH_EXECUTABLE',str(Path(__file__).resolve().parents[1]/'app/ai_studio_adapter.py'))
    monkeypatch.setenv('MTA_AI_WORKER_AUDIO_TO_MIDI_BASIC_PITCH_PYTHON',os.getenv('MTA_STUDIO_PYTHON',sys.executable))
    return authority,node


def sound():
    stream=io.BytesIO();rate=44100;t=np.arange(rate*2)/rate
    with wave.open(stream,'wb') as f:
        f.setnchannels(1);f.setsampwidth(2);f.setframerate(rate)
        f.writeframes((np.sin(2*np.pi*440*t)*.2*32767).astype('<i2').tobytes())
    return stream.getvalue()


def admit(reviewed):
    authority,node=reviewed
    job=central.enqueue(authority[0],KIND,{},source_wav=sound(),timeout_seconds=240)
    assignment=central.assignment(node['credential'],'a'*32)
    return node,job,assignment


def receipt(assignment):
    required=assignment['model_requirement']
    return {'schema':att.VERIFIED_SCHEMA,'context':att.context(assignment),'pid':123,
            'model_sha256':required['model_sha256'],'rights_sha256':required['rights_sha256'],
            'runtime':copy.deepcopy(att.RIGHTS['runtime'])}


def test_contract_binds_rights_loader_plan_and_original_epoch_before_dispatch(reviewed):
    node,job,assignment=admit(reviewed);r=assignment['model_requirement']
    assert r['schema']==att.VERIFIED_SCHEMA and r['rights']['license']=='Apache-2.0'
    assert set(r['sources'])=={'ai_studio_adapter.py','ai_model_bytes.py','ai_model_attestation.py'}
    assert r['epoch']=={'regime':'NON_COMMERCIAL','revision':0}
    assert receipt(assignment)['context']['plan_sha256']==hashlib.sha256(b'{}').hexdigest()
    with auth.db() as c:
        assert json.loads(c.execute('SELECT requirement_json FROM ai_pull_model_requirements WHERE job_id=?',(job,)).fetchone()[0])==r
    assert central.assignment(node['credential'],'a'*32)==assignment


@pytest.mark.parametrize('field',['rights','runtime','model','plan','epoch','source','policy','pid'])
def test_incomplete_or_substituted_checkpoint_evidence_cannot_publish_or_settle(reviewed,field):
    node,job,assignment=admit(reviewed);r=receipt(assignment)
    if field=='rights':r['rights_sha256']='0'*64
    elif field=='runtime':r['runtime']['onnxruntime']='unreviewed'
    elif field=='model':r['model_sha256']='0'*64
    elif field=='plan':r['context']['plan_sha256']='0'*64
    elif field=='epoch':r['context']['contract']['epoch']['revision']=True
    elif field=='source':r['context']['source_sha256']='0'*64
    elif field=='policy':r['context']['policy']['policy_sha256']='0'*64
    else:r['pid']=True
    with pytest.raises(ValueError):
        central.complete(node['credential'],job,assignment['instance'],assignment['nonce'],outcome()|{'model_receipt':r})
    assert economic(job)==('running','running','open') and task(job)['state']=='dispatched'


def test_failed_measured_execution_also_requires_its_original_load_rights_receipt(reviewed):
    node,job,a=admit(reviewed)
    failed={'status':'failed','cpu_seconds':.2,'media_type':None,'result_b64':''}
    with pytest.raises(ValueError):central.complete(node['credential'],job,a['instance'],a['nonce'],failed)
    assert economic(job)==('running','running','open')
    central.complete(node['credential'],job,a['instance'],a['nonce'],failed|{'model_receipt':receipt(a)})
    assert economic(job)==('failed','finished','closed')


def test_revoked_contract_never_rebinds_an_original_dispatched_job(reviewed,monkeypatch):
    node,job,a=admit(reviewed)
    monkeypatch.setenv('MTA_PULL_MODEL_ATTESTATION','off')
    with pytest.raises(FenceBlocked):central.heartbeat(node['credential'],job,a['instance'],a['nonce'])
    assert economic(job)==('running','running','open')


def test_missing_original_requirement_never_downgrades_to_unattested_completion(reviewed):
    node,job,a=admit(reviewed)
    with auth.db() as c:
        c.execute('DROP TRIGGER ai_pull_model_requirement_delete')
        c.execute('DELETE FROM ai_pull_model_requirements WHERE job_id=?',(job,))
    with pytest.raises(FenceBlocked,match='requirement missing'):
        central.complete(node['credential'],job,a['instance'],a['nonce'],outcome())
    assert economic(job)==('running','running','open')


@pytest.mark.parametrize('kind',sorted(__import__('app.ai_worker_registry',fromlist=['registered_kinds']).registered_kinds()-{KIND}))
def test_mode_flag_does_not_authorize_an_unreviewed_checkpoint(reviewed,kind):
    authority,_=reviewed
    with auth.db() as c:before=c.execute('SELECT COUNT(*) FROM ai_compute_jobs').fetchone()[0]
    with pytest.raises(LicenseDenied):central.enqueue(authority[0],kind,{},source_wav=sound())
    with auth.db() as c:assert c.execute('SELECT COUNT(*) FROM ai_compute_jobs').fetchone()[0]==before


@pytest.mark.skipif(not os.getenv('MTA_STUDIO_PYTHON'),reason='Explicit installed reviewed model/runtime required')
@pytest.mark.parametrize('regime',['NON_COMMERCIAL','COMMERCIAL'])
@pytest.mark.parametrize('lost',[False,True])
def test_real_checkpoint_independent_worker_https_rights_receipt_and_original_replay(reviewed,https,monkeypatch,regime,lost):
    authority,node=reviewed
    if regime=='COMMERCIAL':
        # Provision the initial empty authority before admission, not a cutover.
        (auth.data_root()/'service-regime.json').write_text('{"regime":"COMMERCIAL","revision":0}')
        with auth.db() as c:
            from app.regime_operation_fence import initialize
            initialize(c,initial_regime='COMMERCIAL')
    with pytest.raises(LicenseDenied):
        authorize_remote_execution(KIND,{})
    job=central.enqueue(authority[0],KIND,{},source_wav=sound(),timeout_seconds=240)
    if lost:https['drops']['complete']=1
    config=cli(authority,https,'reviewed-real-node',credential=node['credential'])
    result=subprocess.run(config[0],env=config[1],capture_output=True,text=True,timeout=180)
    assert result.returncode==(1 if lost else 0),(result.stdout,result.stderr)
    assert economic(job)==('done','finished','closed'),result.stderr
    proof=json.loads(task(job)['completion_json']);r=proof['model_receipt']
    assert r['schema']==att.VERIFIED_SCHEMA and r['context']['contract']['epoch']['regime']==regime
    assert r['runtime']==att.RIGHTS['runtime'] and r['model_sha256']==r['context']['contract']['model_sha256']
    assert proof['cpu_seconds']>0 and proof['media_type']=='application/zip'
    assert r['context']['source_sha256']==hashlib.sha256(sound()).hexdigest()
    assert base64.b64encode(task(job)['result']).startswith(b'UEs')
    import zipfile
    with zipfile.ZipFile(io.BytesIO(task(job)['result'])) as archive:
        music=json.loads(archive.read('music.json'))
    assert any(note['pitch']==69 for part in music['parts'] for note in part['notes'])
    frozen=task(job)['completion_json'];again=subprocess.run(config[0],env=config[1],capture_output=True,text=True,timeout=30)
    assert again.returncode==0 and task(job)['completion_json']==frozen
    assert not list(config[2].rglob('*.sqlite*'))
