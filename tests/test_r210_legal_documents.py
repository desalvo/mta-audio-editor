"""Public legal routes, bilingual content, instance disclosures and admin protection."""
from html.parser import HTMLParser
import json
from pathlib import Path
import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from app import auth, legal, account_lifecycle as life


@pytest.fixture
def env(tmp_path,monkeypatch):
    monkeypatch.setattr(auth,'DATA_ROOT',tmp_path/'auth')
    monkeypatch.setenv('MTA_ADMIN_PASSWORD','administrator-password')
    monkeypatch.delenv('MTA_ALLOW_INSECURE_NO_AUTH',raising=False)
    monkeypatch.delenv('MTA_NATIVE_SINGLE_USER',raising=False)
    auth.init_auth_db()
    uid=auth.find_user('admin')['id']
    with auth.db() as con:
        con.execute("INSERT INTO users(username,email,password_hash,active,email_confirmed,role,created_at,updated_at) VALUES('legaluser','legal@example.test','x',1,1,'user',1,1)")
        user=con.execute("SELECT id FROM users WHERE username='legaluser'").fetchone()[0]
    app=FastAPI();legal.register_routes(app)
    return uid,user,TestClient(app)


def cookie(uid):
    request=Request({'type':'http','headers':[(b'user-agent',b'testclient')]})
    return {'mta_session':auth.create_session(uid,request)}


def complete():
    cfg={key:'Disclosed instance fact' for key in legal.REQUIRED}
    cfg.update(privacy_email='privacy@example.test',support_email='support@example.test',public_url='https://mta.apps.desalvo.eu',reviewed=True,effective_date='2026-10-18')
    return cfg


@pytest.mark.parametrize('kind,lang',[('privacy','it'),('privacy','en'),('terms','it'),('terms','en')])
def test_public_document_without_login_and_no_writes(env,kind,lang):
    _,_,client=env
    before=auth.db_path().read_bytes()
    response=client.get(f'/{kind}/{lang}')
    assert response.status_code==200 and response.headers['content-language']==lang
    assert f'<html lang="{lang}">' in response.text
    assert '{{' not in response.text
    assert '2026-10-18-r210' in response.headers['x-mta-legal-version']
    assert 'legal-warning' in response.text
    assert auth.db_path().read_bytes()==before
    assert response.headers['cache-control']=='no-store'


@pytest.mark.parametrize('path', ['/privacy','/terms'])
def test_language_routes(env,path):
    client=env[2]
    for lang in ('it','en'):
        response=client.get(path,headers={'accept-language':lang},follow_redirects=False)
        assert response.status_code==303 and response.headers['location']==path+'/'+lang
        assert client.get(path+'?lang='+lang,follow_redirects=False).headers['location']==path+'/'+lang
    assert client.get(path+'/fr').status_code==404
    assert client.get(path+'?lang=../../etc').status_code==404


def test_admin_and_csrf_protection_in_real_server(env,monkeypatch):
    from app import main
    uid,user,_=env
    monkeypatch.setattr(main,'NATIVE_SINGLE_USER',False)
    monkeypatch.setattr(main,'check_basic_auth',lambda request:False)
    client=TestClient(main.app)
    assert client.get('/api/admin/legal-settings').status_code==401
    client.cookies.update(cookie(user))
    assert client.get('/api/admin/legal-settings').status_code==403
    client.cookies.update(cookie(uid))
    assert client.put('/api/admin/legal-settings',json=complete()).status_code==403
    response=client.put('/api/admin/legal-settings',json=complete(),headers={'x-mta-request':'1'})
    assert response.status_code==200 and response.json()['ready']


def test_review_requires_instance_facts_and_new_edits_invalidate_it(env):
    uid,_,client=env
    with pytest.raises(ValueError,match='obbligatori'):legal.save({'reviewed':True},uid)
    cfg=legal.save(complete(),uid)
    assert cfg['ready'] and cfg['revision']==1
    assert 'legal-warning' not in client.get('/privacy/en').text
    legal.save({'operator_name':'Updated operator'},uid)
    assert 'legal-warning' in client.get('/privacy/en').text
    with auth.db() as con:
        rows=con.execute('SELECT revision,actor_id,config_json FROM legal_instance_history ORDER BY revision').fetchall()
    assert len(rows)==2 and rows[0]['actor_id']==uid
    assert json.loads(rows[0]['config_json'])['operator_name']=='Disclosed instance fact'


def test_runtime_retention_and_review_invalidation(env):
    uid,_,client=env
    legal.save(complete(),uid)
    life.settings({'project_days':17,'sandbox_days':90})
    for lang,days in (('en','days'),('it','giorni')):
        page=client.get('/privacy/'+lang).text
        assert '17 '+days in page and '90 '+days in page and 'legal-warning' in page
    cfg=legal.save(complete(),uid)
    assert cfg['ready']
    assert 'legal-warning' not in client.get('/privacy/en').text


def test_instance_text_is_escaped_not_executed(env):
    uid,_,client=env
    cfg=complete();cfg.update(operator_name='<script>alert(1)</script>',hosting_en='<img src=x onerror=alert(1)>\nSecond line')
    legal.save(cfg,uid)
    page=client.get('/privacy/en').text
    assert '<script>alert(1)</script>' not in page and '&lt;script&gt;' in page
    assert '&lt;img src=x onerror=alert(1)&gt;<br>Second line' in page


@pytest.mark.parametrize('bad',[{'privacy_email':'a\nb@example.test'},{'public_url':'javascript:alert(1)'},{'public_url':'https://user:secret@example.test'},{'public_url':'https://example.test/path'},{'reviewed':'true'},{'effective_date':'wrong'},{'hosting_en':'x'*8001},{'revision':123}])
def test_invalid_settings_rejected_without_mutation(env,bad):
    uid,_,_=env
    before=auth.db_path().read_bytes()
    with pytest.raises(ValueError):legal.save(bad,uid)
    assert auth.db_path().read_bytes()==before


class Links(HTMLParser):
    def __init__(self):super().__init__();self.links=[];self.ids=[]
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if tag=='a' and 'href' in a:self.links.append(a['href'])
        if 'id' in a:self.ids.append(a['id'])


def test_login_register_links_and_public_allowlist_end_to_end(env,monkeypatch):
    from app import main
    monkeypatch.setattr(main,'NATIVE_SINGLE_USER',False)
    monkeypatch.setattr(main,'check_basic_auth',lambda request:False)
    client=TestClient(main.app)
    for entry in ('/login','/register'):
        response=client.get(entry);assert response.status_code==200
        links=Links();links.feed(response.text)
        for path in ('/privacy/it','/privacy/en','/terms/it','/terms/en'):
            assert path in links.links
            result=client.get(path,follow_redirects=False)
            assert result.status_code==200 and result.headers['x-frame-options']=='DENY'
    assert not main._is_public('/privacy/admin')
    assert not main._is_public('/api/admin/legal-settings')


def test_sections_translations_and_template_assets(env):
    _,_,client=env
    for kind in ('privacy','terms'):
        parsed=[]
        for lang in ('it','en'):
            page=client.get(f'/{kind}/{lang}').text
            parser=Links();parser.feed(page)
            assert len(parser.ids)==12 and len(set(parser.ids))==12
            assert all(link[1:] in parser.ids for link in parser.links if link.startswith('#'))
            parsed.append(set(parser.ids))
            assert (legal.BASE/'static/legal.css').is_file()
        assert parsed[0]==parsed[1]
    assert 'EUPL 1.2' in client.get('/terms/en').text
    assert 'mta_session' in client.get('/privacy/en').text


def test_no_database_still_renders_unreviewed_policy(tmp_path,monkeypatch):
    monkeypatch.setattr(auth,'DATA_ROOT',tmp_path/'missing')
    assert legal.render('privacy','en').status_code==200
    assert not auth.db_path().exists()


def test_server_packaging_includes_legal_tree():
    root=Path(__file__).parents[1]
    spec=(root/'native/mta_audio_editor_native.spec').read_text()
    for folder in ('docs','templates','static'):
        assert '"app" / "'+folder+'"' in spec
    assert 'COPY app ./app' in (root/'Dockerfile').read_text()
