"""Admin search/exclusions, social credentials and real SMTP submission regressions."""
import json
import time
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app import auth, ai_billing as billing, ai_queue_admin as admin, ai_arranger_runtime as queue
from app import social_settings as social


@pytest.fixture
def env(tmp_path,monkeypatch):
    monkeypatch.setattr(auth,'DATA_ROOT',tmp_path/'auth')
    monkeypatch.setattr(queue,'_ROOT',tmp_path/'queue')
    monkeypatch.setenv('MTA_ADMIN_PASSWORD','administrator-password')
    monkeypatch.setenv('MTA_ADMIN_EMAIL','admin@example.test')
    monkeypatch.setenv('MTA_PUBLIC_URL','https://mta.example.test')
    auth.init_auth_db();uid=auth.find_user('admin')['id']
    with auth.db() as con:admin.tables(con)
    return uid


def seed(uid,count=45):
    stamp=int(time.time())-100
    with queue._db() as con:
        for n in range(count):
            con.execute('INSERT INTO jobs(job_id,project_id,operation,state,rank,created_at,started_at,completed_at,phase,message,actor_user_id) VALUES(?,?,?,?,?,?,?,?,?,?,?)',
              (f'job-{n:03d}','project-a','worker:lyrics' if n%2 else 'worker:stems','completed',n,stamp+n,stamp+n,stamp+n+1,'done','',uid))
    with auth.db() as con:
        for n in range(count):
            con.execute('INSERT INTO ai_compute_jobs(id,user_id,kind,status,started_at,finished_at,usage_json,resource_source,queue_job_id) VALUES(?,?,?,?,?,?,?,?,?)',
              (f'ledger-{n:03d}',uid,'lyrics','done',stamp+n,stamp+n+1,'{"cpu_seconds":2}','cgroup',f'job-{n:03d}'))
    return stamp


def test_queue_search_and_stable_pagination_over_500(env):
    seed(env,550)
    result=admin.query();assert result['total']==550 and len(result['jobs'])==20 and result['pages']==28
    assert not {j['job_id'] for j in result['jobs']}&{j['job_id'] for j in admin.query(page=2)['jobs']}
    assert admin.query('worker:stems',page_size=100)['total']==275
    assert admin.query('%')['total']==0
    assert admin.query('job-001')['jobs'][0]['job_id']=='job-001'
    assert admin.query(page=999)['page']==28


@pytest.mark.parametrize('args',[{'page_size':9},{'page_size':101},{'page':0},{'state':'bad'},{'visibility':'bad'}])
def test_invalid_search(env,args):
    with pytest.raises(ValueError):admin.query(**args)


def action(ids,which='disable',**kw):
    return {'ids':ids,'action':which,'reason':'Duplicate test run','filters':{},**kw}


def test_disable_restore_delete_really_excludes_accounting_and_token_totals(env):
    stamp=seed(env,3)
    from app.ai_usage_reporting import snapshot
    before=snapshot(env,stamp-1,stamp+10);assert before['jobs']==3
    preview=admin.manage(env,action(['job-000'],preview=True));assert preview['preview']
    assert snapshot(env,stamp-1,stamp+10)['jobs']==3
    admin.manage(env,action(['job-000']))
    assert snapshot(env,stamp-1,stamp+10)['jobs']==2
    report=billing.report('day',user_id=env)
    assert sum(r['jobs'] for r in report['rows'])==2
    assert sum(r['resources'].get('cpu_seconds',0) for r in report['rows'])==4
    assert admin.query(visibility='disabled')['total']==1
    admin.manage(env,action(['job-000'],'enable'));assert snapshot(env,stamp-1,stamp+10)['jobs']==3
    admin.manage(env,action(['job-000'],'delete'))
    assert admin.query()['total']==2 and admin.query(visibility='deleted')['total']==1
    assert snapshot(env,stamp-1,stamp+10)['jobs']==2
    with pytest.raises(ValueError,match='ripristinate'):admin.manage(env,action(['job-000'],'enable',filters={'visibility':'all'}))
    with auth.db() as con:
        assert con.execute('SELECT usage_json FROM ai_compute_jobs WHERE id="ledger-000"').fetchone()[0]=='{"cpu_seconds":2}'
        assert con.execute('SELECT count(*) FROM ai_job_disposition_audit').fetchone()[0]==3


def test_bulk_is_atomic_and_rechecks_search_and_closed_invoices(env):
    stamp=seed(env,3)
    with pytest.raises(ValueError,match='ricerca corrente'):admin.manage(env,action(['job-000'],filters={'search':'worker:lyrics'}))
    with auth.db() as con:
        con.execute('INSERT INTO ai_billing_periods(user_id,start_ts,end_ts,currency,total_micro,snapshot_json,created_at) VALUES(?,?,?,?,?,?,?)',(env,stamp+1,stamp+2,'EUR',99,'{"immutable":true}',stamp+3))
    with pytest.raises(ValueError,match='fatturato'):admin.manage(env,action(['job-000','job-001']))
    with auth.db() as con:
        assert con.execute('SELECT count(*) FROM ai_job_dispositions').fetchone()[0]==0
        assert con.execute('SELECT snapshot_json FROM ai_billing_periods').fetchone()[0]=='{"immutable":true}'


def test_active_job_cannot_be_excluded(env,monkeypatch):
    # This fixture intentionally has no persisted executor payload; isolate the guard
    # from the unrelated orphan recovery that would terminalize such a fake job.
    monkeypatch.setattr(queue,'_recover_dead_runners',lambda con:None)
    seed(env,1)
    with queue._db() as con:con.execute('UPDATE jobs SET state="queued"')
    with pytest.raises(ValueError,match='attivi'):admin.manage(env,action(['job-000']))


def test_social_disabled_by_default_encrypted_and_blank_preserves_secret(env):
    assert social.public()['enabled'] is False and auth.oauth_public_providers()==[]
    saved=social.save({'enabled':True,'public_url':'https://mta.example.test','providers':{'google':{'enabled':True,'client_id':'client','client_secret':'secret-value'}}})
    assert saved['providers']['google']['ready'] and 'secret-value' not in json.dumps(saved)
    with auth.db() as con:assert 'secret-value' not in con.execute('SELECT config_json FROM social_login_settings').fetchone()[0]
    social.save({'providers':{'google':{'client_secret':''}}})
    assert social.provider('google')['client_secret']=='secret-value'
    assert auth.oauth_public_providers()==[{'id':'google','label':'Google'}]
    social.save({'enabled':False,'providers':{'google':{'clear_secret':True}}})
    assert not social.public()['providers']['google']['secret_set'] and auth.oauth_public_providers()==[]


@pytest.mark.parametrize('url',['http://mta.test','https://u:p@mta.test','https://mta.test/path','https://mta.test/?x=1'])
def test_social_rejects_unsafe_redirect_base(env,url):
    with pytest.raises(ValueError):social.save({'public_url':url})
    assert not social.public()['enabled']


def test_social_state_is_single_use_and_pkce_is_bound(env):
    from starlette.requests import Request
    social.save({'enabled':True,'providers':{'github':{'enabled':True,'client_id':'id','client_secret':'secret'}}})
    request=Request({'type':'http','scheme':'https','method':'GET','server':('mta.test',443),'path':'/','headers':[],'query_string':b''})
    url,nonce=auth.oauth_authorize_url('github',request)
    from urllib.parse import parse_qs,urlsplit
    params=parse_qs(urlsplit(url).query)
    assert params['code_challenge_method']==['S256']
    assert auth.oauth_pkce(nonce)!=auth.oauth_pkce('other')
    assert not auth.oauth_verify_state('github',params['state'][0],'wrong')
    assert auth.oauth_verify_state('github',params['state'][0],nonce)
    assert not auth.oauth_verify_state('github',params['state'][0],nonce)


def test_admin_routes_authorization_and_smtp_submission(env,monkeypatch):
    from app import main
    monkeypatch.setattr(auth,'session_user',lambda request: {'id':env,'role':request.headers['x-role']} if request.headers.get('x-role') else None)
    app=FastAPI()
    for path,endpoint,methods in [('/jobs',main.admin_ai_execution_jobs,['GET']),('/history',main.admin_ai_execution_history,['POST']),('/social',main.admin_social_get,['GET']),('/social',main.admin_social_save,['PUT']),('/smtp-test',main.admin_smtp_send_test,['POST'])]:app.add_api_route(path,endpoint,methods=methods)
    client=TestClient(app)
    for role,status in [({},401),({'x-role':'user'},403)]:
        assert client.get('/jobs',headers=role).status_code==status
        for path in ('/history','/smtp-test'):assert client.post(path,headers=role,json={}).status_code==status
        assert client.put('/social',headers=role,json={}).status_code==status
    messages=[]
    class SMTP:
        def login(self,*a):assert a==('account','password')
        def send_message(self,msg):messages.append(msg);return {}
        def quit(self):pass
    monkeypatch.setattr(auth,'_smtp_client',lambda cfg:SMTP())
    auth.save_smtp_config({'host':'smtp.test','from_email':'mta@example.test','username':'account','password':'password'})
    headers={'x-role':'admin'}
    assert client.post('/smtp-test',headers=headers,json={'recipient':'a@example.test,b@example.test'}).status_code==422
    response=client.post('/smtp-test',headers=headers,json={'recipient':'test@example.test','configuration':{'password':''}})
    assert response.status_code==200,response.text
    assert len(messages)==1 and messages[0]['To']=='test@example.test'
    assert '0.3.0-r210' in messages[0].get_body(preferencelist=('plain',)).get_content()
    assert messages[0].get_body(preferencelist=('html',)) is not None
    assert 'password' not in response.text


def test_model_inventory_counts_shared_weights_once_and_not_runtime(tmp_path,monkeypatch):
    from app import model_storage
    cache=tmp_path/'cache';cache.mkdir();(cache/'weight.bin').write_bytes(b'x'*123)
    (cache/'snapshot').mkdir();(cache/'snapshot'/'weight.bin').symlink_to(cache/'weight.bin')
    monkeypatch.setattr(model_storage,'roots',lambda:[('huggingface',cache),('torch',cache/'snapshot')])
    usage=model_storage.usage();assert usage['total_bytes']==123 and usage['complete']


def test_model_catalog_does_not_call_missing_weights_zero_bytes(tmp_path,monkeypatch):
    from app import model_updater as models
    monkeypatch.setattr(models,'SERVER_DIR',tmp_path)
    monkeypatch.setattr(models,'cached_catalog',lambda:[])
    monkeypatch.setattr(models,'_registry_server_profiles',lambda:[{'id':'test','model':'test'}])
    monkeypatch.setattr(models,'_demucs_signatures',lambda name:(None,[]))
    row=models.server_inventory()['models'][0]
    assert not row['installed'] and row['size'] is None


def test_excluding_gpu_slot_never_reallocates_charge_to_other_user(env):
    from app import ai_gpu_slot_accounting as slots
    seed(env,2)
    with auth.db() as con:
        slots._init(con)
        con.executemany('INSERT INTO ai_gpu_slot_leases(job_id,gpu_key,acquired_ms,released_ms,state,method) VALUES(?,?,?,?,?,?)',
          [('ledger-000','gpu0',1000,11000,'released',slots.METHOD),('ledger-001','gpu0',1000,11000,'released',slots.METHOD)])
    before=slots.preview(start_ms=1000,end_ms=11000,rate_micro_per_second=100)
    admin.manage(env,action(['job-000']))
    after=slots.preview(start_ms=1000,end_ms=11000,rate_micro_per_second=100)
    assert len(before['jobs'])==2 and len(after['jobs'])==1
    assert after['jobs'][0]['slot_seconds']==5 and after['total_micro_eur']==500


def test_social_totp_requires_code_and_one_time_browser_challenge(env,monkeypatch):
    from app import social_totp
    from starlette.requests import Request
    from app import main
    monkeypatch.setattr(auth,'_verify_totp',lambda secret,code:secret=='totp-secret' and code=='123456')
    with auth.db() as con:con.execute('UPDATE users SET totp_enabled=1,totp_secret_enc=? WHERE id=?',(auth._seal('totp-secret'),env))
    app=FastAPI()
    app.add_api_route('/oauth-second-factor',social_totp.page,methods=['GET'])
    app.add_api_route('/oauth-second-factor',social_totp.submit,methods=['POST'])
    client=TestClient(app,base_url='https://mta.example.test')
    req=Request({'type':'http','scheme':'https','method':'GET','server':('mta.example.test',443),'path':'/','headers':[],'query_string':b''})
    challenge=social_totp.challenge(env,req)
    token=challenge.headers['set-cookie'].split(';',1)[0].split('=',1)[1]
    client.cookies.set('mta_social_totp',token)
    assert client.post('/oauth-second-factor',data={'code':'000000'},follow_redirects=False).status_code==401
    response=client.post('/oauth-second-factor',data={'code':'123456'},follow_redirects=False)
    assert response.status_code==303 and 'mta_session=' in response.headers['set-cookie']
    client.cookies.set('mta_social_totp',token)
    assert client.post('/oauth-second-factor',data={'code':'123456'},follow_redirects=False).status_code==401
    assert main._is_public('/oauth-second-factor')


def test_admin_ui_search_selection_and_pagination_in_node():
    import subprocess
    from pathlib import Path
    source=Path('app/static/admin.js').read_text()
    section=source[source.index('let aiQueueRefreshTimer'):source.index('async function saveAIQueueSettings')]
    script=r'''
const vm=require('vm'),assert=require('assert'),nodes={},urls=[];
const q=s=>nodes[s]||(nodes[s]={value:'',textContent:'',innerHTML:''});
q('#queuePageSize').value='20';let rows=[];
const api=async url=>{urls.push(url);return url.includes('/settings')?{max_concurrent_jobs:1,max_artifact_mib:1024}:{jobs:rows,page:Number(new URL('https://mta.test'+url).searchParams.get('page')),pages:3,total:45}};
const ctx={q,qa:()=>[],api,esc:String,URLSearchParams,Number,alert:()=>{}};vm.createContext(ctx);vm.runInContext(process.argv[1],ctx);
(async()=>{await ctx.loadAIQueue();assert(urls[0].includes('page_size=20'));assert(q('#queuePrev').disabled);
ctx.queueSelect('job-a',true);ctx.queueChangePage(1);await new Promise(r=>setImmediate(r));assert.equal(q('#queueSelected').textContent,'1 selezionati');
q('#queueSearch').value='lyrics';ctx.queueSearchChanged();await new Promise(r=>setImmediate(r));assert.equal(q('#queueSelected').textContent,'0 selezionati');assert(urls.at(-1).includes('search=lyrics'));
ctx.queueManagement();assert.equal(q('#queueBulk').hidden,false);
})().catch(e=>{console.error(e);process.exitCode=1});
'''
    result=subprocess.run(['node','-e',script,section],capture_output=True,text=True,timeout=10)
    assert result.returncode==0,result.stderr


def test_late_ledger_replay_keeps_queue_exclusion(env):
    seed(env,1);admin.manage(env,action(['job-000'],'delete'))
    with auth.db() as con:
        con.execute('INSERT INTO ai_compute_jobs(id,user_id,kind,status,started_at,queue_job_id) VALUES(?,?,?,?,?,?)',('late-ledger',env,'stems','done',int(time.time()),'job-000'))
        assert con.execute('SELECT accounting_excluded FROM ai_compute_jobs WHERE id="late-ledger"').fetchone()[0]==1


def test_smtp_refused_recipient_is_not_success(env,monkeypatch):
    class SMTP:
        def send_message(self,msg):return {'test@example.test':(550,b'rejected')}
        def quit(self):pass
    auth.save_smtp_config({'host':'smtp.test','from_email':'mta@example.test'})
    monkeypatch.setattr(auth,'_smtp_client',lambda cfg:SMTP())
    with pytest.raises(RuntimeError,match='rifiutato'):auth.send_mail(['test@example.test'],'test','test')


def test_deleted_tombstone_cannot_be_restored_by_stale_admin_selection(env,monkeypatch):
    seed(env,1);stale=admin.query()
    admin.manage(env,action(['job-000'],'delete'))
    monkeypatch.setattr(admin,'query',lambda **kwargs:stale)
    with pytest.raises(ValueError,match='altro amministratore'):admin.manage(env,action(['job-000'],'enable'))
    assert admin.dispositions()['job-000']=='deleted'


def test_readable_social_help_is_served_only_to_admin(env,monkeypatch):
    from app import main
    from fastapi import Request
    monkeypatch.setattr(main,'require_admin',lambda request:{'id':env,'role':'admin'})
    req=Request({'type':'http','scheme':'https','method':'GET','server':('mta.test',443),'path':'/','headers':[],'query_string':b''})
    page=main.admin_social_login_docs(req)
    assert 'Valid OAuth Redirect URIs' in page and 'Google Auth Platform' in page and 'Authorization callback URL' in page
    assert '/settings' in page and '0.3.0-r210' in page
