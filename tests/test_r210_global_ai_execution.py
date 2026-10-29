"""Authenticated server admission and backend contracts, without model downloads."""
import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from app import ai_arranger_runtime as queue, ai_global_execution as execution


@pytest.fixture
def isolated_queue(tmp_path,monkeypatch):
    monkeypatch.setattr(queue,'_ROOT',tmp_path/'queue')
    monkeypatch.setenv('MTA_DATA_DIR',str(tmp_path/'data'))
    queue.configure(1)
    yield
    deadline=time.monotonic()+5
    while queue._LOCAL and time.monotonic()<deadline:time.sleep(.02)


def test_token_and_nested_web_jobs_share_one_fifo_slot(isolated_queue):
    entered=threading.Event();release=threading.Event();calls=[]
    def first(cancelled):
        entered.set();assert release.wait(5)
        return execution.execute(1,'markers',lambda c:calls.append('nested') or 'nested')
    with ThreadPoolExecutor(2) as pool:
        a=pool.submit(execution.execute,1,'whisper',first)
        assert entered.wait(5)
        b=pool.submit(execution.execute,2,'demucs',lambda c:calls.append('second') or 'done')
        deadline=time.monotonic()+5
        while len(queue.list_jobs())<2 and time.monotonic()<deadline:time.sleep(.02)
        rows=queue.list_jobs()
        assert sum(r['state']=='running' for r in rows)==1
        assert sum(r['state']=='queued' for r in rows)==1
        assert calls==[]
        release.set()
        assert a.result(5)=='nested' and b.result(5)=='done'
    assert calls==['nested','second']
    assert len(queue.list_jobs())==2  # nested execution did not consume another slot
    assert all(r['state']=='completed' for r in queue.list_jobs())


def test_queued_cancel_does_not_dispatch(isolated_queue):
    hold=threading.Event();entered=threading.Event();cancel=threading.Event();called=[]
    def first(c):entered.set();assert hold.wait(5)
    with ThreadPoolExecutor(2) as pool:
        a=pool.submit(execution.execute,1,'whisper',first)
        assert entered.wait(5)
        b=pool.submit(execution.execute,2,'markers',lambda c:called.append(True),cancel_check=cancel.is_set)
        cancel.set()
        with pytest.raises(RuntimeError,match='cancelled'):b.result(5)
        hold.set();a.result(5)
    assert not called


def test_orphan_remote_admission_does_not_block_fifo(isolated_queue,monkeypatch):
    queue.start('remote-user-1','worker:whisper',lambda p,s:None,job_id='orphan',defer_spawn=True,payload={'schema_version':1,'actor_user_id':1})
    with queue._db() as con:
        con.execute("UPDATE jobs SET runner_pid=99999999,runner_identity='dead' WHERE job_id='orphan'")
    assert execution.execute(2,'markers',lambda c:'result')=='result'
    assert queue.get('orphan')['state']=='interrupted'


def test_operator_registry_supports_future_engine_and_rejects_bad_config(tmp_path,monkeypatch):
    from app import ai_worker_registry as registry
    runner=tmp_path/'trusted.py';runner.write_text('');runner.chmod(0o700)
    config=tmp_path/'engines.json';monkeypatch.setenv('MTA_AI_ENGINE_REGISTRY_FILE',str(config))
    monkeypatch.setenv('MTA_AI_WORKER_ENABLED','true')
    config.write_text(json.dumps([{'kind':'future-engine','executable':str(runner),'gpu_capable':True}]))
    assert registry.resolve_worker('future-engine')==runner
    assert registry.available_workers()['future-engine']
    config.write_text(json.dumps([{'kind':'future-engine','executable':['unsafe']}]))
    with pytest.raises(ValueError):registry.extensions()


def test_markers_and_chord_options_are_available_in_unified_protocol(tmp_path,monkeypatch):
    from app import ai_unified_adapter as adapter,music_text
    source=tmp_path/'source.wav';source.write_bytes(b'private fixture')
    monkeypatch.setattr(music_text,'extract_markers',lambda p:[])
    adapter.infer({'kind':'markers','source_audio':str(source)},tmp_path/'preview.wav')
    assert json.loads((tmp_path/'markers.json').read_text())=={'markers':[]}
    seen={}
    def chords(path,**kwargs):seen.update(kwargs);return []
    monkeypatch.setattr(music_text,'extract_chords_progressive',chords)
    adapter.infer({'kind':'chords-ml','source_audio':str(source),'engine':'profile-fast','options':{'sensitivity':65},'bpm':99,'beat_origin_ms':25},tmp_path/'preview.wav')
    assert seen=={'engine':'profile-fast','options':{'sensitivity':65},'bpm':99.,'beat_origin_ms':25}


def test_native_future_engine_uses_shared_token_and_keeps_it_private(tmp_path,monkeypatch):
    from app import native_ai_routing as routing
    monkeypatch.setenv('MTA_NATIVE_AI_CONFIG',str(tmp_path/'remote.json'))
    routing.configure('future-engine','remote','https://mta.example.org','private-token')
    public=routing.public_settings()
    assert public['workers']['future-engine']['has_token']
    assert 'private-token' not in json.dumps(public)


def test_production_server_requires_authenticated_queue_identity(monkeypatch):
    from app import ai_server_execution as server
    monkeypatch.delenv('MTA_ALLOW_INSECURE_NO_AUTH',raising=False)
    assert server.enabled(False) and not server.enabled(True)
    with pytest.raises(ValueError,match='Authenticated'):server.identity()


def test_authenticated_token_worker_uses_global_queue_and_owner_receipt(isolated_queue,tmp_path,monkeypatch):
    from app import ai_access,ai_billing,auth
    from app.ai_billing_routes import router
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    auth.init_auth_db()
    with auth.db() as con:
        for name in ('one','two'):
            con.execute("INSERT INTO users(username,email,password_hash,active,email_confirmed,role,created_at,updated_at) VALUES(?,?,?,1,1,'user',1,1)",(name,name+'@example.org','fake'))
        users=[r[0] for r in con.execute("SELECT id FROM users WHERE username IN ('one','two') ORDER BY username")]
    token=ai_access.issue(users[0],'Mac')['token'];other=ai_access.issue(users[1],'Windows')['token']
    runner=tmp_path/'markers.py'
    runner.write_text('''import argparse,json,pathlib,hashlib
p=argparse.ArgumentParser();p.add_argument('--request');p.add_argument('--output');a=p.parse_args()
f=pathlib.Path(a.output).parent;r=f/'markers.json';r.write_text('{"markers":[]}')
(f/'output.manifest.json').write_text(json.dumps({'version':1,'files':[{'name':r.name,'type':'application/json','sha256':hashlib.sha256(r.read_bytes()).hexdigest()}]}))
''');runner.chmod(0o700)
    monkeypatch.setenv('MTA_AI_WORKER_ENABLED','true');monkeypatch.setenv('MTA_AI_WORKER_MARKERS_EXECUTABLE',str(runner))
    monkeypatch.delenv('MTA_ALLOW_INSECURE_NO_AUTH',raising=False)
    monkeypatch.delenv('MTA_AI_CGROUP_PARENT',raising=False)
    app=FastAPI();app.include_router(router);client=TestClient(app)
    headers={'Authorization':'Bearer '+token}
    response=client.post('/api/ai-jobs/execute',headers=headers,json={'kind':'markers','plan':{'kind':'markers'}})
    assert response.status_code==200,response.text
    jid=response.headers['x-mta-ai-job-id']
    receipt=client.get('/api/ai-jobs/resources/'+jid,headers=headers)
    assert receipt.status_code==200 and receipt.json()['usage']['cpu_seconds']>=0
    assert receipt.json()['gpu_verified'] is False
    qid=receipt.json()['queue_job_id']
    assert queue.get(qid)['state']=='completed' and queue.get(qid)['operation']=='worker:markers'
    with ai_billing.db() as con:
        row=con.execute('SELECT user_id,token_id FROM ai_compute_jobs WHERE id=?',(jid,)).fetchone()
        assert row[0]==users[0] and row[1]==ai_access.authenticate(token)['id']
    assert client.get('/api/ai-jobs/resources/'+jid,headers={'Authorization':'Bearer '+other}).status_code==404
    assert client.get('/api/ai-jobs/resources/'+jid).status_code==401


def test_server_raw_wav_preserves_publication_metadata(isolated_queue,tmp_path,monkeypatch):
    import io,wave
    from app import ai_server_execution as server,ai_metering_agent,auth
    auth.init_auth_db()
    with auth.db() as con:
        con.execute("INSERT INTO users(username,email,password_hash,active,role,created_at,updated_at) VALUES('metadata-owner','metadata@example.test','unused',1,'user',1,1)")
        uid=con.execute("SELECT id FROM users WHERE username='metadata-owner'").fetchone()[0]
    out=io.BytesIO()
    with wave.open(out,'wb') as handle:
        handle.setnchannels(1);handle.setsampwidth(2);handle.setframerate(44100);handle.writeframes(bytes(882))
    audio=out.getvalue();source=tmp_path/'source.wav';source.write_bytes(audio)
    monkeypatch.setattr(ai_metering_agent,'execute_registered_worker',lambda *a,**k:(audio,{'job_id':'metered','usage':{'cpu_seconds':1},'metering_source':'worker'}))
    result=execution.execute(uid,'ace-step',lambda c:server.infer('ace-step',source,{},raw=True))
    assert result[0]==audio
    assert result[1]['frames']==441 and result[1]['sample_rate']==44100 and result[1]['channels']==1
    assert result[1]['usage']=={'cpu_seconds':1}


def test_server_runtime_configuration_is_private_and_preserves_settings(tmp_path,monkeypatch):
    import importlib.util,sys,subprocess
    spec=importlib.util.spec_from_file_location('configure_workers',Path(__file__).parents[1]/'scripts/configure_ai_workers.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    config=tmp_path/'mta.env';config.write_text('MTA_PUBLIC_URL="https://mta.example.org"\nMTA_AI_WORKER_WHISPER_PYTHON="old"\n')
    calls=[]
    monkeypatch.setattr(module.subprocess,'run',lambda *a,**k:calls.append((a,k)))
    result=module.configure(sys.executable,config,['whisper','markers'])
    assert result['configured']==['whisper','markers'] and result['gpu_billing_activated'] is False
    assert config.stat().st_mode&0o777==0o600
    text=config.read_text()
    assert text.count('MTA_AI_WORKER_WHISPER_PYTHON=')==1 and 'MTA_PUBLIC_URL="https://mta.example.org"' in text
    assert 'MTA_AI_UNIFIED_WORKERS_ENABLED="true"' in text and calls[0][1]['check'] is True
    previous=config.read_bytes()
    def broken(*a,**k):raise subprocess.CalledProcessError(1,a)
    monkeypatch.setattr(module.subprocess,'run',broken)
    with pytest.raises(subprocess.CalledProcessError):module.configure(sys.executable,config,['whisper'])
    assert config.read_bytes()==previous


def test_server_whisper_cannot_bill_an_unprofiled_cli(tmp_path,monkeypatch):
    from app import music_text
    monkeypatch.setattr(music_text.importlib.util,'find_spec',lambda name:None)
    monkeypatch.setattr(music_text.shutil,'which',lambda name:'/operator/whisper')
    monkeypatch.setenv('MTA_DATA_DIR',str(tmp_path))
    with pytest.raises(RuntimeError,match='in-process'):
        music_text.extract_lyrics(tmp_path/'input.wav',require_inprocess=True)
