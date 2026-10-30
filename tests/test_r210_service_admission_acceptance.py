"""Original C2 acceptance:real API/process/PCM boundaries;no plugin/hardware claim."""
# ruff: noqa: F811 -- imported pytest fixtures are injected by name
from contextlib import closing
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import threading
import time
from types import SimpleNamespace

from fastapi.testclient import TestClient
import pytest
from app import auth,service_admission as gate,storage
from app.regime_operation_fence import FenceBlocked
from test_r210_service_admission import authority as authority,env as env,change,status  # noqa:F401
from test_r210_legal_documents import cookie


def wait_until(call,seconds=6):
    deadline=time.monotonic()+seconds
    while time.monotonic()<deadline:
        if call():return
        time.sleep(.02)
    assert call()


def test_actual_main_restart_under_drain_skips_work_then_explicit_resume_bootstraps_once(authority,monkeypatch):
    from app import main
    monkeypatch.setattr(main,'NATIVE_SINGLE_USER',False)
    cookies=cookie(authority[0]);calls=[]
    for name in ['_start_diagnostic_cleanup','_start_background_services','_restore_persisted_ai_queue','_start_kara_checkpoint_repair']:
        monkeypatch.setattr(main,name,lambda name=name:calls.append(name))
    monkeypatch.setattr(main,'_cleanup_session_previews_on_shutdown',lambda:None)
    assert change(authority)['drained']
    with TestClient(main.app) as client:
        client.cookies.update(cookies)
        assert calls==[]
        assert client.get('/api/projects').status_code==503
        read=client.get('/api/admin/service-admission');assert read.status_code==200,read.text
        assert read.json()['drained']
        response=client.post('/api/admin/service-admission/change',headers={'X-MTA-Request':'1'},json={
            'expected_generation':1,'draining':False,'identifier':'drain-original','confirm':True})
        assert response.status_code==200,response.text
        wait_until(lambda:len(calls)==4)
        assert len(set(calls))==4
        assert client.get('/api/projects').status_code==200
        wait_until(lambda:status(authority)['active_count']==0)


def test_new_build_handoff_keeps_original_rows_and_gate_closed(authority,monkeypatch):
    original=gate.build();change(authority)
    with sqlite3.connect(gate.path()) as con:before=con.execute('SELECT * FROM admissions').fetchall()
    monkeypatch.setattr(gate,'build',lambda:'b'*64)
    current=status(authority);assert not current['drained'] and not current['build_matches']
    with pytest.raises(FenceBlocked):gate.reserve('new-build')
    handed=gate.upgrade(actor=authority[0],expected_generation=1,expected_build=original,confirm=True)
    assert handed['generation']==2 and handed['phase']=='draining' and handed['drained']
    assert [r['action'] for r in handed['audit']]==['upgrade','begin']
    with sqlite3.connect(gate.path()) as con:assert con.execute('SELECT * FROM admissions').fetchall()==before
    with pytest.raises(FenceBlocked):gate.reserve('still-held')
    change(authority,generation=2,draining=False)
    with gate.operation('new-build'):pass
    monkeypatch.setattr(gate,'build',lambda:original)
    with pytest.raises(FenceBlocked):gate.reserve('old-replica')


@pytest.mark.parametrize('block',['open','active','pending','stale','foreign'])
def test_upgrade_never_discards_original_unfinished_or_foreign_work(authority,monkeypatch,block):
    old=gate.build()
    if block=='active':gate.reserve('unfinished')
    if block=='pending':
        folder=storage.ROOT/'p';folder.mkdir();(folder/'.ordinary-upload-pending.json').write_text('{}')
    if block!='open':change(authority)
    monkeypatch.setattr(gate,'build',lambda:'b'*64)
    with pytest.raises(FenceBlocked):gate.upgrade(actor=authority[0],expected_generation=0 if block=='stale' else 1,
        expected_build='f'*64 if block=='foreign' else old,confirm=True)
    with sqlite3.connect(gate.path()) as con:assert con.execute('SELECT build FROM state').fetchone()[0]==old


def test_original_http_capture_finishes_and_import_child_remains_tracked_under_drain(authority,monkeypatch):
    import numpy as np
    from app import main,audio_capture
    monkeypatch.setattr(main,'NATIVE_SINGLE_USER',False)
    project=storage.create_project('Drain capture',owner_user_id=authority[0]);cookies=cookie(authority[0])
    entered=threading.Event();finish=threading.Event();original=main._track_import_worker
    def worker(*args,**kw):entered.set();assert finish.wait(6);return original(*args,**kw)
    monkeypatch.setattr(main,'_track_import_worker',worker)
    with closing(TestClient(main.app)) as client:
        client.cookies.update(cookies);client.headers['X-MTA-Request']='1'
        url='/api/projects/'+project.id+'/audio-capture'
        response=client.post(url,json={'rate':48000});assert response.status_code==200,response.text
        token=response.json()['capture_id'];url+='/'+token
        pcm=np.sin(np.arange(9600)*.1).astype('<f4').tobytes()
        assert client.post(url+'/pcm?sequence=0',content=pcm).status_code==200
        held=change(authority);assert held['active_by_source']=={'audio-capture':1} and not held['drained']
        assert client.post(url+'/pcm?sequence=1',content=pcm).status_code==503
        try:
            response=client.post(url+'/finish',json={'sequence':1,'name':'Original recording'})
            assert response.status_code==200,response.text
            assert entered.wait(3) and token not in audio_capture._CAPTURES
            assert not status(authority)['drained'] and status(authority)['active_count']==1
        finally:finish.set()
        wait_until(lambda:status(authority)['drained'],seconds=15)
        saved=storage.load_project(project.id)
        assert len(saved.tracks)==1 and saved.tracks[0].name=='Original recording'
        assert storage.audio_path(project.id,saved.tracks[0].filename).is_file()


@pytest.mark.parametrize('fail_close',[False,True])
def test_vst3_lifetime_ticket_covers_real_child_and_failed_cleanup_is_never_drained(authority,monkeypatch,fail_close):
    from app import server_vst3
    children=[]
    class ProcessSession:
        def __init__(self,*args,**kwargs):
            self.proc=subprocess.Popen([sys.executable,'-c','import time;time.sleep(60)']);children.append(self.proc)
        def status(self):return {'physical':False}
        def close(self):
            if fail_close:raise OSError('Unverified external worker shutdown')
            self.proc.terminate();self.proc.wait(4)
    monkeypatch.setattr(server_vst3,'Session',ProcessSession)
    manager=server_vst3.Sessions()
    try:
        opened=manager.start(authority[0],SimpleNamespace(id='p'),[],'original-client',0)
        held=change(authority);assert held['active_by_source']=={'vst3-session':1}
        assert children[0].poll() is None
        if fail_close:
            with pytest.raises(OSError):manager.close(opened['session_id'])
            assert not status(authority)['drained'] and children[0].poll() is None
        else:
            manager.close(opened['session_id']);assert children[0].poll() is not None
            assert status(authority)['drained']
    finally:
        for proc in children:
            if proc.poll() is None:proc.kill();proc.wait(4)


def test_independent_process_admission_and_drain_serialize_at_original_journal(authority,tmp_path):
    go=tmp_path/'go';ready=tmp_path/'ready';finish=tmp_path/'finish';output=tmp_path/'result'
    code='''import os,time
from pathlib import Path
from app import service_admission as gate
from app.regime_operation_fence import FenceBlocked
p=Path(os.environ['MTA_RACE_DIR']);(p/'ready').touch()
while not (p/'go').exists():time.sleep(.005)
try:
 with gate.operation('race-process'):
  (p/'result').write_text('admitted')
  while not (p/'finish').exists():time.sleep(.005)
except FenceBlocked:(p/'result').write_text('refused')
'''
    env_={**os.environ,'MTA_DATA_DIR':str(auth.data_root()),'MTA_RACE_DIR':str(tmp_path),'PYTHONPATH':str(Path.cwd())}
    proc=subprocess.Popen([sys.executable,'-c',code],env=env_,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    try:
        wait_until(ready.exists);go.touch();held=change(authority);wait_until(output.exists)
        assert output.read_text() in {'admitted','refused'}
        if output.read_text()=='admitted':assert not status(authority)['drained']
        else:assert held['drained']
        finish.touch();assert proc.wait(5)==0
        assert status(authority)['drained']
    finally:
        if proc.poll() is None:proc.kill();proc.wait(4)


def test_read_snapshot_blocks_resume_until_pending_audit_has_finished(authority,monkeypatch):
    from app import service_drain_obligations
    change(authority);original=service_drain_obligations.audit;entered=threading.Event();finish=threading.Event();results=[];errors=[]
    def audit():entered.set();assert finish.wait(4);return original()
    monkeypatch.setattr(service_drain_obligations,'audit',audit)
    def read():
        try:results.append(status(authority))
        except Exception as exc:errors.append(exc)
    def resume():
        try:results.append(change(authority,generation=1,draining=False))
        except Exception as exc:errors.append(exc)
    first=threading.Thread(target=read);first.start();assert entered.wait(2)
    second=threading.Thread(target=resume);second.start();time.sleep(.1)
    assert not results
    finish.set();first.join(5);second.join(5)
    assert all(isinstance(e,FenceBlocked) for e in errors) and results[0]['drained']
    if errors:assert change(authority,generation=1,draining=False)['phase']=='open'
    else:assert len(results)==2 and results[1]['phase']=='open'


def test_active_drain_poll_does_not_exclude_original_worker_database(authority,monkeypatch):
    from contextlib import contextmanager
    from app import regime_service_lease,service_drain_obligations
    original_lease=regime_service_lease.lease
    original_audit=service_drain_obligations.audit
    audits=[]
    # Observe acquisition, rather than replacing the actual flock protocol.
    @contextmanager
    def observed_lease(*,exclusive=False):
        if exclusive:exclusive_calls.append(True)
        with original_lease(exclusive=exclusive):yield
    exclusive_calls=[]
    monkeypatch.setattr(regime_service_lease,'lease',observed_lease)
    def audit():
        audits.append(True)
        return original_audit()
    monkeypatch.setattr(service_drain_obligations,'audit',audit)
    with gate.operation('original-worker'):
        held=change(authority)
        assert not held['drained'] and held['active_count']==1
        assert not exclusive_calls and not audits
        assert not held['pending']['verified'] and held['pending']['count'] is None
        with auth.db() as con:
            assert con.execute('SELECT count(*) FROM users').fetchone()[0]
        assert not status(authority)['drained']
    assert status(authority)['drained']
    assert exclusive_calls==[True] and audits==[True]


def test_drain_observer_cannot_interrupt_an_admitted_database_entry(authority,monkeypatch):
    from app import service_drain_obligations
    original=service_drain_obligations.audit
    entered=threading.Event();attempt=threading.Event();attempted=threading.Event()
    errors=[];reads=[]
    def worker():
        entered.set()
        try:
            assert attempt.wait(4)
            with gate.control(),auth.db() as con:reads.append(con.execute('SELECT count(*) FROM users').fetchone()[0])
        except Exception as exc:errors.append(type(exc).__name__)
        finally:attempted.set()
    def audit():
        # Force the database entry inside the observer's lease window. On
        # the old code its exclusive flock rejects the original participant.
        attempt.set();assert attempted.wait(4)
        return original()
    monkeypatch.setattr(service_drain_obligations,'audit',audit)
    thread=gate.worker_thread(target=worker,name='original-database-entry')
    thread.start();assert entered.wait(2)
    try:
        assert not change(authority)['drained']
    finally:
        attempt.set();thread.join(5)
    assert not thread.is_alive() and not errors and reads
    assert status(authority)['drained']


@pytest.mark.parametrize('source',['scheduler','sampler'])
def test_timer_entry_is_denied_before_any_work_when_barrier_held(authority,monkeypatch,source):
    from app import ai_billing_scheduler,ai_storage_sampler
    change(authority);calls=[]
    monkeypatch.setattr(ai_billing_scheduler,'run_scheduled_closures',lambda:calls.append('billed'))
    with pytest.raises(FenceBlocked):
        (ai_billing_scheduler.main if source=='scheduler' else ai_storage_sampler.sample_all)()
    assert not calls and status(authority)['drained']


@pytest.mark.parametrize('damage',['empty','public-journal','public-seal','malformed-seal'])
def test_truncated_or_unsafe_original_journal_never_reinitializes_open(authority,damage):
    change(authority)
    if damage=='empty':gate.path().write_bytes(b'')
    elif damage=='public-journal':gate.path().chmod(0o644)
    elif damage=='public-seal':gate.path().with_suffix('.instance').chmod(0o644)
    else:gate.path().with_suffix('.instance').write_text('X'*64)
    with pytest.raises((FenceBlocked,sqlite3.Error)):
        with gate.operation('new-work'):pytest.fail('Original damaged state was reset')


def test_second_thread_start_cannot_replace_original_running_ticket(authority):
    started=threading.Event();finish=threading.Event()
    def work():started.set();assert finish.wait(4)
    thread=gate.worker_thread(target=work,name='original-thread');thread.start();assert started.wait(2)
    first=dict(thread._admission)
    try:
        with pytest.raises(RuntimeError):thread.start()
        assert thread._admission==first
        assert not change(authority)['drained']
    finally:finish.set();thread.join(5)
    assert status(authority)['drained']


from test_r210_deferred_owner_e2e import setup as local_job,operator as operator,generate  # noqa:F401,E402


def test_registered_local_worker_heartbeat_publication_and_single_charge_finish_under_drain(local_job,tmp_path,monkeypatch):
    from app import ai_arranger_runtime as queue,ai_publish_outbox as publication,ai_billing_outbox as billing
    monkeypatch.setenv('MTA_SERVICE_ADMISSION',gate.MODE)
    monkeypatch.setattr(storage,'ROOT',tmp_path/'projects');storage.ROOT.mkdir()
    monkeypatch.setattr('app.deferred_execution_owner.HEARTBEAT_INTERVAL',.02)
    uid,job,ledger=local_job
    with auth.db() as con:
        admin=con.execute("INSERT INTO users(username,email,password_hash,role,active,email_confirmed,created_at,updated_at) VALUES('drain-admin','drain@example.test','unused','admin',1,1,1,1)").lastrowid
    started=threading.Event();finish=threading.Event();published=[]
    def work(progress,stop):
        started.set();assert finish.wait(5)
        audio=generate(uid,job)
        publication.stage(job,'project1',audio,{'mode':'arranger'})
        publication.recover(lambda *args:published.append(args[0]),job_id=job)
    assert queue.activate(job,work);assert started.wait(3)
    held=gate.change(actor=admin,expected_generation=0,draining=True,identifier='drain-local-worker',confirm=True)
    assert not held['drained']
    time.sleep(.12)  # actual original-claim heartbeats continue under the barrier
    finish.set()
    wait_until(lambda:gate.inspect(actor=admin)['drained'],seconds=15)
    with gate.control(),auth.db() as con:
        assert con.execute('SELECT status FROM ai_compute_jobs WHERE id=?',(ledger,)).fetchone()[0]=='done'
        assert con.execute('SELECT state FROM regime_worker_claims WHERE operation_id=?',('job:ledger:'+ledger,)).fetchone()[0]=='finished'
    with gate.control():
        assert queue.get(job)['state']=='completed' and billing.inspect(job)['state']=='delivered'
    assert published==[job]


@pytest.mark.parametrize('kind',['sending-mail','deleting-account','purge-recovery','unsafe-project-root'])
def test_original_legacy_side_effects_and_unknown_roots_block_drain(authority,kind,tmp_path,monkeypatch):
    from app import account_lifecycle
    if kind=='unsafe-project-root':
        alias=tmp_path/'foreign-root';alias.symlink_to(storage.ROOT,target_is_directory=True);monkeypatch.setattr(storage,'ROOT',alias)
    else:
        with auth.db() as con:
            account_lifecycle.init(con)
            if kind=='sending-mail':con.execute("INSERT INTO account_mail_outbox(id,recipient,subject,body,state,lease) VALUES('original','nobody@example.test','test','unused','sending',0)")
            elif kind=='purge-recovery':con.execute('INSERT INTO account_purge_jobs VALUES(?,?)',(authority[0],'[]'))
            else:con.execute("INSERT INTO account_lifecycle(user_id,state) VALUES(?,'deleting')",(authority[0],))
    snapshot=change(authority)
    assert not snapshot['drained']
    assert not snapshot['pending']['verified'] or snapshot['pending']['count']>0


def test_actual_admin_upgrade_route_checks_csrf_exact_body_and_keeps_gate_closed(authority,monkeypatch):
    from test_r210_service_admission import web_app
    cookies=cookie(authority[0]);old=gate.build();change(authority)
    monkeypatch.setattr(gate,'build',lambda:'b'*64)
    with closing(TestClient(web_app())) as client:
        client.cookies.update(cookies);url='/api/admin/service-admission/upgrade'
        body={'expected_generation':1,'expected_build':old,'confirm':True}
        assert client.post(url,json=body).status_code==403
        headers={'X-MTA-Request':'1'}
        assert client.post(url,json={**body,'ignore_work':True},headers=headers).status_code==400
        assert client.post(url,json={**body,'confirm':1},headers=headers).status_code==400
        result=client.post(url,json=body,headers=headers);assert result.status_code==200,result.text
        assert result.json()['drained'] and result.json()['generation']==2
        assert client.post('/work').status_code==503


def test_real_changed_source_build_handoff_in_independent_process_fences_old_replica(authority,tmp_path):
    from app import ai_arranger_runtime as queue
    import json
    copy=tmp_path/'new-build';original=Path(gate.__file__).parent
    for p in original.rglob('*.py'):
        dest=copy/'app'/p.relative_to(original);dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(p.read_bytes())
    p=copy/'app/version.py';p.write_text(p.read_text()+'\n# New reviewed build for admission handoff acceptance.\n')
    old=gate.build();change(authority)
    code='''import json,os
from pathlib import Path
from app import service_admission as gate,ai_arranger_runtime as queue,storage
from app.regime_operation_fence import FenceBlocked
queue._ROOT=Path(os.environ['MTA_C2_QUEUE']);storage.ROOT=Path(os.environ['MTA_C2_PROJECTS'])
try:gate.reserve('new-code-before-upgrade')
except FenceBlocked:pass
else:raise SystemExit('Unapproved build admitted work')
print(json.dumps(gate.upgrade(actor=int(os.environ['MTA_C2_ACTOR']),expected_generation=1,expected_build=os.environ['MTA_C2_OLD'],confirm=True)))
'''
    env_={**os.environ,'MTA_DATA_DIR':str(auth.data_root()),'MTA_C2_QUEUE':str(queue._ROOT),
        'MTA_C2_PROJECTS':str(storage.ROOT),'MTA_C2_ACTOR':str(authority[0]),'MTA_C2_OLD':old,'PYTHONPATH':str(copy)}
    result=subprocess.run([sys.executable,'-c',code],cwd=copy,env=env_,capture_output=True,text=True,timeout=10)
    assert result.returncode==0,result.stderr
    value=json.loads(result.stdout);assert value['drained'] and value['current_build']!=old
    assert value['phase']=='draining' and value['generation']==2
    with pytest.raises(FenceBlocked):gate.reserve('old-replica-after-upgrade')


from test_r210_user_erasure_dump import env as dump_env  # noqa:F401,E402


def test_online_backup_and_offline_restore_preserve_original_gate_instance_and_uncertain_work(dump_env,tmp_path,monkeypatch):
    from app import admin_dump as dump
    import zipfile
    monkeypatch.setenv('MTA_SERVICE_ADMISSION',gate.MODE)
    original=gate.reserve('original-unverified-work')
    archive=dump.create({'all_users':True,'all_projects':True})
    try:
        with zipfile.ZipFile(archive) as z:
            assert {'data/service-admission.sqlite3','data/service-admission.instance'}<=set(z.namelist())
        restored=tmp_path/'restored-data'
        dump.restore(archive,data_dir=restored,queue_dir=tmp_path/'restored-queue',gpu_dir=tmp_path/'restored-gpu',service_stopped=True)
        with sqlite3.connect(restored/'service-admission.sqlite3') as con:
            assert con.execute('SELECT state FROM admissions WHERE id=?',(original['id'],)).fetchone()[0]=='open'
        assert (restored/'service-admission.instance').read_bytes()==gate.path().with_suffix('.instance').read_bytes()
        monkeypatch.setattr(auth,'DATA_ROOT',restored)
        value=gate.change(actor=dump_env[0],expected_generation=0,draining=True,identifier='restored-drain',confirm=True)
        assert not value['drained'] and value['active_by_source']['original-unverified-work']==1
    finally:archive.unlink()


@pytest.mark.parametrize('change_sql',[
 'DROP TRIGGER immutable_admission',
 'CREATE TRIGGER foreign_code AFTER INSERT ON admissions BEGIN DELETE FROM events;END',
 'CREATE VIEW forged_admissions AS SELECT * FROM admissions',
])
def test_missing_or_extra_executable_journal_schema_is_not_accepted(authority,change_sql):
    change(authority)
    with sqlite3.connect(gate.path()) as con:con.execute(change_sql)
    with pytest.raises(FenceBlocked):gate.inspect(actor=authority[0])
    with pytest.raises(FenceBlocked):gate.reserve('new-work')
