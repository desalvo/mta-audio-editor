"""Immediate erasure and scoped administrator backup/restore integration."""
import json
import sqlite3
import zipfile
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app import auth, storage, account_lifecycle as life, account_erasure as erasure
from app import admin_dump as dump, admin_dump_routes, ai_billing as billing, ai_arranger_runtime as queue


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setattr(auth, 'DATA_ROOT', tmp_path/'data')
    monkeypatch.setattr(storage, 'ROOT', tmp_path/'data')
    monkeypatch.setattr(queue, '_ROOT', tmp_path/'queue')
    monkeypatch.setattr(storage, 'SHARED_MEDIA_ROOT', tmp_path/'shared')
    monkeypatch.setattr(storage, 'SHARED_AUDIO_ROOT', tmp_path/'shared/audio')
    monkeypatch.setattr(storage, 'SHARED_INDEX_PATH', tmp_path/'shared/index.json')
    monkeypatch.setenv('MTA_GPU_BILLING_ROOT', str(tmp_path/'gpu'))
    monkeypatch.setenv('MTA_ADMIN_PASSWORD', 'administrator-password')
    monkeypatch.setattr(auth, 'send_mail', lambda *a, **kw: None)
    auth.init_auth_db(); life.settings()
    admin=auth.find_user('admin')['id']
    with auth.db() as con:
        billing._init(con)
        for username,role in (('alice','user'),('bob','user'),('second-admin','admin')):
            con.execute('INSERT INTO users(username,email,password_hash,role,active,email_confirmed,created_at,updated_at) VALUES(?,?,?, ?,1,1,1,1)',(username,username+'@example.test',auth._password_hash('long-password-test'),role))
    alice=auth.find_user('alice')['id'];bob=auth.find_user('bob')['id'];other=auth.find_user('second-admin')['id']
    life.register(alice);life.register(bob)
    return admin,alice,bob,other


def ledger(uid, jid='ledger'):
    with auth.db() as con:
        con.execute("INSERT INTO ai_compute_jobs(id,user_id,kind,status,started_at,queue_job_id,usage_json,resource_source) VALUES(?,?,'demucs','done',1,?,?,'cgroup')",(jid,uid,'q-'+jid,json.dumps({'cpu_seconds':12.5})))
    with queue._db() as con:
        con.execute("INSERT INTO jobs(job_id,project_id,operation,state,rank,created_at,phase,message,actor_user_id) VALUES(?, 'p','stem-separation','completed',1,1,'done','',?)",('q-'+jid,uid))


def test_all_admins_immutable_even_with_multiple_admins(env):
    admin,_,_,other=env
    for target in (admin,other):
        for options in ({'active':False},{'role':'user'},{'active':False,'role':'user'}):
            with pytest.raises(ValueError):auth.update_user_admin(target,admin,**options)
        with pytest.raises(ValueError):life.retire(target,admin)
        with pytest.raises(ValueError):erasure.erase(target,admin,confirmed=True)
        assert auth.get_user(target)['role']=='admin' and auth.get_user(target)['active']


def test_immediate_erasure_removes_all_retained_copies_and_preserves_others(env):
    admin,alice,bob,_=env
    p=storage.create_project('Alice song',owner_user_id=alice)
    other=storage.create_project('Bob song',owner_user_id=bob)
    other.shared_with_user_ids=[alice];storage.save_project(other)
    ledger(alice);ledger(bob,'other')
    with auth.db() as con:
        con.execute('CREATE TABLE future_queue_detail(job_id TEXT, secret TEXT)')
        con.execute("INSERT INTO future_queue_detail VALUES('q-ledger','private')")
    life.retire(alice,admin)
    archive=life.listings()['archives'][0];path=life.root()/(archive['id']+'.zip')
    assert archive['expires_at']>__import__('time').time() and path.exists()
    with pytest.raises(ValueError):life.confirmation(admin,alice,{'confirm':False})
    assert life.confirmation(admin,alice,{'confirm':True})=={'done':True}
    assert not auth.get_user(alice) and auth.get_user(bob)
    assert not path.exists() and not storage.pdir(p.id).exists()
    assert storage.load_project(other.id).shared_with_user_ids==[]
    assert not life.jobs(alice) and life.jobs(bob)
    assert not life.listings()['archives'] and not life.listings()['sandboxes']
    with auth.db() as con:
        for table,col in (('account_identity_reservations','user_id'),('account_lifecycle','user_id'),('ai_compute_jobs','user_id'),('account_mail_outbox','user_id'),('account_audit','user_id')):
            assert not con.execute('SELECT 1 FROM '+table+' WHERE '+col+'=?',(alice,)).fetchone()  # noqa: S608 -- fixed test table allowlist
    assert life.availability('alice','alice@example.test')=={'username_available':True,'email_available':True}
    assert not list(life.root().glob('erase-*'))
    with auth.db() as con:assert not con.execute('SELECT 1 FROM future_queue_detail').fetchone()


def test_erasure_of_legacy_already_purged_account_removes_old_sandbox(env):
    admin,alice,_,_=env
    ledger(alice);life.retire(alice,admin);life.purge(alice,admin,True)
    assert not auth.get_user(alice) and life.listings()['sandboxes']
    # Simulate receipts left by a release predating publication-outbox cleanup.
    from app import ai_publish_outbox
    with ai_publish_outbox._open() as con:
        con.execute("INSERT INTO publications(job_id,project_id,audio_sha256,metadata,state,staged_at,published_at) VALUES('q-ledger','p','hash','{}','published',1,2)")
    artifact=queue._ROOT/'publication/q-ledger.wav';artifact.write_bytes(b'private')
    with auth.db() as con:
        con.execute('CREATE TABLE future_queue_detail(job_id TEXT, secret TEXT)')
        con.execute("INSERT INTO future_queue_detail VALUES('q-ledger','private')")
    assert erasure.erase(alice,admin,confirmed=True)['done']
    assert not life.listings()['archives'] and not life.listings()['sandboxes']
    assert not list(life.root().glob('*.sandbox')) and not artifact.exists()
    with ai_publish_outbox._open() as con:assert not con.execute('SELECT 1 FROM publications').fetchone()
    with auth.db() as con:assert not con.execute('SELECT 1 FROM future_queue_detail').fetchone()
    assert life.availability('alice','alice@example.test')['email_available']


def test_failed_file_erasure_remains_retryable_and_blocks_reactivation(env, monkeypatch):
    admin,alice,_,_=env
    p=storage.create_project('Song',owner_user_id=alice);life.retire(alice,admin)
    real=storage.delete_project
    monkeypatch.setattr(storage,'delete_project',lambda pid:None)
    with pytest.raises(OSError):erasure.erase(alice,admin,confirmed=True)
    assert auth.get_user(alice) and storage.pdir(p.id).exists()
    with pytest.raises(ValueError):auth.update_user_admin(alice,admin,active=True)
    monkeypatch.setattr(storage,'delete_project',real);erasure.resume()
    assert not auth.get_user(alice) and not list(life.root().glob('erase-*'))


def test_dump_selection_closure_and_roundtrip(env,tmp_path):
    admin,alice,bob,other=env
    first=storage.create_project('Alice A',owner_user_id=alice)
    second=storage.create_project('Alice B',owner_user_id=alice)
    excluded=storage.create_project('Bob private',owner_user_id=bob)
    ledger(alice);ledger(bob,'other')
    (storage.pdir(first.id)/'private.txt').write_text('project bytes')
    with auth.db() as con:con.execute("UPDATE smtp_config SET host='smtp.example.test' WHERE id=1")
    path=dump.create({'user_ids':[alice]})
    try:
        m=dump.inspect(path)
        assert set(m['user_ids'])=={admin,alice,other}
        assert set(m['project_ids'])=={first.id,second.id}
        assert not any(excluded.id in n for n in m['entries'])
        roots=[tmp_path/x for x in ('restored-data','restored-queue','restored-gpu')]
        assert dump.restore(path,data_dir=roots[0],queue_dir=roots[1],gpu_dir=roots[2],service_stopped=True)['done']
        assert (roots[0]/first.id/'private.txt').read_text()=='project bytes'
        assert (roots[0]/'.auth-secret').read_bytes()==auth.secret_path().read_bytes()
        with sqlite3.connect(roots[0]/'auth.sqlite3') as con:
            assert {r[0] for r in con.execute('SELECT username FROM users')}=={'admin','alice','second-admin'}
            assert [r[0] for r in con.execute('SELECT id FROM ai_compute_jobs')]==['ledger']
            assert con.execute('PRAGMA foreign_key_check').fetchone() is None
        with sqlite3.connect(roots[1]/'jobs.sqlite3') as con:assert [r[0] for r in con.execute('SELECT job_id FROM jobs')]==['q-ledger']
        with pytest.raises(ValueError,match='empty'):dump.restore(path,data_dir=roots[0],queue_dir=roots[1],gpu_dir=roots[2],service_stopped=True)
    finally:path.unlink()


def test_project_selection_includes_owner_but_not_other_owned_projects(env):
    _,alice,_,_=env
    p=storage.create_project('A',owner_user_id=alice);storage.create_project('B',owner_user_id=alice)
    _,uids,pids=dump.selection({'project_ids':[p.id]})
    assert alice in uids and pids=={p.id}


def test_config_only_and_all_users_dump_selections(env):
    admin,alice,bob,other=env
    p=storage.create_project('A',owner_user_id=alice)
    assert dump.selection({})[1:]==({admin,other},set())
    assert dump.selection({'all_users':True})[1:]==({admin,alice,bob,other},{p.id})


@pytest.mark.parametrize('bad',[{'user_ids':[True]},{'all_users':'yes'},{'user_ids':[999999]},{'project_ids':['../no']},{'extra':True}])
def test_invalid_selection(env,bad):
    with pytest.raises(ValueError):dump.selection(bad)


def test_active_jobs_and_project_symlinks_refuse_dump(env,tmp_path):
    _,alice,_,_=env;ledger(alice)
    with queue._db() as con:con.execute("UPDATE jobs SET state='running'")
    with pytest.raises(ValueError,match='job AI'):dump.create({})
    with queue._db() as con:con.execute("UPDATE jobs SET state='completed'")
    p=storage.create_project('A',owner_user_id=alice)
    (storage.pdir(p.id)/'outside').symlink_to(tmp_path/'secret')
    with pytest.raises(ValueError,match='symlink'):dump.create({'user_ids':[alice]})


@pytest.mark.parametrize('name',['../escape','/escape','projects/../../x','projects/abcd/C:/x','data/other','queue/unknown','projects/abcd/a\\b'])
def test_unsafe_paths_refused(name):
    with pytest.raises(ValueError):dump._safe_name(name)


def rewritten(source,target, change):
    with zipfile.ZipFile(source) as src,zipfile.ZipFile(target,'w') as out:
        for name in src.namelist():
            data=src.read(name)
            if name=='manifest.json':
                value=json.loads(data);change(value);data=json.dumps(value).encode()
            out.writestr(name,data)


def test_corrupt_checksum_and_unconfirmed_restore_write_nothing(env,tmp_path):
    path=dump.create({})
    try:
        bad=tmp_path/'bad.zip';rewritten(path,bad,lambda m:m['entries']['data/.auth-secret'].update(sha256='0'*64))
        with pytest.raises(ValueError,match='checksum'):dump.inspect(bad)
        roots=[tmp_path/x for x in ('a','b','c')]
        with pytest.raises(ValueError):dump.restore(bad,data_dir=roots[0],queue_dir=roots[1],gpu_dir=roots[2],service_stopped=True)
        with pytest.raises(ValueError):dump.restore(path,data_dir=roots[0],queue_dir=roots[1],gpu_dir=roots[2])
        assert not any(r.exists() for r in roots)
    finally:path.unlink()


def test_restore_rolls_back_if_publication_fails(env,tmp_path,monkeypatch):
    path=dump.create({});roots=[tmp_path/x for x in ('a','b','c')];real=dump.os.replace;calls=[]
    def fail(src,dst):
        calls.append(str(dst))
        if len(calls)==2:raise OSError('simulated disk failure')
        return real(src,dst)
    monkeypatch.setattr(dump.os,'replace',fail)
    try:
        with pytest.raises(OSError):dump.restore(path,data_dir=roots[0],queue_dir=roots[1],gpu_dir=roots[2],service_stopped=True)
        assert not any(r.exists() for r in roots)
        assert not list(tmp_path.glob('.mta-restore-*'))
    finally:path.unlink()


def test_dump_routes_admin_permissions_and_preview(env,monkeypatch):
    admin,alice,_,_=env
    monkeypatch.setattr(auth,'session_user',lambda r: {'id':admin if r.headers.get('x-role')=='admin' else alice,'role':r.headers['x-role']} if r.headers.get('x-role') else None)
    app=FastAPI();admin_dump_routes.register_routes(app);client=TestClient(app)
    for route in ('/api/admin/application-dump/catalog','/docs/admin/application-dump'):
        assert client.get(route).status_code==401
        assert client.get(route,headers={'x-role':'user'}).status_code==403
    headers={'x-role':'admin'}
    assert client.post('/api/admin/application-dump/preview',headers=headers,json={'user_ids':[alice]}).json()['users']==3
    response=client.post('/api/admin/application-dump',headers=headers,json={'user_ids':[alice]})
    assert response.status_code==200 and response.content[:2]==b'PK'
    result=client.post('/api/admin/application-dump/restore-preview',headers=headers,files={'file':('dump.zip',response.content,'application/zip')})
    assert result.status_code==200 and result.json()['valid']
    assert client.post('/api/admin/application-dump/restore-preview',headers=headers,files={'file':('bad.zip',b'no')}).status_code==422


def test_health_probes_remain_available_during_dump_maintenance(env,monkeypatch):
    from app import main
    admin=auth.get_user(env[0])
    monkeypatch.setattr(main,'NATIVE_SINGLE_USER',False)
    monkeypatch.setattr(main,'session_user',lambda request:admin)
    client=TestClient(main.app)
    monkeypatch.setattr(dump,'_BUSY',True)
    assert client.get('/api/admin/users').status_code==503
    assert client.get('/health').status_code==200
    assert client.get('/api/health').status_code==200
    assert dump._ACTIVE==0


def test_central_ledger_cannot_advance_past_outbox_snapshot(env,monkeypatch):
    original=dump._snapshot;checks=[]
    def guarded(source,target):
        if source==auth.db_path():
            with sqlite3.connect(auth.db_path(),timeout=.01) as writer:
                with pytest.raises(sqlite3.OperationalError,match='locked'):
                    writer.execute('BEGIN IMMEDIATE')
            checks.append(True)
        return original(source,target)
    monkeypatch.setattr(dump,'_snapshot',guarded)
    path=dump.create({})
    try:
        assert checks==[True]
        with auth.db() as con:con.execute('BEGIN IMMEDIATE')
    finally:path.unlink()


def test_file_based_global_settings_are_in_dump_and_restore(env,tmp_path,monkeypatch):
    from app import diagnostic_bundle,model_updater
    source=tmp_path/'settings';source.mkdir()
    monkeypatch.setattr(diagnostic_bundle,'BASE',source)
    monkeypatch.setattr(model_updater,'BLACKLIST_FILE',source/'blacklist.json')
    monkeypatch.setattr(model_updater,'CATALOG_FILE',source/'catalog.json')
    values={'enabled.json':{'enabled':True},'blacklist.json':['blocked-model'],'catalog.json':{'models':[]}}
    for name,value in values.items():(source/name).write_text(json.dumps(value))
    path=dump.create({});roots=[tmp_path/x for x in ('restore-data','restore-queue','restore-gpu')]
    try:
        dump.restore(path,data_dir=roots[0],queue_dir=roots[1],gpu_dir=roots[2],service_stopped=True)
        assert json.loads((roots[0]/'.diagnostics/enabled.json').read_text())==values['enabled.json']
        for name in ('blacklist.json','catalog.json'):
            assert json.loads((roots[0]/'.model-settings'/name).read_text())==values[name]
    finally:path.unlink()
