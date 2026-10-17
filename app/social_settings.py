"""Admin-managed social login. Secrets are encrypted with the server auth key."""
import json
import os
from urllib.parse import urlsplit
from . import auth


def _table(con):
    con.execute('CREATE TABLE IF NOT EXISTS social_login_settings(id INTEGER PRIMARY KEY CHECK(id=1),config_json TEXT NOT NULL)')


def full():
    auth.init_auth_db()
    with auth.db() as con:
        _table(con);row=con.execute('SELECT config_json FROM social_login_settings WHERE id=1').fetchone()
    if row:
        cfg=json.loads(row[0])
        for p in cfg['providers'].values():p['client_secret']=auth._open(p.pop('secret_enc',''))
        return cfg
    return {'enabled':False,'public_url':os.getenv('MTA_PUBLIC_URL','').rstrip('/'),'providers':{
        key:{'enabled':os.getenv(v['enabled_env'],'false').lower() in ('1','true','yes','on'),
             'client_id':os.getenv(v['client_env'],''),'client_secret':os.getenv(v['secret_env'],'')}
        for key,v in auth.OAUTH_PROVIDERS.items()}}


def public():
    cfg=full()
    for key,p in cfg['providers'].items():
        p['secret_set']=bool(p.pop('client_secret',''));p['label']=auth.OAUTH_PROVIDERS[key]['label']
        p['callback_url']=cfg['public_url']+'/oauth/'+key+'/callback' if cfg['public_url'] else ''
        p['ready']=bool(cfg['enabled'] and p['enabled'] and p['client_id'] and p['secret_set'] and cfg['public_url'])
    return cfg


def save(body):
    cfg=full()
    if set(body)-{'enabled','public_url','providers'}:raise ValueError('Opzione social non valida')
    if 'enabled' in body:
        if type(body['enabled']) is not bool:raise ValueError('enabled deve essere booleano')
        cfg['enabled']=body['enabled']
    if 'public_url' in body:
        value=str(body['public_url']).strip().rstrip('/');url=urlsplit(value)
        if value and (url.scheme!='https' or not url.hostname or url.username or url.password or url.query or url.fragment or url.path or url.port not in (None,443)):
            raise ValueError('URL pubblico richiesto in HTTPS, senza percorso, query o credenziali')
        cfg['public_url']=value
    providers=body.get('providers',{})
    if not isinstance(providers,dict) or set(providers)-set(auth.OAUTH_PROVIDERS):raise ValueError('Provider non valido')
    for key,patch in providers.items():
        if not isinstance(patch,dict) or set(patch)-{'enabled','client_id','client_secret','clear_secret'}:raise ValueError('Configurazione provider non valida')
        p=cfg['providers'][key]
        if 'enabled' in patch:
            if type(patch['enabled']) is not bool:raise ValueError('enabled deve essere booleano')
            p['enabled']=patch['enabled']
        for name in ('client_id','client_secret'):
            if name in patch:
                v=patch[name]
                if not isinstance(v,str) or len(v)>4096 or any(c in v for c in '\r\n'):raise ValueError('Credenziale non valida')
                if name=='client_id' or v:p[name]=v.strip()
        if patch.get('clear_secret') is True:p['client_secret']=''
    # Validate legacy environment values too before allowing the master switch.
    value=cfg['public_url'];url=urlsplit(value)
    if value and (url.scheme!='https' or not url.hostname or url.username or url.password or url.query or url.fragment or url.path or url.port not in (None,443)):
        raise ValueError('URL pubblico HTTPS non valido')
    if cfg['enabled']:
        if not cfg['public_url']:raise ValueError('Imposta prima l’URL pubblico HTTPS del server')
        for key,p in cfg['providers'].items():
            if p['enabled'] and not (p['client_id'] and p['client_secret']):raise ValueError('Credenziali mancanti per '+key)
    for p in cfg['providers'].values():p['secret_enc']=auth._seal(p.pop('client_secret'))
    with auth.db() as con:
        _table(con);con.execute('INSERT INTO social_login_settings VALUES(1,?) ON CONFLICT(id) DO UPDATE SET config_json=excluded.config_json',(json.dumps(cfg),))
    return public()


def provider(key):
    cfg=full();p=cfg['providers'].get(key,{})
    return p if cfg['enabled'] and cfg['public_url'] and p.get('enabled') and p.get('client_id') and p.get('client_secret') else None
