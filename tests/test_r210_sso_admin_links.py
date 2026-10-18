"""SSO branding, truthful provider notices and safe administrative email navigation."""
import html
from html.parser import HTMLParser
from pathlib import Path
import json
import pytest
from fastapi.testclient import TestClient
from app import auth, account_lifecycle as life, admin_navigation as nav, social_ui


@pytest.fixture
def env(tmp_path,monkeypatch):
    monkeypatch.setattr(auth,'DATA_ROOT',tmp_path/'auth')
    monkeypatch.setenv('MTA_ADMIN_PASSWORD','administrator-password')
    monkeypatch.setenv('MTA_PUBLIC_URL','https://mta.example.test')
    monkeypatch.delenv('MTA_ALLOW_INSECURE_NO_AUTH',raising=False)
    monkeypatch.delenv('MTA_NATIVE_SINGLE_USER',raising=False)
    auth.init_auth_db();life.settings()
    monkeypatch.setattr(auth,'send_mail',lambda *args,**kwargs:None)
    return auth.find_user('admin')


class Markup(HTMLParser):
    def __init__(self):super().__init__();self.links=[];self.images=[]
    def handle_starttag(self,tag,attrs):
        attrs=dict(attrs)
        if tag=='a':self.links.append(attrs)
        if tag=='img':self.images.append(attrs)


def test_enabled_providers_have_bundled_marks_and_distinct_styles():
    markup=social_ui.buttons([{'id':key} for key in auth.OAUTH_PROVIDERS])
    parsed=Markup();parsed.feed(markup)
    assert len(parsed.links)==len(parsed.images)==3
    for key,link,icon in zip(auth.OAUTH_PROVIDERS,parsed.links,parsed.images):
        assert link['href']==f'/oauth/{key}/start'
        assert 'social-'+key in link['class']
        assert icon['src'].startswith('/static/social/') and icon['alt']==''
        assert (Path(__file__).parents[1]/'app'/icon['src'].lstrip('/')).is_file()
    assert social_ui.buttons([])=='' and social_ui.buttons([{'id':'evil<script>'}])==''
    css=(Path(__file__).parents[1]/'app/static/auth.css').read_text()
    for key in auth.OAUTH_PROVIDERS:assert '.social-login.social-'+key in css
    assert '.social-login:focus-visible' in css


@pytest.mark.parametrize('provider',['google','github','facebook'])
@pytest.mark.parametrize('verified',[True,False])
def test_notice_names_actual_provider_and_verification(provider,verified):
    result=social_ui.registration_notice(provider,{'email_confirmed':verified},True)
    label=auth.OAUTH_PROVIDERS[provider]['label']
    assert label in result['title'] and label in result['message']
    for other,cfg in auth.OAUTH_PROVIDERS.items():
        if other!=provider:assert cfg['label'] not in result['message']
    assert ('già verificato' in result['message'])==verified
    assert ('tramite il link di verifica' in result['message'])==(not verified)
    assert 'amministratore' in result['message']
    assert 'non è ancora attivo' in social_ui.registration_notice(provider,{'email_confirmed':verified},False)['message']


@pytest.mark.parametrize('provider',['google','github','facebook'])
def test_actual_oauth_callback_renders_provider_specific_notice(env,monkeypatch,provider):
    from app import main
    monkeypatch.setattr(main,'NATIVE_SINGLE_USER',False)
    monkeypatch.setattr(main,'oauth_verify_state',lambda *args:True)
    monkeypatch.setattr(main,'oauth_exchange_profile',lambda *args:{})
    user={'id':987,'active':False,'email_confirmed':provider!='facebook','totp_enabled':False}
    monkeypatch.setattr(main,'social_login_or_register',lambda *args:(user,True))
    response=TestClient(main.app).get('/oauth/'+provider+'/callback?code=code&state=state')
    assert response.status_code==200 and auth.OAUTH_PROVIDERS[provider]['label'] in response.text
    for key in auth.OAUTH_PROVIDERS:
        if key!=provider:assert auth.OAUTH_PROVIDERS[key]['label'] not in response.text


@pytest.mark.parametrize('bad',['https://evil.test','//evil.test','/\\evil.test','/%2f%2fevil.test','/settings?tab=users&next=https://evil.test','/settings?tab=users&tab=web','/settings?tab=invalid','/settings?user=-1','/settings?job=a/b','/settings#//evil.test','/logout','/api/admin/users/1','/settings\r\nLocation: evil'])
def test_login_destinations_reject_external_or_action_urls(bad):assert nav.safe_next(bad)=='/'


@pytest.mark.parametrize('good',['/settings?tab=users&section=pending&user=42','/settings?tab=users&section=archives&user=42','/settings?tab=aiQueue&job=job_123','/admin/ai-billing','/admin/ai-tokens','/account','/ai-device?code=ABCD-1234'])
def test_known_navigation_destinations(good):assert nav.safe_next(good)==good


def test_admin_email_links_are_absolute_escaped_and_do_not_execute(env):
    uid=env['id'];target=nav.settings_target('pending',uid)
    plain,link=nav.action('Notice',target,'Apri <richiesta>')
    assert 'https://mta.example.test/settings?' in plain
    assert '&amp;section=pending' in link and '&lt;richiesta&gt;' in link
    assert '/api/' not in link and 'access_token' not in link
    assert nav.outbox_action('pending:42:admin:1',42)[0].endswith('user=42')
    assert 'archives' in nav.outbox_action('privacy-request:42:123:1',42)[0]
    assert 'pending' in nav.outbox_action('reactivation-admin:42:123:1',42)[0]
    assert nav.outbox_action('otp:42:login:abc',42) is None


def test_untrusted_or_missing_public_url_is_not_sent(env,monkeypatch):
    for base in ('','javascript:alert(1)','https://user:password@evil.test','https://good.test/?next=evil','https://good.test/\nHeader: x'):
        monkeypatch.setenv('MTA_PUBLIC_URL',base)
        assert nav.action('Original',nav.settings_target('users',1),'Open')==('Original','')


def test_social_config_public_url_fallback_is_read_only(env,monkeypatch):
    monkeypatch.delenv('MTA_PUBLIC_URL',raising=False)
    with auth.db() as con:
        con.execute('CREATE TABLE social_login_settings(id INTEGER PRIMARY KEY,config_json TEXT)')
        con.execute('INSERT INTO social_login_settings VALUES(1,?)',(json.dumps({'public_url':'https://configured.example.test'}),))
    before=auth.db_path().read_bytes()
    assert nav.public_base()=='https://configured.example.test'
    assert auth.db_path().read_bytes()==before


def test_legacy_admin_notifications_include_clickable_context(env,monkeypatch):
    messages=[];monkeypatch.setattr(auth,'send_mail',lambda *a,**kw:messages.append(a))
    user={'id':17,'username':'<person>','email':'person@example.test'}
    auth._notify_admins_registration(user,'google');auth._notify_admins_activated(user)
    assert len(messages)==2
    for message in messages:
        assert 'https://mta.example.test/settings?' in message[2]
        assert 'href="https://mta.example.test/settings?' in message[3]
        assert '<person>' not in message[3] and '&lt;person&gt;' in message[3]
        assert 'user=17' in html.unescape(message[3])


@pytest.mark.parametrize('key,section',[('pending:17:admin:1','pending'),('privacy-request:17:123:1','archives'),('reactivation-admin:17:123:1','pending')])
def test_outbox_existing_admin_events_get_links_at_send_time(env,monkeypatch,key,section):
    messages=[];monkeypatch.setattr(auth,'get_smtp_config',lambda:{'host':'smtp.test','from_email':'mta@example.test'})
    monkeypatch.setattr(auth,'send_mail',lambda *a,**kw:messages.append(a))
    with auth.db() as con:life.init(con);life.enqueue(con,key,env['email'],'Admin action','Original administrative instructions',uid=17)
    life.send_pending()
    assert len(messages)==1
    assert 'section='+section in messages[0][2]
    assert 'href="https://mta.example.test/settings?' in messages[0][3]
    assert 'user=17' in messages[0][2]


def test_email_destination_survives_password_login_and_requires_authorization(env,monkeypatch):
    from app import main
    monkeypatch.setattr(main,'NATIVE_SINGLE_USER',False);monkeypatch.setattr(main,'check_basic_auth',lambda request:False)
    client=TestClient(main.app);target=nav.settings_target('pending',env['id'])
    response=client.get(target,follow_redirects=False)
    assert response.status_code==303 and response.headers['location'].startswith('/login?next=')
    assert 'mta_login_next' in client.cookies
    page=client.get(response.headers['location'])
    assert html.escape(target,quote=True) in page.text
    response=client.post('/login',data={'identifier':env['username'],'password':'administrator-password','next':target},follow_redirects=False)
    assert response.status_code==303 and response.headers['location']==target
    assert 'mta_login_next' not in client.cookies
    assert client.get(target).status_code==200


def test_email_destination_survives_social_login(env,monkeypatch):
    from app import main
    monkeypatch.setattr(main,'oauth_verify_state',lambda *args:True)
    monkeypatch.setattr(main,'oauth_exchange_profile',lambda *args:{})
    user={'id':env['id'],'active':True,'email_confirmed':True,'totp_enabled':False}
    monkeypatch.setattr(main,'social_login_or_register',lambda *args:(user,False))
    client=TestClient(main.app);target=nav.settings_target('archives',42)
    client.cookies.set('mta_login_next',target,domain='testserver.local',path='/')
    response=client.get('/oauth/google/callback?code=code&state=state',follow_redirects=False)
    assert response.status_code==303 and response.headers['location']==target
    assert 'mta_login_next' not in client.cookies


def test_admin_sso_totp_keeps_destination_until_verified(env,monkeypatch):
    from app import main
    secret=auth._new_totp_secret()
    with auth.db() as con:con.execute('UPDATE users SET totp_enabled=1,totp_secret_enc=? WHERE id=?',(auth._seal(secret),env['id']))
    user={'id':env['id'],'active':True,'email_confirmed':True,'totp_enabled':True}
    monkeypatch.setattr(main,'oauth_verify_state',lambda *args:True)
    monkeypatch.setattr(main,'oauth_exchange_profile',lambda *args:{})
    monkeypatch.setattr(main,'social_login_or_register',lambda *args:(user,False))
    client=TestClient(main.app);target=nav.settings_target('pending',42)
    client.cookies.set('mta_login_next',target,domain='testserver.local',path='/')
    response=client.get('/oauth/google/callback?code=code&state=state',follow_redirects=False)
    assert response.headers['location']=='/oauth-second-factor'
    assert 'mta_session' not in client.cookies and 'mta_login_next' in client.cookies
    bad=client.post('/oauth-second-factor',data={'code':'invalid'},follow_redirects=False)
    assert bad.status_code==401 and 'mta_session' not in client.cookies
    response=client.post('/oauth-second-factor',data={'code':auth._totp(secret)},follow_redirects=False)
    assert response.status_code==303 and response.headers['location']==target
    assert 'mta_session' in client.cookies and 'mta_login_next' not in client.cookies


def test_admin_client_opens_requested_tab_and_focuses_only_requested_record():
    import subprocess
    import shutil
    if not shutil.which('node'):pytest.skip('Node unavailable')
    script=Path(__file__).parents[1]/'app/static/admin_links.js'
    js='''const fs=require('fs'),vm=require('vm'),assert=require('assert');
    const source=fs.readFileSync(process.argv[1],'utf8');
    function run(search){let clicks=[],focus=[],input={value:''};let row={dataset:{userId:'42'},classList:{add:c=>focus.push(c)},scrollIntoView:()=>{},focus:()=>focus.push('focused')};
      let box={querySelectorAll:()=>[row],closest:()=>({scrollIntoView:()=>{}})};
      let window={};const context={URLSearchParams,location:{search},window,document:{readyState:'complete',getElementById:id=>id==='queueSearch'?input:box,querySelectorAll:()=>['users','aiQueue'].map(tab=>({dataset:{tab},click:()=>clicks.push(tab)}))}};
      vm.runInNewContext(source,context);window.mtaAdminLinkFocus();return {clicks,focus,input};}
    let a=run('?tab=users&section=pending&user=42');assert.deepStrictEqual(a.clicks,['users']);assert(a.focus.includes('focused'));
    let b=run('?tab=aiQueue&job=job_12');assert.deepStrictEqual(b.clicks,['aiQueue']);assert.strictEqual(b.input.value,'job_12');
    let c=run('?tab=evil&section=pending&user=not-a-user');assert.deepStrictEqual(c.clicks,[]);assert(!c.focus.includes('focused'));
    '''
    subprocess.run(['node','-e',js,str(script)],check=True)
