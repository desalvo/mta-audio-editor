"""Original decision binding across real child entry, local/native/pull parents."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from app import ai_execution_policy as binding, model_license_policy as rights
from app import transkun_runner as runner
from test_r208_unified_adapter_billing_e2e import operator as operator, source_audio  # noqa: F401
from test_r210_pull_coordinator import authority as authority, DirectClient, enqueue, economic  # noqa: F401


def test_transkun_loader_uses_verified_stream_after_path_replacement(tmp_path):
    path=tmp_path/'weights.pt';raw=b'synthetic safe weights';path.write_bytes(raw)
    class Tensor:pass
    state={'layer':Tensor()}
    def load(stream,**kw):
        path.write_bytes(b'replacement')
        assert stream.read()==raw
        assert kw=={'map_location':'cpu','weights_only':True}
        return {'state_dict':state}
    assert runner.load_state(SimpleNamespace(load=load,Tensor=Tensor),path,'cpu',hashlib.sha256(raw).hexdigest()) is state


def test_transkun_config_is_private_exact_copy_removed_after_parse(tmp_path):
    path=tmp_path/'config.py';raw=b'model = "fixture"';path.write_bytes(raw);seen=[]
    def parse(actual):
        path.write_bytes(b'replaced original config')
        actual=Path(actual);assert actual!=path and actual.read_bytes()==raw
        assert actual.stat().st_mode&0o777==0o400
        seen.append(actual);return {'Model':'synthetic'}
    assert runner.load_settings(SimpleNamespace(parseFromFile=parse),path,hashlib.sha256(raw).hexdigest())=={'Model':'synthetic'}
    assert not seen[0].exists()


@pytest.mark.parametrize('loader',['checkpoint','config'])
def test_transkun_tamper_rejected_before_deserializer_or_executable_configuration(tmp_path,loader):
    path=tmp_path/'asset';raw=b'original';path.write_bytes(b'tampered')
    load=Mock();digest=hashlib.sha256(raw).hexdigest()
    with pytest.raises(ValueError,match='integrity'):
        if loader=='checkpoint':runner.load_state(SimpleNamespace(load=load),path,'cpu',digest)
        else:runner.load_settings(SimpleNamespace(parseFromFile=load),path,digest)
    load.assert_not_called()


@pytest.mark.parametrize('mutation',['missing','kind','digest','review-type','duplicate','schema'])
def test_child_rejects_missing_changed_or_malformed_original_policy(tmp_path,monkeypatch,mutation):
    monkeypatch.setenv('MTA_DATA_DIR',str(tmp_path))
    decision=rights.evaluate('vocal-harmony',{})
    env=binding.admitted_env('vocal-harmony',decision)
    doc=json.loads(env[binding.KEY])
    if mutation=='kind':doc['kind']='whisper'
    elif mutation=='digest':doc['decision']['policy_sha256']='0'*64
    elif mutation=='review-type':doc['decision']['operator_review']=int(decision.operator_review)
    elif mutation=='schema':doc['schema']='other'
    raw=json.dumps(doc)
    if mutation=='duplicate':raw=raw[:-1]+',"kind":"vocal-harmony"}'
    if mutation=='missing':monkeypatch.delenv(binding.KEY,raising=False)
    else:monkeypatch.setenv(binding.KEY,raw)
    with pytest.raises(ValueError):binding.verify_plan({'kind':'vocal-harmony'})


def test_actual_child_entry_rejects_before_reading_score_or_loading_models(tmp_path,monkeypatch):
    monkeypatch.setenv('MTA_DATA_DIR',str(tmp_path/'data'))
    request=tmp_path/'request.json';request.write_text('{"kind":"vocal-harmony","source_score":"missing-score"}')
    cmd=[sys.executable,'app/ai_studio_adapter.py','--request',str(request),'--output',str(tmp_path/'preview.wav')]
    for envelope in [None,binding.admitted_env('whisper',rights.evaluate('whisper',{}))[binding.KEY]]:
        env=dict(os.environ);env.pop(binding.KEY,None)
        if envelope:env[binding.KEY]=envelope
        result=subprocess.run(cmd,env=env,capture_output=True,text=True,timeout=20)
        assert result.returncode!=0 and 'Original admitted worker' in result.stderr
        assert 'Unsafe score transport' not in result.stderr
    assert not (tmp_path/'preview.wav').exists()


def test_registered_parent_overwrites_inherited_policy_and_real_child_verifies(operator,tmp_path,monkeypatch):
    from app import ai_metering_agent
    root=Path(__file__).resolve().parents[1]
    driver=tmp_path/'policy_worker.py'
    driver.write_text('import sys\nsys.path.insert(0,'+repr(str(root))+')\nimport argparse,json,pathlib\nfrom app.ai_execution_policy import verify_plan\np=argparse.ArgumentParser();p.add_argument("--request");p.add_argument("--output");a=p.parse_args()\nverify_plan(json.loads(pathlib.Path(a.request).read_text()))\n'+(tmp_path/'fixed_adapter.py').read_text())
    driver.chmod(0o700)
    monkeypatch.setenv('MTA_AI_WORKER_WHISPER_EXECUTABLE',str(driver))
    monkeypatch.setenv(binding.KEY,'untrusted inherited policy')
    payload,meta=ai_metering_agent.execute_registered_worker(operator,'whisper',{},source_wav=source_audio())
    assert payload and meta['usage']['cpu_seconds']>0


def test_pull_parent_propagates_original_assignment_to_actual_child(authority,monkeypatch):
    from app import ai_pull_worker
    root=Path(__file__).resolve().parents[1];script=authority[2]/'fixed_worker.py'
    original=script.read_text()
    script.write_text('import sys\nsys.path.insert(0,'+repr(str(root))+')\nimport json,pathlib\nfrom app.ai_execution_policy import verify_plan\nverify_plan(json.loads(pathlib.Path(sys.argv[sys.argv.index("--request")+1]).read_text()))\n'+original)
    monkeypatch.setenv(binding.KEY,'untrusted inherited policy')
    job=enqueue(authority)
    assert ai_pull_worker.run_once(DirectClient(authority[1]['credential']),authority[2]/'policy-state')
    assert economic(job)==('done','finished','closed')
    assert (authority[2]/'execution-count').read_bytes()==b'1'


def test_native_parent_actual_studio_adapter_preserves_output_and_no_server_invoice(operator,monkeypatch):
    from app import studio_compute,auth
    from app.studio_score import Score
    from app.music_interchange import MusicResult,MusicPart
    from app.models import MidiNote
    monkeypatch.setenv('MTA_NATIVE_SINGLE_USER','true')
    monkeypatch.setenv(binding.KEY,'untrusted inherited policy')
    score=Score(music=MusicResult(parts=[MusicPart(id='melody',name='Melody',notes=[
        MidiNote(id='n',pitch=60,start_ms=0,duration_ms=500)])])).model_dump_json().encode()
    with auth.db() as con:before=con.execute('SELECT COUNT(*) FROM ai_compute_jobs').fetchone()[0]
    result,meta=studio_compute.compute(0,'vocal-harmony',{},score=score,timeout=20)
    assert result.parts and any(p.notes for p in result.parts)
    assert meta['billable'] is False and meta['usage']['cpu_seconds']>0
    with auth.db() as con:assert con.execute('SELECT COUNT(*) FROM ai_compute_jobs').fetchone()[0]==before


def test_registered_child_cannot_adopt_different_current_policy(operator,tmp_path,monkeypatch):
    from app import ai_metering_agent,auth
    from dataclasses import replace
    # Parent binds its original policy; actual trusted child independently
    # evaluates the current local policy rather than adopting the envelope.
    original=rights.evaluate
    monkeypatch.setattr(rights,'evaluate',lambda kind,plan:replace(original(kind,plan),policy_sha256='0'*64))
    root=Path(__file__).resolve().parents[1]
    driver=tmp_path/'guarded.py'
    driver.write_text('import sys,json,pathlib\nsys.path.insert(0,'+repr(str(root))+')\nfrom app.ai_execution_policy import verify_plan\nverify_plan(json.loads(pathlib.Path(sys.argv[sys.argv.index("--request")+1]).read_text()))\nraise RuntimeError("must not reach model")\n')
    driver.chmod(0o700);monkeypatch.setenv('MTA_AI_WORKER_WHISPER_EXECUTABLE',str(driver))
    with pytest.raises(RuntimeError):ai_metering_agent.execute_registered_worker(operator,'whisper',{},source_wav=source_audio())
    with auth.db() as con:
        row=con.execute('SELECT status FROM ai_compute_jobs ORDER BY rowid DESC LIMIT 1').fetchone()
        assert row[0]=='failed'
