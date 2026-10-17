"""Native account authorization, user/token attribution and durable lifecycle mail."""
import json
import time
import uuid
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from app import auth,ai_access,ai_device_auth as device,ai_notifications as mail,ai_billing as billing
from app import ai_arranger_runtime as queue, native_ai_account as account
from app.ai_usage_reporting import snapshot


@pytest.fixture
def env(tmp_path,monkeypatch):
    monkeypatch.setattr(auth,'DATA_ROOT',tmp_path/'auth')
    monkeypatch.setattr(queue,'_ROOT',tmp_path/'queue')
    monkeypatch.setenv('MTA_NATIVE_AI_CONFIG',str(tmp_path/'native'/'workers.json'))
    monkeypatch.setenv('MTA_NATIVE_AI_ACCOUNT',str(tmp_path/'native'/'account.json'))
    monkeypatch.delenv('MTA_NATIVE_SINGLE_USER',raising=False)
    monkeypatch.delenv('MTA_ALLOW_INSECURE_NO_AUTH',raising=False)
    auth.init_auth_db()
    with auth.db() as con:
        for name in ('first','second'):
            con.execute('INSERT INTO users(username,email,password_hash,active,email_confirmed,role,created_at,updated_at) VALUES(?,?,?,1,1,\'user\',1,1)',(name,name+'@example.com','unused'))
        users=[dict(r) for r in con.execute("SELECT * FROM users WHERE username IN ('first','second') ORDER BY username")]
    monkeypatch.setattr(auth,'get_smtp_config',lambda:{'host':'smtp.example.com','from_email':'mta@example.com'})
    from app import ai_billing_profiles
    monkeypatch.setattr(ai_billing_profiles,'suggested_prices',lambda:{'model_version':'test','cpu_model':'test','gpu_model':None,'suggested_micro_per_unit':{'cpu_seconds':0,'gpu_slot_seconds_estimated':0,'disk_gb_hours':0}})
    return users


def test_device_approval_creates_one_active_token_per_user_instance(env,monkeypatch):
    user=env[0];instance='a'*32
    first=device.begin(instance,'My Mac')
    assert device.poll(first['device_code'])['state']=='pending'
    device.approve(user,first['user_code'])
    with auth.db() as con:con.execute('UPDATE ai_device_requests SET last_poll=0')
    approved=device.poll(first['device_code']);token=approved['token']
    assert ai_access.authenticate(token)['user_id']==user['id']
    another=device.begin(instance,'My Mac');device.approve(user,another['user_code'])
    assert ai_access.authenticate(token) is None
    third=device.begin('b'*32,'Windows');device.approve(user,third['user_code'])
    active=[t for t in ai_access.list_tokens(user['id']) if not t['revoked_at']]
    assert len(active)==2 and len({t['client_id'] for t in active})==2
    with auth.db() as con:
        stored=json.dumps([dict(r) for r in con.execute('SELECT * FROM ai_device_requests')])
        assert token not in stored and first['device_code'] not in stored


@pytest.mark.parametrize('active,verified',[(False,True),(True,False),(False,False)])
def test_device_rejects_inactive_unverified_accounts(env,active,verified):
    request=device.begin('c'*32)
    with pytest.raises(ValueError):device.approve({**env[0],'active':active,'email_confirmed':verified},request['user_code'])
    assert device.poll(request['device_code'])['state']=='pending'


def test_device_denial_expiry_and_poll_throttle(env,monkeypatch):
    request=device.begin('c'*32)
    device.approve(env[0],request['user_code'],allow=False)
    assert device.poll(request['device_code'])['state']=='denied'
    assert device.poll(request['device_code'])['state']=='slow_down'
    with auth.db() as con:con.execute('UPDATE ai_device_requests SET expires_at=0')
    assert device.poll(request['device_code'])['state']=='expired'
    with pytest.raises(ValueError):device.approve(env[0],request['user_code'])


def test_native_enrollment_keeps_secret_private_and_shares_all_engine_tokens(env,monkeypatch):
    def request(server,path,data):
        return device.begin(data['client_id'],data['label']) if path.endswith('/start') else device.poll(data['device_code'])
    monkeypatch.setattr(account,'_request',request)
    state=account.begin('https://mta.example.com')
    assert 'token' not in state and 'device_code' not in state
    device.approve(env[0],state['user_code'])
    connected=account.poll();assert connected['connected'] is True
    cfg=account.credentials();assert cfg['token'] not in json.dumps(connected)
    assert account._file().stat().st_mode&0o777==0o600
    from app import native_ai_routing as routing
    for kind in routing.KINDS:routing.configure(kind,'remote')
    configs=routing._read()['workers']
    assert {x['token'] for x in configs.values()}=={cfg['token']}
    assert {x['url'] for x in configs.values()}=={'https://mta.example.com'}
    assert cfg['token'] not in json.dumps(routing.public_settings())


@pytest.mark.parametrize('url',['http://mta.example.com','file:///tmp/test','https://user:password@example.com','https://example.com/?token=x','https://example.com/other'])
def test_native_enrollment_rejects_unsafe_urls(env,url):
    with pytest.raises(ValueError):account.begin(url)
    assert not account._file().exists()


def test_account_reports_combine_tokens_without_cross_user_data_or_gpu_charge(env):
    first,second=env;tokens=[ai_access.issue(first['id'],label) for label in ('Mac','Windows')]
    billing.set_price('cpu_seconds',100,valid_from=1)
    now=int(time.time())
    for token,seconds in zip(tokens,[2,3]):
        jid=billing.create_job(first['id'],'whisper',token['id'],started_at=now-10)
        billing.finish_job(jid,'done',{'cpu_seconds':seconds},source='cgroup',finished_at=now-1)
    jid=billing.create_job(second['id'],'whisper',started_at=now-10)
    billing.finish_job(jid,'done',{'cpu_seconds':999},source='cgroup',finished_at=now-1)
    report=snapshot(first['id'],now-20,now+1)
    assert report['jobs']==2 and report['usage']=={'cpu_seconds':5}
    assert len(report['by_token'])==2 and report['cost_micro']==500 and report['amount_micro']==0
    billing.set_user_billing_enabled(first['id'],True)
    assert snapshot(first['id'],now-20,now+1)['amount_micro']==500
    assert snapshot(first['id'],now-20,now+1,token_id=tokens[0]['id'])['usage']=={'cpu_seconds':2}
    with pytest.raises(ValueError):snapshot(first['id'],0,float('nan'))


def add_queue(user,state='completed',**extra):
    now=time.time();jid=uuid.uuid4().hex
    values=dict(job_id=jid,project_id='p',operation='arranger',state=state,rank=1,created_at=now,
        started_at=now,completed_at=now+1 if state!='running' else None,phase=state,message='private prompt DO_NOT_MAIL',actor_user_id=user['id'],**extra)
    with queue._db() as con:
        columns=','.join(values)
        con.execute('INSERT INTO jobs('+columns+') VALUES('+','.join('?' for _ in values)+')',tuple(values.values()))
    return jid


def test_start_terminal_emails_html_logo_zero_cost_and_diagnostic_only_gpu(env,monkeypatch):
    mail.collect();add_queue(env[0],gpu_seconds_estimated=7,cpu_seconds_estimated=8)
    assert mail.collect()['queued']==2
    assert mail.collect()['queued']==0
    messages=[]
    monkeypatch.setattr(auth,'send_mail',lambda *args,**kwargs:messages.append((args,kwargs)))
    assert mail.deliver()['sent']==2
    assert all(m[0][0]==[env[0]['email']] for m in messages)
    assert 'Avviato' in messages[0][0][1] and 'Completato' in messages[1][0][1]
    assert all('cid:mta-logo' in m[0][3] and '0.3.0-r210' in m[0][3] for m in messages)
    assert all(m[1]['inline_image'].startswith(b'\x89PNG') for m in messages)
    assert all('0.000000' in m[0][3] for m in messages)
    assert 'DO_NOT_MAIL' not in repr(messages)
    assert 'gpu_seconds_estimated' in messages[1][0][3]
    assert len({m[1]['message_id'] for m in messages})==2
    assert mail.deliver()['sent']==0
    assert snapshot(env[0]['id'],0,time.time()+10)['diagnostic']=={'cpu_seconds_estimated':8,'gpu_seconds_estimated':7}


def test_smtp_disabled_does_not_enqueue_or_send_old_jobs(env,monkeypatch):
    monkeypatch.setattr(auth,'get_smtp_config',lambda:{'host':'','from_email':''})
    add_queue(env[0]);assert mail.collect()['queued']==0
    assert mail.deliver()['sent']==0
    monkeypatch.setattr(auth,'get_smtp_config',lambda:{'host':'smtp','from_email':'mta@example.com'})
    # Existing terminal job predates activation; no historical start flood.
    with queue._db() as con:con.execute('UPDATE jobs SET completed_at=created_at')
    assert mail.collect()['queued']==0


def test_mail_retry_preserves_terminal_order_and_never_changes_job(env,monkeypatch):
    mail.collect();jid=add_queue(env[0])
    mail.collect()
    monkeypatch.setattr(auth,'send_mail',lambda *a,**k:(_ for _ in ()).throw(OSError('private-password')))
    assert mail.deliver()['failed']==1
    with auth.db() as con:
        rows=[dict(r) for r in con.execute('SELECT * FROM ai_mail_events')]
        assert len(rows)==2 and all('private-password' not in str(r) for r in rows)
        con.execute('UPDATE ai_mail_events SET due=0')
    assert queue.get(jid)['state']=='completed'
    messages=[];monkeypatch.setattr(auth,'send_mail',lambda *a,**k:messages.append(a))
    assert mail.deliver()['sent']==2
    assert 'Avviato' in messages[0][1]


def test_digest_uses_completion_window_so_long_jobs_are_not_lost(env,monkeypatch):
    user=env[0];mail.collect();mail.set_preferences(user['id'],{'cadence':'day','language':'en'})
    now=int(time.time());start=now-200000
    jid=billing.create_job(user['id'],'whisper',started_at=start)
    billing.finish_job(jid,'done',{'cpu_seconds':12},source='cgroup',finished_at=now-1)
    with auth.db() as con:con.execute('UPDATE ai_mail_preferences SET cursor=? WHERE user_id=?',(now-90000,user['id']))
    mail.collect();mail.collect()
    with auth.db() as con:
        summaries=[json.loads(r[0]) for r in con.execute("SELECT payload FROM ai_mail_events WHERE id LIKE 'summary:%'")]
    assert len(summaries)==1
    assert summaries[0]['report']['usage']=={'cpu_seconds':12}
    assert summaries[0]['report']['interval_basis']=='completion'
    assert mail.preferences(user['id'])['effective_cadence']=='day'
    mail.set_preferences(user['id'],{'cadence':None,'language':'en'});mail.set_default('month')
    assert mail.preferences(user['id'])['effective_cadence']=='month'


def test_device_http_csrf_auth_and_personal_admin_preferences_acl(env,monkeypatch):
    from app import main
    identity=[None]
    monkeypatch.setattr(main,'session_user',lambda _:identity[0]);monkeypatch.setattr(auth,'session_user',lambda _:identity[0])
    monkeypatch.setattr(main,'check_basic_auth',lambda _:False)
    client=TestClient(main.app);headers={'x-mta-request':'1'}
    body={'client_id':'f'*32}
    assert client.post('/api/ai-device/start',json=body).status_code==403
    request=client.post('/api/ai-device/start',json=body,headers=headers).json()
    assert request['verification_uri'].startswith('/ai-device?code=')
    assert client.get('/ai-device?code='+request['user_code']).status_code==200
    assert client.post('/api/account/ai-device/approve',json={'code':request['user_code'],'allow':True},headers=headers).status_code==401
    identity[0]=env[0]
    assert client.put('/api/account/ai-notifications',json={'cadence':'day'},headers=headers).status_code==200
    assert client.put('/api/admin/ai-notifications',json={'cadence':'month'},headers=headers).status_code==403
    assert client.post('/api/account/ai-device/approve',json={'code':request['user_code'],'allow':True},headers=headers).status_code==200
    assert client.get('/api/account/ai-resources?user_id='+str(env[1]['id'])).json()['user_id']==env[0]['id']
    assert client.get('/api/admin/ai-resources?user_id='+str(env[1]['id'])).status_code==403


def test_mime_email_has_embedded_logo_and_stable_message_id(env,monkeypatch):
    sent=[]
    class SMTP:
        def send_message(self,msg):sent.append(msg)
        def quit(self):pass
    monkeypatch.setattr(auth,'_smtp_full',lambda:{'host':'smtp','from_email':'mta@example.com','from_name':'MTA','username':''})
    monkeypatch.setattr(auth,'_smtp_client',lambda cfg:SMTP())
    auth.send_mail(['user@example.com'],'Subject','Plain','<img src="cid:mta-logo">',inline_image=(Path(mail.__file__).parent/'static/mail-logo.png').read_bytes(),message_id='<stable@mta.local>')
    msg=sent[0]
    assert msg['Message-ID']=='<stable@mta.local>'
    assert any(part.get_content_type()=='text/html' for part in msg.walk())
    assert any(part['Content-ID']=='<mta-logo>' for part in msg.walk())


def test_remote_audio_exec_leaves_event_loop_responsive_and_attributes_same_token(env,monkeypatch):
    import asyncio
    import base64
    import io
    import wave
    from fastapi import FastAPI
    import httpx
    from app import ai_billing_routes as routes,ai_metering_agent
    token=ai_access.issue(env[0]['id'],'Native instance')
    stream=io.BytesIO()
    with wave.open(stream,'wb') as wav:
        wav.setnchannels(1);wav.setsampwidth(2);wav.setframerate(44100);wav.writeframes(bytes(882))
    audio=stream.getvalue();identities=[]
    import threading
    started=threading.Event();released=threading.Event();finished=threading.Event()
    def work(uid,kind,plan,**kw):
        identities.append((uid,kind,kw['token_id']))
        started.set()
        assert released.wait(2),'event loop was blocked by synchronous inference'
        finished.set()
        jid=billing.create_job(uid,kind,kw['token_id'])
        billing.finish_job(jid,'done',{'cpu_seconds':1},source='cgroup')
        return audio,{'job_id':jid,'media_type':'audio/wav'}
    monkeypatch.setattr(ai_metering_agent,'execute_registered_worker',work)
    from app import ai_worker_registry
    monkeypatch.setattr(ai_worker_registry,'resolve_worker',lambda kind: '/trusted/operator/worker')
    server=FastAPI();server.include_router(routes.router)
    @server.get('/probe')
    async def probe():return {'ok':True}
    async def run():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=server),base_url='https://mta.example.com') as client:
            observed=[]
            async def observer():
                for _ in range(1000):
                    if started.is_set():break
                    await asyncio.sleep(.001)
                observed.append(finished.is_set())
                assert (await client.get('/probe')).status_code==200
                released.set()
            headers={'Authorization':'Bearer '+token['token'],'Content-Type':'audio/wav'}
            await asyncio.gather(client.post('/api/ai-jobs/execute-audio/whisper',headers=headers,content=audio),observer())
            assert observed==[False]  # Probe ran while the worker was still running.
            options=base64.urlsafe_b64encode(json.dumps({'model_id':'ace-step-1.5'}).encode()).decode().rstrip('=')
            result=await client.post('/api/ai-jobs/execute-audio/ace-step',headers={**headers,'X-MTA-AI-Options':options},content=audio)
            assert result.status_code==200
    asyncio.run(run())
    assert [r[2] for r in identities]==[token['id'],token['id']]
    assert snapshot(env[0]['id'],0,time.time()+2)['jobs']==2


def test_diagnostics_are_persistent_separate_and_never_increase_billing(env):
    from app.ai_compute_diagnostics import store
    jid=billing.create_job(env[0]['id'],'ace-step')
    billing.finish_job(jid,'done',{'cpu_seconds':2},source='cgroup')
    store(jid,{'gpu_seconds_estimated':10,'gpu_seconds':999,'cpu_seconds_estimated':4})
    report=snapshot(env[0]['id'],0,time.time()+1)
    assert report['usage']=={'cpu_seconds':2}
    assert report['diagnostic']=={'gpu_seconds_estimated':10,'cpu_seconds_estimated':4}
    assert report['amount_micro']==0


def test_recovery_from_interrupted_to_completed_emails_the_new_terminal_state(env,monkeypatch):
    mail.collect();jid=add_queue(env[0],state='interrupted');mail.collect()
    messages=[];monkeypatch.setattr(auth,'send_mail',lambda *a,**k:messages.append(a))
    mail.deliver()
    with queue._db() as con:con.execute("UPDATE jobs SET state='completed' WHERE job_id=?",(jid,))
    assert mail.collect()['queued']==1
    assert mail.deliver()['sent']==1
    assert 'Completato' in messages[-1][1]
