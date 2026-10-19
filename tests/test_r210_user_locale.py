"""Account locale, browser-only legal links, runtime PDF and default quota regressions."""
import json
from pathlib import Path
import subprocess
import pytest
import fitz
from fastapi import Request
from fastapi.testclient import TestClient
from app import auth, i18n, legal
SEND_MAIL=auth.send_mail

@pytest.fixture
def env(tmp_path,monkeypatch):
    monkeypatch.setattr(auth,'DATA_ROOT',tmp_path/'auth')
    monkeypatch.setenv('MTA_ADMIN_PASSWORD','administrator-password')
    monkeypatch.delenv('MTA_ALLOW_INSECURE_NO_AUTH',raising=False)
    monkeypatch.delenv('MTA_NATIVE_SINGLE_USER',raising=False)
    auth.init_auth_db()
    monkeypatch.setattr(auth,'send_mail',lambda *a,**kw:None)
    return auth.find_user('admin')['id']

@pytest.mark.parametrize('header,want',[('it-IT,it;q=0.9,en;q=0.8','it'),('it;q=0.2,en-US;q=0.9','en'),('fr,it;q=0.4','it'),('it;q=0,en;q=0.5','en'),('fr','en'),('it;q=bad,en','en')])
def test_browser_language(header,want):assert i18n.browser_language(header)==want


def test_new_accounts_quota_and_profile_locale(env):
    token=i18n.current_language.set('it')
    try:
        local,_=auth.register_user('locale-user','locale@example.test','Locale','secure-password-123')
        social,_=auth.social_login_or_register('google',{'subject':'locale-google','email':'social@example.test','name':'Social','email_verified':True})
    finally:i18n.current_language.reset(token)
    for uid in (env,local['id'],social['id']):
        user=auth.public_user(auth.get_user(uid))
        assert user['workspace_quota_bytes']==(0 if uid==env else 5*1024**3) and user['language']=='auto'
    assert i18n.user_language(local['id'])=='it'
    for choice in ('en','it','auto'):
        auth.update_profile(local['id'],language=choice)
        user=auth.public_user(auth.get_user(local['id']))
        assert user['language']==choice and user['display_name']=='Locale' and user['email']=='locale@example.test'
    with pytest.raises(ValueError,match='language'):auth.update_profile(local['id'],language='fr')
    with auth.db() as con:con.execute('UPDATE users SET workspace_quota_bytes=123 WHERE id=?',(local['id'],))
    auth.init_auth_db()
    assert auth.public_user(auth.get_user(local['id']))['workspace_quota_bytes']==123


def test_browser_login_and_profile_override(env,monkeypatch):
    from app import main
    monkeypatch.setattr(main,'NATIVE_SINGLE_USER',False)
    monkeypatch.setattr(main,'check_basic_auth',lambda r:False)
    client=TestClient(main.app)
    for lang,other in (('it','en'),('en','it')):
        response=client.get('/login',headers={'accept-language':lang+'-XX'})
        assert response.status_code==200 and response.headers['content-language']==lang
        assert f'href="/privacy/{lang}"' in response.text and f'href="/terms/{lang}"' in response.text
        assert f'href="/privacy/{other}"' not in response.text
    req=Request({'type':'http','headers':[(b'user-agent',b'testclient')]})
    client.cookies.set('mta_session',auth.create_session(env,req))
    response=client.patch('/api/account',json={'language':'it'},headers={'x-mta-request':'1','accept-language':'en'})
    assert response.status_code==200
    response=client.get('/account',headers={'accept-language':'en'})
    assert response.status_code==200 and response.headers['content-language']=='it'
    assert 'window.MTA_LOCALE={"language":"it","choice":"it"}' in response.text
    assert client.get('/api/session',headers={'accept-language':'en'}).json()['language']=='it'


@pytest.mark.parametrize('kind',['privacy','terms'])
@pytest.mark.parametrize('lang',['it','en'])
def test_dynamic_pdf_omits_empty_fields(env,kind,lang):
    from fastapi import FastAPI
    app=FastAPI();legal.register_routes(app);client=TestClient(app)
    legal.save({'operator_name':'INSTANCE ONE','operator_address':'','operator_country':'Italy','support_email':'support@example.test','privacy_email':'','public_url':'https://mta.example.test'},env)
    response=client.get(f'/{kind}/{lang}.pdf')
    assert response.status_code==200 and response.headers['content-type']=='application/pdf'
    assert response.headers['cache-control']=='no-store' and response.headers['content-language']==lang
    with fitz.open(stream=response.content,filetype='pdf') as doc:text='\n'.join(p.get_text() for p in doc)
    assert 'INSTANCE ONE' in text and '{{' not in text and 'not yet disclosed' not in text.lower()
    assert 'Address and country:' not in text and 'Indirizzo e paese:' not in text
    legal.save({'operator_name':'INSTANCE TWO'},env)
    response=client.get(f'/{kind}/{lang}.pdf')
    with fitz.open(stream=response.content,filetype='pdf') as doc:text='\n'.join(p.get_text() for p in doc)
    assert 'INSTANCE TWO' in text and 'INSTANCE ONE' not in text


def test_catalog_html_and_template_translation():
    assert i18n.translate('  Save project  ','it')=='  Salva progetto  '
    assert i18n.translate('Salva progetto','en')=='Save project'
    assert i18n.translate_html('<p>Save project</p><code>Save project</code><span translate="no">Save project</span>','it')=='<p>Salva progetto</p><code>Save project</code><span translate="no">Save project</span>'
    catalog=i18n.catalog()
    assert len(catalog)>1000
    js=Path('app/static/i18n_catalog.js').read_text()
    assert json.loads(js.split('window.MTA_TRANSLATION_ALIASES=')[0].removeprefix('window.MTA_TRANSLATIONS=').strip().removesuffix(';'))==catalog
    for lang in ('it','en'):
        for source,target in i18n.mapping(lang).items():
            if '{0}' not in source:
                translated=i18n.translate(source,lang)
                assert i18n.translate(translated,lang)==translated,(lang,source,target)


def test_js_locale_runtime():
    script=r'''const fs=require('fs'),vm=require('vm');
const context={window:{MTA_LOCALE:{choice:'auto'},dispatchEvent(){}},navigator:{languages:['fr-FR','it-IT']},document:{readyState:'loading',addEventListener(){},documentElement:{},createTreeWalker(){return {nextNode(){return false}}}},NodeFilter:{SHOW_TEXT:4},CustomEvent:class{}};
vm.createContext(context);for(const p of ['app/static/i18n_catalog.js','app/static/localization.js'])vm.runInContext(fs.readFileSync(p,'utf8'),context);
const t=context.window.MtaLocale;if(t.language!=='it'||t.translate('Save project')!=='Salva progetto')throw Error('auto');
t.setChoice('en');if(t.translate('Salva progetto')!=='Save project')throw Error('override');
for(const choice of ['it','en']){t.setChoice(choice);for(const key of Object.keys(context.window.MTA_TRANSLATIONS)){const once=t.translate(key);if(t.translate(once)!==once)throw Error('non-idempotent '+key)}}
'''
    subprocess.run(['node','-e',script],check=True)


def test_recipient_locale_is_independent_of_sender(env,monkeypatch):
    with auth.db() as con:
        con.execute("UPDATE users SET email='admin@example.test',language='it' WHERE id=?",(env,))
        con.execute("INSERT INTO users(username,email,password_hash,active,email_confirmed,role,created_at,updated_at,language,browser_language) VALUES('english','en@example.test','unused',1,1,'user',1,1,'auto','en')")
    messages=[]
    monkeypatch.setattr(auth,'_send_mail_one',lambda *args,**kwargs:messages.append(args))
    token=i18n.current_language.set('it')
    try:SEND_MAIL(['admin@example.test','en@example.test'],'Save project','Save project','<p>Save project</p>')
    finally:i18n.current_language.reset(token)
    assert messages[0][:4]==(['admin@example.test'],'Salva progetto','Salva progetto','<p>Salva progetto</p>')
    assert messages[1][:4]==(['en@example.test'],'Save project','Save project','<p>Save project</p>')


def test_icons_placeholders_and_native_catalog_packaging():
    assert i18n.translate('▶ Importa audio','en')=='▶ Import audio'
    assert i18n.translate('⧉ Copy','it')=='⧉ Copia'
    assert i18n.translate_html('<span class="track-name">Save project</span>','it')=='<span class="track-name">Save project</span>'
    assert 'i18n_catalog.json' in Path('native/mta_audio_editor_native.spec').read_text()
    script=Path('app/static/localization.js').read_text()
    assert "'title','placeholder','aria-label'" in script


def test_metrics_label_translation():
    assert i18n.translate('CPU 1.2 s (verificata finora)','en')=='CPU 1.2 s (verified so far)'
    assert i18n.translate('12000 campioni','en')=='12000 samples'
    assert i18n.translate('Utente: user-123','en')=='User: user-123'
