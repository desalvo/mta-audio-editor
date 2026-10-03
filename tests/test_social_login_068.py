from pathlib import Path
from starlette.requests import Request
import pytest

ROOT=Path(__file__).resolve().parents[1]

def req(path='/oauth/google/start'):
    return Request({'type':'http','method':'GET','scheme':'https','server':('mta.example.test',443),'path':path,'root_path':'','query_string':b'','headers':[(b'host',b'mta.example.test')]})

def bootstrap(auth,tmp_path,monkeypatch):
    auth.DATA_ROOT=tmp_path
    monkeypatch.setenv('MTA_ADMIN_USERNAME','admin');monkeypatch.setenv('MTA_ADMIN_PASSWORD','administrator-password');monkeypatch.setenv('MTA_ADMIN_EMAIL','admin@example.test')
    auth.init_auth_db();return auth.find_user('admin')

def test_social_providers_disabled_by_default(monkeypatch):
    import app.auth as auth
    for p in ('GOOGLE','FACEBOOK','GITHUB'):
        monkeypatch.delenv(f'MTA_OAUTH_{p}_ENABLED',raising=False);monkeypatch.delenv(f'MTA_OAUTH_{p}_CLIENT_ID',raising=False);monkeypatch.delenv(f'MTA_OAUTH_{p}_CLIENT_SECRET',raising=False)
    assert auth.oauth_public_providers()==[]

def test_oauth_state_is_bound_to_browser_cookie(tmp_path,monkeypatch):
    import app.auth as auth
    auth.DATA_ROOT=tmp_path
    state,nonce=auth.oauth_make_state('google')
    assert auth.oauth_verify_state('google',state,nonce)
    assert not auth.oauth_verify_state('google',state,'different')
    assert not auth.oauth_verify_state('github',state,nonce)

def test_social_registration_is_verified_but_pending_approval(tmp_path,monkeypatch):
    import app.auth as auth
    admin=bootstrap(auth,tmp_path,monkeypatch)
    monkeypatch.setattr(auth,'_notify_admins_registration',lambda *a,**k:None)
    user,created=auth.social_login_or_register('google',{'subject':'g-123','email':'social@example.test','name':'Social User'})
    assert created and user['email_confirmed'] and not user['active']
    assert user['social_providers']==['google']
    again,created=auth.social_login_or_register('google',{'subject':'g-123','email':'social@example.test','name':'Social User'})
    assert not created and again['id']==user['id']
    active=auth.update_user_admin(user['id'],admin['id'],active=True)
    assert active['active']

def test_social_registration_does_not_autolink_existing_email(tmp_path,monkeypatch):
    import app.auth as auth
    bootstrap(auth,tmp_path,monkeypatch);monkeypatch.setattr(auth,'_notify_admins_registration',lambda *a,**k:None);monkeypatch.setattr(auth,'_send_verification_email',lambda *a,**k:None)
    auth.register_user('localuser','same@example.test','Local','very-secure-password')
    with pytest.raises(ValueError,match='Esiste già un account'):
        auth.social_login_or_register('github',{'subject':'gh-1','email':'same@example.test','name':'Same'})

def test_social_login_docs_and_defaults_present():
    docs=(ROOT/'docs/SOCIAL_LOGIN.md').read_text()
    compose=(ROOT/'docker-compose.yml').read_text()
    for provider in ('GOOGLE','FACEBOOK','GITHUB'):
        assert f'MTA_OAUTH_{provider}_ENABLED' in docs
        assert f'MTA_OAUTH_{provider}_ENABLED' in compose
    assert 'false' in compose

def test_authorize_url_and_provider_profiles(tmp_path,monkeypatch):
    import app.auth as auth
    auth.DATA_ROOT=tmp_path
    monkeypatch.setenv('MTA_PUBLIC_URL','https://mta.example.test')
    for provider in ('GOOGLE','GITHUB','FACEBOOK'):
        monkeypatch.setenv(f'MTA_OAUTH_{provider}_ENABLED','true');monkeypatch.setenv(f'MTA_OAUTH_{provider}_CLIENT_ID','client');monkeypatch.setenv(f'MTA_OAUTH_{provider}_CLIENT_SECRET','secret')
    url,nonce=auth.oauth_authorize_url('google',req())
    assert 'client_id=client' in url and nonce

    def google_json(url,**kwargs):
        return {'access_token':'tok'} if 'token' in url else {'sub':'g1','email':'g@example.test','email_verified':True,'name':'Google User'}
    monkeypatch.setattr(auth,'_oauth_json',google_json)
    assert auth.oauth_exchange_profile('google','code',req())['email']=='g@example.test'

    def github_json(url,**kwargs):
        if 'access_token' in url:return {'access_token':'tok'}
        if url.endswith('/user'):return {'id':42,'login':'octo','name':'Octo'}
        return [{'email':'gh@example.test','verified':True,'primary':True}]
    monkeypatch.setattr(auth,'_oauth_json',github_json)
    assert auth.oauth_exchange_profile('github','code',req('/oauth/github/callback'))['email']=='gh@example.test'

    def facebook_json(url,**kwargs):
        return {'access_token':'tok'} if 'access_token' in url else {'id':'fb1','email':'fb@example.test','name':'Face User'}
    monkeypatch.setattr(auth,'_oauth_json',facebook_json)
    assert auth.oauth_exchange_profile('facebook','code',req('/oauth/facebook/callback'))['subject']=='fb1'
