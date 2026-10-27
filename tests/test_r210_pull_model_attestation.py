"""Authenticated assignment/ledger/receipt protocol; synthetic receipts != real models."""
from dataclasses import asdict
import hashlib
import json
import sqlite3
from unittest.mock import Mock

import pytest
from app.regime_operation_fence import FenceBlocked
from app import ai_pull_coordinator as central, ai_pull_worker as worker
from app import ai_model_attestation as attestation, model_license_policy as rights
from test_r208_unified_adapter_billing_e2e import operator as operator, source_audio  # noqa: F401
from test_r210_pull_transport import https as https  # noqa: F401
from test_r210_pull_lifecycle import api as api  # noqa: F401
from test_r210_pull_coordinator import authority as authority, task, economic, outcome, DirectClient  # noqa: F401

KIND='audio-to-midi-basic-pitch'


def admit(authority,monkeypatch):
    monkeypatch.setenv('MTA_PULL_MODEL_ATTESTATION','basic-pitch-v1')
    node=central.register('attested-node',[KIND])
    job=central.enqueue(authority[0],KIND,{},source_wav=source_audio())
    assignment=central.assignment(node['credential'],'a'*32)
    return node,job,assignment


def receipt(assignment):
    return {'schema':attestation.SCHEMA,'context':attestation.context(assignment),'pid':42,
            'model_sha256':assignment['model_requirement']['model_sha256']}


def test_requirement_frozen_at_admission_and_nonpilot_denied_before_ledger(authority,monkeypatch):
    node,job,assignment=admit(authority,monkeypatch)
    monkeypatch.setenv('MTA_PULL_MODEL_ATTESTATION','off')
    assert central.assignment(node['credential'],'a'*32)==assignment
    with central.transaction() as con:
        with pytest.raises(sqlite3.IntegrityError):con.execute('UPDATE ai_pull_model_requirements SET requirement_json=? WHERE job_id=?',('{}',job))
        with pytest.raises(sqlite3.IntegrityError):con.execute('DELETE FROM ai_pull_model_requirements WHERE job_id=?',(job,))
    monkeypatch.setenv('MTA_PULL_MODEL_ATTESTATION','basic-pitch-v1')
    with central.transaction() as con:before=con.execute('SELECT COUNT(*) FROM ai_compute_jobs').fetchone()[0]
    with pytest.raises(ValueError,match='explicit Basic Pitch'):central.enqueue(authority[0],'whisper',{})
    with central.transaction() as con:assert con.execute('SELECT COUNT(*) FROM ai_compute_jobs').fetchone()[0]==before


@pytest.mark.parametrize('field',['missing','model','job','instance','nonce','policy','source','pid-bool','schema'])
def test_bad_loaded_receipt_never_freezes_settles_or_publishes(authority,monkeypatch,field):
    node,job,assignment=admit(authority,monkeypatch);proof=receipt(assignment)
    if field=='model':proof['model_sha256']='0'*64
    elif field in ['job','instance','nonce','source']:
        key={'job':'job_id','source':'source_sha256'}.get(field,field);proof['context'][key]='0'*len(proof['context'][key])
    elif field=='policy':proof['context']['policy']={**proof['context']['policy'],'policy_sha256':'0'*64}
    elif field=='pid-bool':proof['pid']=True
    elif field=='schema':proof['schema']='other'
    data=outcome()
    if field!='missing':data['model_receipt']=proof
    with pytest.raises(ValueError):central.complete(node['credential'],job,assignment['instance'],assignment['nonce'],data)
    assert task(job)['state']=='dispatched'
    assert economic(job)==('running','running','open')


def test_valid_authenticated_receipt_frozen_with_result_and_replay_conflict_denied(authority,monkeypatch):
    node,job,assignment=admit(authority,monkeypatch)
    data=outcome()|{'model_receipt':receipt(assignment)}
    args=(node['credential'],job,assignment['instance'],assignment['nonce'])
    assert central.complete(*args,data)['acknowledged']
    assert economic(job)==('done','finished','closed')
    frozen=json.loads(task(job)['completion_json'])
    assert frozen['model_receipt']==data['model_receipt']
    assert frozen['result_sha256']==hashlib.sha256(source_audio()).hexdigest()
    assert central.complete(*args,data)['acknowledged']
    changed={**data,'model_receipt':{**data['model_receipt'],'pid':43}}
    with pytest.raises(FenceBlocked):central.complete(*args,changed)


def test_wrong_authenticated_node_cannot_submit_receipt(authority,monkeypatch):
    _,job,assignment=admit(authority,monkeypatch)
    other=central.register('foreign-node',[KIND])
    with pytest.raises(FenceBlocked):central.complete(other['credential'],job,assignment['instance'],assignment['nonce'],outcome()|{'model_receipt':receipt(assignment)})
    assert task(job)['state']=='dispatched'


def test_opaque_adapter_refused_before_process(authority,monkeypatch):
    node,job,assignment=admit(authority,monkeypatch)
    client=DirectClient(node['credential']);folder=authority[2]/'attested-state';folder.mkdir(mode=0o700)
    worker._write(folder/'active.json',{'binding':client.binding,'phase':'claimed','instance':assignment['instance'],'task':assignment})
    monkeypatch.setenv('MTA_AI_WORKER_AUDIO_TO_MIDI_BASIC_PITCH_EXECUTABLE',str(authority[2]/'fixed_worker.py'))
    assert worker.run_once(DirectClient(node['credential']),authority[2]/'attested-state')
    assert economic(job)==('failed','finished','closed')
    assert not (authority[2]/'execution-count').exists()


def test_real_receipt_writer_is_exclusive_and_bound_to_actual_pid(tmp_path,monkeypatch):
    import os
    data=b'synthetic model bytes'
    assignment={'job_id':'a'*32,'kind':KIND,'instance':'b'*32,'nonce':'c'*64,'source_sha256':'d'*64,
                'policy':asdict(rights.Decision('basic-pitch','cost_recovery','https://example.test','e'*64))}
    path=tmp_path/'receipt.json'
    monkeypatch.setenv(attestation.CONTEXT,central.encode(attestation.context(assignment)))
    monkeypatch.setenv(attestation.RECEIPT,str(path))
    attestation.record_loaded(data)
    proof=central.decode(path.read_bytes());expected={'model_sha256':hashlib.sha256(data).hexdigest()}
    assert attestation.validate(proof,expected,assignment,pid=os.getpid())==proof
    with pytest.raises(ValueError):attestation.validate(proof,expected,assignment,pid=os.getpid()+1)
    with pytest.raises(FileExistsError):attestation.record_loaded(data)


def test_record_is_not_emitted_if_onnx_constructor_fails(tmp_path,monkeypatch):
    from types import SimpleNamespace
    import sys
    from app import ai_studio_adapter as adapter
    path=tmp_path/'must-not-exist'
    monkeypatch.setenv(attestation.RECEIPT,str(path));monkeypatch.setenv(attestation.CONTEXT,'{}')
    monkeypatch.setattr(adapter,'model_bytes',lambda:b'synthetic')
    monkeypatch.setitem(sys.modules,'soundfile',SimpleNamespace(info=lambda _:SimpleNamespace(channels=1,duration=1,samplerate=44100)))
    monkeypatch.setitem(sys.modules,'onnxruntime',SimpleNamespace(SessionOptions=SimpleNamespace,
        disable_telemetry_events=lambda:None,InferenceSession=Mock(side_effect=RuntimeError('load failed'))))
    class Model:MODEL_TYPES=SimpleNamespace(ONNX='onnx')
    monkeypatch.setitem(sys.modules,'basic_pitch',SimpleNamespace())
    monkeypatch.setitem(sys.modules,'basic_pitch.inference',SimpleNamespace(Model=Model,predict=Mock()))
    with pytest.raises(RuntimeError,match='load failed'):adapter.transcribe('source.wav',{})
    assert not path.exists()


def test_https_attested_completion_lost_ack_recovers_exact_receipt_without_reexecution(authority,https,monkeypatch):
    node,job,assignment=admit(authority,monkeypatch)
    client=worker.WorkerClient(https['url'],node['credential'],ca_file=https['ca_file'])
    assert client.call('claim',{'instance':assignment['instance']})['task']==assignment
    data=outcome()|{'model_receipt':receipt(assignment)}
    body={'instance':assignment['instance'],'nonce':assignment['nonce'],'outcome':data}
    https['drops']['complete']=1
    with pytest.raises(OSError):client.call('complete',body,job=job)
    assert economic(job)==('done','finished','closed')
    assert client.call('complete',body,job=job)=={'job_id':job,'acknowledged':True}
    central.control(node['node_id'],revoke=True)
    with pytest.raises(worker.WorkerHTTP) as error:client.call('complete',body,job=job)
    assert error.value.status==401


def test_receipt_pid_matches_reaped_process_before_output_is_accepted(tmp_path,monkeypatch):
    import sys
    from app.ai_metering_agent import run_metered_process
    path=tmp_path/'receipt.json';raw=b'synthetic loaded fixture'
    assignment={'job_id':'a'*32,'kind':KIND,'instance':'b'*32,'nonce':'c'*64,'source_sha256':'d'*64,
                'policy':asdict(rights.Decision('basic-pitch','cost_recovery','https://example.test','e'*64))}
    env=__import__('os').environ.copy();env.update({attestation.CONTEXT:central.encode(attestation.context(assignment)),attestation.RECEIPT:str(path)})
    result=run_metered_process([sys.executable,'-c','from app.ai_model_attestation import record_loaded;record_loaded('+repr(raw)+')'],cwd=str(__import__('pathlib').Path(__file__).resolve().parents[1]),env=env,timeout_seconds=10)
    assert result.isolated and result.exit_code==0 and result.pid>0
    proof=central.decode(path.read_bytes())
    assert attestation.validate(proof,{'model_sha256':hashlib.sha256(raw).hexdigest()},assignment,pid=result.pid)==proof


@pytest.mark.parametrize('receipt_state',['matching','missing','foreign-pid'])
def test_worker_receipt_gate_and_durable_completion_with_explicit_process_double(authority,monkeypatch,receipt_state):
    import os
    from pathlib import Path
    from app import ai_metering_agent,ai_studio_adapter
    raw=b'synthetic model fixture'
    monkeypatch.setattr(ai_studio_adapter,'MODEL_SHA256',hashlib.sha256(raw).hexdigest())
    node,job,assignment=admit(authority,monkeypatch)
    adapter=Path(worker.__file__).with_name('ai_studio_adapter.py')
    monkeypatch.setenv('MTA_AI_WORKER_AUDIO_TO_MIDI_BASIC_PITCH_EXECUTABLE',str(adapter))
    client=DirectClient(node['credential']);folder=authority[2]/'receipt-process-double';folder.mkdir(mode=0o700)
    worker._write(folder/'active.json',{'binding':client.binding,'phase':'claimed','instance':assignment['instance'],'task':assignment})
    def process(argv,*,cwd,env,**kwargs):
        assert argv[1]==str(adapter)
        # Deliberate process double: this tests supervisor receipt validation,
        # not actual model loading (covered by a separate target prerequisite).
        with monkeypatch.context() as context:
            context.setenv(attestation.CONTEXT,env[attestation.CONTEXT]);context.setenv(attestation.RECEIPT,env[attestation.RECEIPT])
            if receipt_state!='missing':attestation.record_loaded(raw)
        model=Path(cwd)/'music.json';model.write_text('{"parts":[],"warnings":[]}')
        from app.ai_unified_adapter import _artifacts
        _artifacts(Path(cwd),[(model,'application/json')])
        return ai_metering_agent.Measurement(0,.1,{'cpu_seconds':.1},'worker',True,pid=os.getpid()+(1 if receipt_state=='foreign-pid' else 0))
    monkeypatch.setattr(ai_metering_agent,'run_metered_process',process)
    assert worker.run_once(client,folder)
    assert economic(job)==(('done','finished','closed') if receipt_state=='matching' else ('failed','finished','closed'))
    proof=json.loads(task(job)['completion_json'])
    assert ('model_receipt' in proof)==(receipt_state=='matching')
    assert json.loads((folder/'active.json').read_text())['phase']=='done'
    assert not worker.run_once(client,folder)


def test_revoked_rights_before_freeze_hold_original_assignment(authority,monkeypatch):
    node,job,assignment=admit(authority,monkeypatch)
    rights.configure('basic-pitch',{'mode':'disabled','acknowledge_responsibility':True,
        'evidence_url':'https://example.test/revocation','reason':'Synthetic fixture revocation before completion',
        'free_access_confirmed':False},authority[0])
    with pytest.raises(rights.LicenseDenied):
        central.complete(node['credential'],job,assignment['instance'],assignment['nonce'],outcome()|{'model_receipt':receipt(assignment)})
    assert task(job)['state']=='dispatched' and economic(job)==('running','running','open')


def test_attested_retention_erases_receipt_but_preserves_exact_lost_ack(authority,monkeypatch):
    node,job,assignment=admit(authority,monkeypatch)
    data=outcome()|{'model_receipt':receipt(assignment)}
    args=(node['credential'],job,assignment['instance'],assignment['nonce'])
    central.complete(*args,data)
    with central.transaction() as con:con.execute('UPDATE ai_pull_tasks SET completed_at=1 WHERE job_id=?',(job,))
    assert central.maintenance()['expired_artifacts']==1
    with central.transaction() as con:
        assert not con.execute('SELECT 1 FROM ai_pull_tasks WHERE job_id=?',(job,)).fetchone()
        assert not con.execute('SELECT 1 FROM ai_pull_model_requirements WHERE job_id=?',(job,)).fetchone()
    assert central.complete(*args,data)['acknowledged']
    with pytest.raises(FenceBlocked):central.complete(*args,data|{'model_receipt':{**data['model_receipt'],'pid':43}})


def test_receipt_writer_runs_without_site_packages_or_server_imports(tmp_path):
    import os,sys,subprocess
    from pathlib import Path
    path=tmp_path/'minimal-receipt.json'
    context={'job_id':'a'*32,'kind':KIND,'instance':'b'*32,'nonce':'c'*64,'source_sha256':'d'*64,'policy':{}}
    env={**os.environ,attestation.CONTEXT:central.encode(context),attestation.RECEIPT:str(path)}
    code="import sys;from app.ai_model_attestation import record_loaded;record_loaded(b'fixture');assert 'app.auth' not in sys.modules;assert 'fastapi' not in sys.modules"
    subprocess.run([sys.executable,'-S','-c',code],cwd=str(Path(__file__).resolve().parents[1]),env=env,check=True,capture_output=True,timeout=10)
    assert central.decode(path.read_bytes())['model_sha256']==hashlib.sha256(b'fixture').hexdigest()


def test_pilot_availability_matches_actual_new_admission(authority,monkeypatch):
    central.register('pilot-capability',[KIND])
    monkeypatch.setenv('MTA_PULL_MODEL_ATTESTATION','basic-pitch-v1')
    available=central.available()
    assert available[KIND] is True and available['whisper'] is False
    monkeypatch.setenv('MTA_PULL_MODEL_ATTESTATION','off')
    assert central.available()['whisper'] is True
    monkeypatch.setenv('MTA_PULL_MODEL_ATTESTATION','invalid')
    with pytest.raises(ValueError):central.available()
