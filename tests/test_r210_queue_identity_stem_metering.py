"""Stem admission, real subprocess CPU settlement and historical identity lookup."""
import json
import sys
import time
from pathlib import Path
import pytest
from app import auth, ai_arranger_runtime as queue, ai_queue_admin, ai_billing as billing


@pytest.fixture
def env(tmp_path,monkeypatch):
    monkeypatch.setattr(auth,'DATA_ROOT',tmp_path/'auth')
    monkeypatch.setattr(queue,'_ROOT',tmp_path/'queue')
    monkeypatch.setenv('MTA_ADMIN_PASSWORD','administrator-password')
    auth.init_auth_db();uid=auth.find_user('admin')['id']
    with auth.db() as con:billing._init(con)
    return uid


def test_legacy_stem_admission_persists_authenticated_actor_and_real_cpu(env,tmp_path,monkeypatch):
    from app import main, ai_metering_agent as agent
    from app.ai_job_context import actor
    from app.ai_global_execution import current_job
    worker=tmp_path/'worker.py'
    worker.write_text('''import argparse,json,time,wave
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--request');p.add_argument('--output');a=p.parse_args()
end=time.monotonic()+.15
while time.monotonic()<end:sum(range(1000))
root=Path(a.output).parent
entries=[]
for name in ('vocals.wav','drums.wav'):
 with wave.open(str(root/name),'wb') as w:w.setnchannels(1);w.setsampwidth(2);w.setframerate(44100);w.writeframes(b'\\0\\0'*8000)
 entries.append({'name':name,'type':'audio/wav'})
(root/'output.manifest.json').write_text(json.dumps({'version':1,'files':entries}))
''')
    monkeypatch.setattr('app.ai_worker_registry.resolve_worker',lambda kind:worker)
    monkeypatch.setattr('app.ai_worker_registry.worker_python',lambda kind:sys.executable)
    monkeypatch.setattr('app.ai_gpu_slot_accounting.slot_enabled_for_kind',lambda kind:False)
    monkeypatch.setattr('app.ai_gpu_verified.readiness',lambda:{'ready':False})
    monkeypatch.delenv('MTA_AI_CGROUP_PARENT',raising=False)
    # This environment's procfs uses another PID namespace; wait4 below still
    # measures the actual child. This worker is known not to spawn children.
    monkeypatch.setattr(agent,'_descendants',lambda pid:set())
    jid='stem-e2e';job={'id':jid,'project_id':'p','status':'queued'};returned={}
    monkeypatch.setitem(main.STEM_JOBS,jid,job)
    def work():
        assert current_job.get()==jid
        returned['payload'],returned['meta']=agent.execute_registered_worker(env,'demucs',{})
    token=actor.set(None)
    try:
        main._enqueue_existing_ai_job(job,work,durable_payload={'schema_version':1},actor_user_id=env)
    finally:actor.reset(token)
    deadline=time.monotonic()+15
    while time.monotonic()<deadline:
        value=queue.get(jid)
        if value['state'] in ('completed','failed','interrupted'):break
        time.sleep(.05)
    assert value['state']=='completed',value.get('message')
    assert value['actor_user_id']==env and value['actor_username']=='admin'
    assert queue.read_payload(jid)['actor_user_id']==env
    assert value['cpu_seconds']>0 and value['gpu_seconds'] is None
    row=ai_queue_admin.query(search='Administrator')['jobs'][0]
    assert row['job_id']==jid and row['cpu_seconds']==value['cpu_seconds']
    with auth.db() as con:
        measured=con.execute('SELECT user_id,usage_json,resource_source,queue_job_id FROM ai_compute_jobs').fetchone()
    assert measured['user_id']==env and measured['queue_job_id']==jid
    assert measured['resource_source']=='worker'
    assert json.loads(measured['usage_json'])['cpu_seconds']==value['cpu_seconds']
    assert returned['meta']['job_id'] and returned['payload'][:2]==b'PK'


def test_old_queue_owner_recovered_only_from_unique_explicit_ledger_link(env):
    with queue._db() as con:
        con.execute("INSERT INTO jobs(job_id,project_id,operation,state,rank,created_at,phase,message) VALUES('old','p','stem-separation','completed',1,1,'done','')")
    with auth.db() as con:
        con.execute("INSERT INTO ai_compute_jobs(id,user_id,kind,status,started_at,queue_job_id,usage_json,resource_source) VALUES('ledger',?,'demucs','done',1,'old',?,'cgroup')",(env,json.dumps({'cpu_seconds':9})))
    value=queue.get('old');assert value['actor_user_id']==env and value['actor_username']=='admin' and value['cpu_seconds']==9
    assert ai_queue_admin.query(search='admin')['total']==1
    assert ai_queue_admin.query(search='Administrator')['total']==1
    assert ai_queue_admin.query(search=str(env))['total']==1
    assert ai_queue_admin.query(search='nonexistent-user')['total']==0


def test_queue_name_is_not_guessed_from_project_owner_or_ambiguous_ledger(env):
    with queue._db() as con:
        con.execute("INSERT INTO jobs(job_id,project_id,operation,state,rank,created_at,phase,message) VALUES('unknown','p','stem-separation','completed',1,1,'done','')")
    assert queue.get('unknown').get('actor_username') is None
    assert ai_queue_admin.query(search='admin')['total']==0


def test_queue_ui_has_visible_user_column_and_escapes_names():
    root=Path(__file__).resolve().parents[1]
    assert '<th>Utente</th>' in (root/'app/templates/admin.html').read_text()
    script=(root/'app/static/admin.js').read_text()
    assert "esc(j.actor_username||'Utente non registrato nel job')" in script
    assert 'username, nome, email' in (root/'app/templates/admin.html').read_text()


def test_model_download_also_persists_actor(env,monkeypatch):
    from app import main
    monkeypatch.setattr(main,'_actor',lambda request:{'id':env})
    monkeypatch.setattr(queue,'_spawn',lambda *a,**kw:True)
    job=main._start_ai_model_download_job('lyrics','safe-model',None)
    try:
        assert queue.read_payload(job['id'])['actor_user_id']==env
        assert queue.get(job['id'])['actor_username']=='admin'
    finally:main.MEDIA_JOBS.pop(job['id'],None)
