"""Public bilingual legal documents and administrator-owned instance disclosures."""
from contextlib import closing
from datetime import date
import html
import json
from pathlib import Path
import re
import sqlite3
from urllib.parse import urlsplit
from fastapi import HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from . import auth
from .version import APP_RELEASE

BASE = Path(__file__).parent
DOCUMENT_VERSION = '2026-10-18-r210'
COMMON = ('operator_name','operator_address','operator_country','registration','privacy_email','support_email','dpo_contact','representative_contact','public_url')
DISCLOSURES = ('hosting','processors','transfers','retention')
FIELDS = COMMON + tuple(f'{name}_{lang}' for name in DISCLOSURES for lang in ('it','en'))
REQUIRED = ('operator_name','operator_address','operator_country','privacy_email','support_email','public_url') + tuple(f'{name}_{lang}' for name in DISCLOSURES for lang in ('it','en'))


def defaults():
    return {**dict.fromkeys(FIELDS, ''), 'public_url':'https://mta.apps.desalvo.eu',
            'reviewed':False,'retention_review':{},'effective_date':'2026-10-18','revision':0}


def snapshot():
    """Reading a public document must not create/migrate a database or settle jobs."""
    cfg=defaults();retention={'project_days':60,'sandbox_days':365}
    path=auth.db_path()
    if path.is_file():
        try:
            with closing(sqlite3.connect(path.as_uri()+'?mode=ro',uri=True,timeout=1)) as con:
                tables={r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
                if 'legal_instance_config' in tables:
                    row=con.execute('SELECT config_json FROM legal_instance_config WHERE id=1').fetchone()
                    if row:
                        data=json.loads(row[0])
                        if isinstance(data,dict):cfg.update({k:v for k,v in data.items() if k in cfg})
                if 'account_retention_config' in tables:
                    row=con.execute('SELECT project_days,sandbox_days FROM account_retention_config WHERE id=1').fetchone()
                    if row:retention=dict(zip(('project_days','sandbox_days'),row))
        except (sqlite3.Error,OSError,ValueError,TypeError):
            cfg=defaults()
    return cfg,retention


def status(cfg, retention=None):
    missing=[key for key in REQUIRED if not isinstance(cfg.get(key),str) or not cfg[key].strip()]
    stale=retention is not None and cfg.get('retention_review') != retention
    return {'ready':cfg.get('reviewed') is True and not missing and not stale,'missing':missing,'review_stale':stale}


def save(body, actor):
    if not isinstance(body,dict) or set(body)-set(FIELDS)-{'reviewed','effective_date'}:
        raise ValueError('Campi legali non validi')
    cfg,retention=snapshot()
    for key,value in body.items():
        if key=='reviewed':
            if type(value) is not bool:raise ValueError('reviewed deve essere booleano')
        else:
            if not isinstance(value,str) or len(value)>(8000 if key not in COMMON else 1000) or any(ord(c)<32 and c not in '\n\t' for c in value):
                raise ValueError('Testo non valido: '+key)
            value=value.strip()
            if key.endswith('email') and value and not auth.EMAIL_RE.fullmatch(value):raise ValueError('Email non valida: '+key)
            if key=='public_url':
                u=urlsplit(value)
                if u.scheme!='https' or not u.hostname or u.username or u.password or u.query or u.fragment or u.path not in ('','/'):
                    raise ValueError('Indica la URL pubblica HTTPS del server senza percorso o credenziali')
                value=value.rstrip('/')
            if key=='effective_date':
                try:date.fromisoformat(value)
                except ValueError as exc:raise ValueError('Data di efficacia non valida') from exc
        cfg[key]=value
    # Every edit requires an explicit fresh review; saving partial facts is allowed.
    cfg['reviewed']=body.get('reviewed',False)
    if cfg['reviewed'] and status(cfg,retention)['missing']:
        raise ValueError('Completa i dati obbligatori IT/EN prima di dichiarare la revisione')
    cfg['retention_review']=retention if cfg['reviewed'] else {}
    with auth.db() as con:
        con.execute('''CREATE TABLE IF NOT EXISTS legal_instance_config
            (id INTEGER PRIMARY KEY CHECK(id=1),config_json TEXT NOT NULL)''')
        con.execute('''CREATE TABLE IF NOT EXISTS legal_instance_history
            (revision INTEGER PRIMARY KEY,actor_id INTEGER NOT NULL,changed_at INTEGER NOT NULL,config_json TEXT NOT NULL)''')
        con.execute('BEGIN IMMEDIATE')
        prior=con.execute('SELECT coalesce(max(revision),0) FROM legal_instance_history').fetchone()[0]
        cfg['revision']=prior+1
        encoded=json.dumps(cfg,ensure_ascii=False,allow_nan=False)
        con.execute('INSERT INTO legal_instance_history VALUES(?,?,unixepoch(),?)',(cfg['revision'],actor,encoded))
        con.execute('INSERT INTO legal_instance_config VALUES(1,?) ON CONFLICT(id) DO UPDATE SET config_json=excluded.config_json',(encoded,))
    return {**cfg,**status(cfg,retention)}


def render(kind,language):
    if kind not in ('privacy','terms') or language not in ('it','en'):raise HTTPException(404,'Document not found')
    cfg,retention=snapshot();it=language=='it'
    missing='Non ancora dichiarato dal gestore' if it else 'Not yet disclosed by the operator'
    values={k:html.escape(str(cfg.get(k) or missing),quote=True).replace('\n','<br>') for k in FIELDS}
    for key in DISCLOSURES:values[key]=values[f'{key}_{language}']
    for key in ('dpo_contact','representative_contact','registration'):
        if not cfg.get(key):values[key]='Non indicato; chiedere al gestore se applicabile' if it else 'Not specified; ask the operator where applicable'
    values.update({k:str(int(v)) for k,v in retention.items()})
    values.update(language=language,kind=kind,release=html.escape(APP_RELEASE),
        title=('Informativa sulla privacy' if it else 'Privacy notice') if kind=='privacy' else ('Termini di servizio' if it else 'Terms of service'),
        effective_date=html.escape(str(cfg['effective_date'])),document_version=f'{DOCUMENT_VERSION}.{int(cfg["revision"])}',
        back='Torna al login' if it else 'Back to sign in',print_label='Stampa / Salva PDF' if it else 'Print / Save PDF',
        other_kind='terms' if kind=='privacy' else 'privacy',other_label=('Termini di servizio' if it else 'Terms of service') if kind=='privacy' else ('Informativa privacy' if it else 'Privacy notice'),
        warning='' if status(cfg,retention)['ready'] else '<aside class="legal-warning" role="note">'+('Documento di istanza da completare e verificare: il gestore non ha ancora confermato tutti i dati obbligatori. Non è una dichiarazione di conformità.' if it else 'Instance document awaiting completion and review: the operator has not confirmed all required disclosures. This is not a statement of compliance.')+'</aside>')
    body=(BASE/'docs/legal'/f'{kind}-{language}.html').read_text(encoding='utf-8')
    template=(BASE/'templates/legal.html').read_text(encoding='utf-8').replace('{{body}}',body)
    template=re.sub(r'\{\{([a-z_]+)\}\}',lambda match:values.get(match[1],match[0]),template)
    return HTMLResponse(template,headers={'Content-Language':language,'Cache-Control':'no-store','X-MTA-Legal-Version':values['document_version']})


def register_routes(app):
    @app.get('/privacy')
    @app.get('/terms')
    def preferred(request: Request,lang: str=''):
        if lang and lang not in ('it','en'):raise HTTPException(404,'Language not supported')
        language=lang or ('it' if request.headers.get('accept-language','').lower().startswith('it') else 'en')
        return RedirectResponse(request.url.path+'/'+language,status_code=303,headers={'Vary':'Accept-Language','Cache-Control':'no-store'})

    @app.get('/privacy/{language}')
    def privacy(language: str):return render('privacy',language)

    @app.get('/terms/{language}')
    def terms(language: str):return render('terms',language)

    @app.get('/api/admin/legal-settings')
    def settings(request: Request):
        auth.require_admin(request)
        cfg,retention=snapshot();return {**cfg,**status(cfg,retention)}

    @app.put('/api/admin/legal-settings')
    def update(request: Request,body: dict):
        actor=auth.require_admin(request)
        try:return save(body,actor['id'])
        except ValueError as exc:raise HTTPException(422,str(exc)) from exc
