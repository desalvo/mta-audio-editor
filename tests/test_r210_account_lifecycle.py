"""Account ownership, mandatory MFA, retirement, quarantine and expiry regressions."""
import json
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app import auth, account_lifecycle as life, account_mfa as mfa, account_routes as routes
from app import ai_arranger_runtime as queue, storage, ai_billing as billing


@pytest.fixture
def env(tmp_path,monkeypatch):
    monkeypatch.setattr(auth,'DATA_ROOT',tmp_path/'auth');monkeypatch.setattr(queue,'_ROOT',tmp_path/'queue');monkeypatch.setattr(storage,'ROOT',tmp_path/'projects')
    storage.ROOT.mkdir()
    monkeypatch.setenv('MTA_ADMIN_PASSWORD','administrator-password');monkeypatch.setenv('MTA_PUBLIC_URL','https://mta.example.test')
    auth.init_auth_db();life.settings()
    monkeypatch.setattr(auth,'send_mail',lambda *a,**kw:None)
    admin=auth.find_user('admin')
    with auth.db() as con:
        con.execute("INSERT INTO users(username,email,password_hash,active,email_confirmed,role,created_at,updated_at) VALUES('person','person@example.test',?,1,1,'user',1,1)",(auth._password_hash('password-long-enough'),))
    user=auth.find_user('person');life.register(user['id'])
    return admin['id'],user['id']


def test_email_mfa_onboarding_precedes_admin_approval_and_blocks_login_without_otp(env,monkeypatch):
    admin,_=env
    user,token=auth.register_user('new-user','new@example.test','New','password-long-enough',require_second_factor=True,mfa_method='email')
    assert life.info(user['id'])['state']=='enrolling'
    assert auth.confirm_email(token)
    with pytest.raises(ValueError,match='secondo fattore'):auth.update_user_admin(user['id'],admin,active=True)
    app=FastAPI();routes.register_routes(app);client=TestClient(app)
    url=routes.enrollment(user['id']);enroll_token=url.split('=',1)[1]
    assert client.get(url).status_code==200
    monkeypatch.setattr(auth,'get_smtp_config',lambda:{'host':'smtp','from_email':'mta@example.test'})
    monkeypatch.setattr(mfa.secrets,'randbelow',lambda size:123456)
    assert client.post('/registration-security',data={'token':enroll_token,'action':'send'}).status_code==200
    assert client.post('/registration-security',data={'token':enroll_token,'action':'verify','code':'123456'}).status_code==200
    assert life.info(user['id'])['state']=='pending'
    auth.update_user_admin(user['id'],admin,active=True)
    assert auth.authenticate('new-user','password-long-enough')[0] is None
    mfa.send(user['id'],'login')
    assert auth.authenticate('new-user','password-long-enough','123456')[0]['id']==user['id']
    assert auth.authenticate('new-user','password-long-enough','123456')[0] is None


def test_totp_onboarding_guard_and_notification_outbox(env):
    admin,_=env
    user,token=auth.register_user('auth-app','app@example.test','App','password-long-enough',require_second_factor=True,mfa_method='totp')
    auth.confirm_email(token)
    with pytest.raises(ValueError):auth.update_user_admin(user['id'],admin,active=True)
    with auth.db() as con:
        con.execute('UPDATE users SET totp_enabled=1 WHERE id=?',(user['id'],));con.execute("UPDATE account_lifecycle SET state='pending' WHERE user_id=?",(user['id'],))
    life.ready(user['id'])
    with auth.db() as con:
        messages=[r['subject'] for r in con.execute('SELECT * FROM account_mail_outbox WHERE user_id=?',(user['id'],))]
    assert any('attesa' in s for s in messages) and any('Richiesta' in s for s in messages)


def test_retirement_preserves_identity_accounting_revokes_tokens_and_exports_projects(env):
    admin,uid=env
    from app.ai_access import issue,authenticate
    credential=issue(uid,'Desktop')['token']
    project=storage.create_project('Song','DAW',owner_user_id=uid)
    with auth.db() as con:
        billing._init(con);con.execute("INSERT INTO ai_compute_jobs(id,user_id,kind,status,started_at) VALUES('ledger',?,'lyrics','done',1)",(uid,))
    result=life.retire(uid,uid)
    assert result['state']=='deleted' and not auth.get_user(uid)['active']
    assert authenticate(credential) is None
    assert not life.availability('person','PERSON@example.test')['email_available']
    with auth.db() as con:assert con.execute('SELECT 1 FROM ai_compute_jobs WHERE user_id=?',(uid,)).fetchone()
    archive=life.listings()['archives'][0]
    app=FastAPI();routes.register_routes(app);client=TestClient(app)
    response=client.get(archive['url']);assert response.status_code==200 and response.content[:2]==b'PK'
    import io,zipfile
    with zipfile.ZipFile(io.BytesIO(response.content)) as z:assert project.id+'.maeproj' in z.namelist()
    life.cleanup(result['project_deadline']+1)
    assert not storage.pdir(project.id).exists()
    assert client.get(archive['url']).status_code==404


def test_reactivation_requires_email_then_admin_and_does_not_restore_old_tokens(env):
    admin,uid=env
    life.retire(uid,uid)
    token=auth._create_email_token(uid,'reactivation')
    assert life.confirm_reactivation(token)
    assert not life.confirm_reactivation(token)
    assert life.info(uid)['state']=='reactivation_pending'
    auth.update_user_admin(uid,admin,active=True)
    assert auth.get_user(uid)['active'] and life.info(uid)['state']=='active'
    assert life.listings()['archives'][0]['url'] is None


def test_total_privacy_delete_requires_two_bound_confirmations_and_expires_sandbox(env):
    admin,uid=env
    with auth.db() as con:
        billing._init(con);con.execute("INSERT INTO ai_compute_jobs(id,user_id,kind,status,started_at) VALUES('ledger',?,'stems','done',1)",(uid,))
        con.execute('CREATE TABLE future_meter(id INTEGER PRIMARY KEY,job_id TEXT,secret TEXT)')
        con.execute("INSERT INTO future_meter(job_id,secret) VALUES('ledger','private')")
    life.retire(uid,uid)
    body={'username':'person','privacy':True}
    first=life.confirmation(admin,uid,body);assert first['stage']==1 and auth.get_user(uid)
    with pytest.raises(ValueError):life.confirmation(admin+1,uid,{**body,'confirmation':first['confirmation']})
    second=life.confirmation(admin,uid,{**body,'confirmation':first['confirmation']});assert second['stage']==2 and auth.get_user(uid)
    assert life.confirmation(admin,uid,{**body,'confirmation':second['confirmation']})['done']
    assert auth.get_user(uid) is None and not life.availability('person','person@example.test')['username_available']
    boxes=life.listings()['sandboxes'];assert len(boxes)==1
    payload=json.loads(auth._open((life.root()/(boxes[0]['id']+'.sandbox')).read_text()))
    assert payload['rows']['ai_compute_jobs'][0]['id']=='ledger'
    assert payload['rows']['future_meter'][0]['secret']=='private'
    with auth.db() as con:
        assert not con.execute('SELECT * FROM ai_compute_jobs').fetchone()
        assert not con.execute('SELECT * FROM future_meter').fetchone()
    life.cleanup(boxes[0]['expires_at']+1)
    assert not list(life.root().glob('*.sandbox'))


def test_non_privacy_total_delete_refuses_billing_and_admin_self_delete(env):
    admin,uid=env
    with pytest.raises(ValueError):life.retire(admin,admin)
    life.retire(uid,uid)
    with auth.db() as con:
        billing._init(con);con.execute("INSERT INTO ai_compute_jobs(id,user_id,kind,status,started_at) VALUES('ledger',?,'stems','done',1)",(uid,))
    with pytest.raises(ValueError,match='contabili'):life.confirmation(admin,uid,{'username':'person','privacy':False})


@pytest.mark.parametrize('settings',[{'project_days':0},{'sandbox_days':True},{'sandbox_days':3651},{'extra':1}])
def test_retention_configuration_validation(env,settings):
    with pytest.raises(ValueError):life.settings(settings)
    assert life.settings()=={'project_days':60,'sandbox_days':365}


def test_email_otp_attempt_limits_cooldown_and_expiry(env,monkeypatch):
    _,uid=env
    monkeypatch.setattr(auth,'get_smtp_config',lambda:{'host':'smtp','from_email':'mta@example.test'})
    monkeypatch.setattr(mfa.secrets,'randbelow',lambda size:123456)
    mfa.send(uid,'login')
    with pytest.raises(ValueError,match='60'):mfa.send(uid,'login')
    for _ in range(5):assert not mfa.verify(uid,'login','000000')
    assert not mfa.verify(uid,'login','123456')
    with auth.db() as con:con.execute('UPDATE account_email_mfa SET sent_at=0')
    mfa.send(uid,'login')
    with auth.db() as con:con.execute('UPDATE account_email_mfa SET expires=0')
    assert not mfa.verify(uid,'login','123456')


def test_retention_api_admin_only_and_self_deletion_forbidden_to_admin(env,monkeypatch):
    admin,uid=env
    monkeypatch.setattr(auth,'session_user',lambda request:{'id':admin if request.headers.get('x-role')=='admin' else uid,'username':'admin' if request.headers.get('x-role')=='admin' else 'person','role':request.headers['x-role']} if request.headers.get('x-role') else None)
    app=FastAPI();routes.register_routes(app);client=TestClient(app)
    assert client.get('/api/admin/account-lifecycle').status_code==401
    assert client.get('/api/admin/account-lifecycle',headers={'x-role':'user'}).status_code==403
    assert client.post('/api/account/delete-request',headers={'x-role':'admin'},json={'username':'admin','confirm':True}).status_code==403
    assert client.get('/api/admin/account-lifecycle',headers={'x-role':'admin'}).status_code==200


def test_email_change_reserves_old_and_pending_email(env):
    _,uid=env
    auth.update_profile(uid,email='changed@example.test')
    assert not life.availability('unused','person@example.test')['email_available']
    assert not life.availability('unused','changed@example.test')['email_available']


def test_failed_purge_removes_uncommitted_sandbox(env,monkeypatch):
    admin,uid=env;life.retire(uid,uid)
    def fail(*args):raise RuntimeError('simulated schema failure')
    monkeypatch.setattr(life,'_rows_for_user',fail)
    with pytest.raises(RuntimeError):life.purge(uid,admin,True)
    assert auth.get_user(uid) and not list(life.root().glob('*.sandbox'))


def test_quarantine_removes_settlement_outbox_and_credentials(env):
    from app import ai_billing_outbox
    admin,uid=env
    with auth.db() as con:
        billing._init(con);con.execute("INSERT INTO ai_compute_jobs(id,user_id,kind,status,started_at) VALUES('ledger',?,'stems','done',1)",(uid,))
    with queue._db() as con:con.execute("INSERT INTO jobs(job_id,project_id,operation,state,rank,created_at,phase,message,actor_user_id) VALUES('queuejob','p','stems','completed',1,1,'done','',?)",(uid,))
    ai_billing_outbox.register('queuejob','ledger','done')
    life.retire(uid,uid);life.purge(uid,admin,True)
    with ai_billing_outbox._db() as con:assert not con.execute('SELECT * FROM deliveries').fetchone()
    box=life.listings()['sandboxes'][0]
    blob=json.loads(auth._open((life.root()/(box['id']+'.sandbox')).read_text()))
    assert blob['billing_outbox'][0]['billing_job_id']=='ledger'
    assert 'password_hash' not in blob['rows']['users'][0]
    assert not life.jobs(uid)


def test_repeated_retirement_reactivation_revokes_each_archive_without_token_collision(env):
    admin,uid=env
    for _ in range(2):
        life.retire(uid,uid)
        token=auth._create_email_token(uid,'reactivation');assert life.confirm_reactivation(token)
        auth.update_user_admin(uid,admin,active=True)
    rows=life.listings()['archives']
    assert len(rows)==2 and all(a['url'] is None for a in rows)
