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
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from . import auth
from .version import APP_RELEASE

BASE = Path(__file__).parent
DOCUMENT_VERSION = '2026-10-18-r210'
COMMON = ('operator_name','operator_address','operator_country','registration','privacy_email','support_email','dpo_contact','representative_contact','public_url')
DISCLOSURES = ('hosting','processors','transfers','retention')
FIELDS = COMMON + tuple(f'{name}_{lang}' for name in DISCLOSURES for lang in ('it','en'))
REQUIRED = ('operator_name','operator_country','support_email','public_url','effective_date')


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
    return {'ready':not missing,'missing':missing,'review_stale':stale}


def save(body, actor):
    if not isinstance(body,dict) or set(body)-set(FIELDS)-{'reviewed','effective_date'}:
        raise ValueError('Campi legali non validi')
    cfg,retention=snapshot();previous=dict(cfg)
    for key,value in body.items():
        if key=='reviewed':
            if type(value) is not bool:raise ValueError('reviewed deve essere booleano')
        else:
            if not isinstance(value,str) or len(value)>(8000 if key not in COMMON else 1000) or any(ord(c)<32 and c not in '\n\t' for c in value):
                raise ValueError('Testo non valido: '+key)
            value=value.strip()
            if key.endswith('email') and value and not auth.EMAIL_RE.fullmatch(value):raise ValueError('Email non valida: '+key)
            if key=='public_url' and value:
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
    if status(cfg,retention)['missing']:
        raise ValueError('Completa i cinque campi obbligatori prima del salvataggio')
    cfg['retention_review']=retention if cfg['reviewed'] else {}
    with auth.db() as con:
        from .resource_accounts import init,notice
        init(con)
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
        changed=[k for k in (*FIELDS,'effective_date') if cfg.get(k)!=previous.get(k)]
        if changed:
            for user in con.execute('SELECT id FROM users'):
                notice(con,f"legal:{cfg['revision']}:{user[0]}",user[0],{'kind':'legal','revision':cfg['revision'],'fields':changed})
    return {**cfg,**status(cfg,retention)}


def document_html(kind,language):
    if kind not in ('privacy','terms') or language not in ('it','en'):raise HTTPException(404,'Document not found')
    cfg,retention=snapshot();it=language=='it'
    values={k:html.escape(str(cfg.get(k) or ''),quote=True).replace('\n','<br>') for k in FIELDS}
    values['operator_location']=' · '.join(values[k] for k in ('operator_address','operator_country') if values[k])
    for key in DISCLOSURES:values[key]=values[f'{key}_{language}']
    values.update({k:str(int(v)) for k,v in retention.items()})
    values.update(language=language,kind=kind,release=html.escape(APP_RELEASE),
        title=('Informativa sulla privacy' if it else 'Privacy notice') if kind=='privacy' else ('Termini di servizio' if it else 'Terms of service'),
        effective_date=html.escape(str(cfg['effective_date'])),document_version=f'{DOCUMENT_VERSION}.{int(cfg["revision"])}',
        document_navigation='Navigazione documenti' if it else 'Document navigation',
        back='Torna al login' if it else 'Back to sign in',print_label='Scarica PDF' if it else 'Download PDF',
        other_kind='terms' if kind=='privacy' else 'privacy',other_label=('Termini di servizio' if it else 'Terms of service') if kind=='privacy' else ('Informativa privacy' if it else 'Privacy notice'),
        warning='')
    body=(BASE/'docs/legal'/f'{kind}-{language}.html').read_text(encoding='utf-8')
    body=body.replace('{{operator_address}} · {{operator_country}}','{{operator_location}}')
    if not cfg.get('operator_address') or not cfg.get('operator_country'):
        label=('Indirizzo' if cfg.get('operator_address') else 'Paese') if it else ('Address' if cfg.get('operator_address') else 'Country')
        body=body.replace('Indirizzo e Paese',label).replace('Address and country',label)
    # Remove the whole label/value row or disclosure section when unset.
    body=re.sub(r'<dt>(.*?)</dt>\s*<dd>(.*?)</dd>',lambda m:m[0] if any(values.get(k,'') for k in re.findall(r'\{\{([a-z_]+)\}\}',m[2])) else '',body,flags=re.S)
    body=re.sub(r'<h3>(.*?)</h3>\s*<p>\{\{([a-z_]+)\}\}</p>',lambda m:m[0] if values.get(m[2]) else '',body,flags=re.S)
    body=body.replace('<dl></dl>','')
    template=(BASE/'templates/legal.html').read_text(encoding='utf-8').replace('{{body}}',body)
    if not values.get('public_url'):template=template.replace('<p><a href="{{public_url}}">{{public_url}}</a></p>','')
    template=re.sub(r'\{\{([a-z_]+)\}\}',lambda match:values.get(match[1],match[0]),template)
    return template,values


def render(kind,language):
    template,values=document_html(kind,language)
    return HTMLResponse(template,headers={'Content-Language':language,'Cache-Control':'no-store','X-MTA-Legal-Version':values['document_version']})


def register_routes(app):
    @app.get('/privacy')
    @app.get('/terms')
    def preferred(request: Request,lang: str=''):
        if lang and lang not in ('it','en'):raise HTTPException(404,'Language not supported')
        from .i18n import browser_language
        language=lang or browser_language(request.headers.get('accept-language',''))
        return RedirectResponse(request.url.path+'/'+language,status_code=303,headers={'Vary':'Accept-Language','Cache-Control':'no-store'})

    @app.get('/privacy/{language}.pdf')
    @app.get('/privacy/{language}/pdf')
    def privacy_pdf(language: str):return pdf_document('privacy',language)

    @app.get('/terms/{language}.pdf')
    @app.get('/terms/{language}/pdf')
    def terms_pdf(language: str):return pdf_document('terms',language)

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


def pdf_document(kind,language):
    """Generate current instance disclosures in memory, without remote assets."""
    from io import BytesIO
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image
    template,values=document_html(kind,language)
    body=re.search(r'<article>(.*?)</article>',template,re.S)[1]
    body=re.sub(r'<nav\b.*?</nav>','',body,flags=re.S)
    body=re.sub(r'<dt>(.*?)</dt>\s*<dd>(.*?)</dd>',r'<p><b>\1:</b> \2</p>',body,flags=re.S)
    body=re.sub(r'<tr>\s*<td>(.*?)</td>\s*<td>(.*?)</td>\s*</tr>',r'<p><b>\1:</b> \2</p>',body,flags=re.S)
    styles=getSampleStyleSheet()
    styles.add(ParagraphStyle(name='LegalText',parent=styles['BodyText'],fontName='Helvetica',fontSize=9,leading=13,spaceAfter=7))
    output=BytesIO();doc=SimpleDocTemplate(output,pagesize=(210*mm,297*mm),leftMargin=19*mm,rightMargin=19*mm,topMargin=18*mm,bottomMargin=20*mm,title=values['title'],author='MTA Audio Editor')
    story=[];logo=BASE/'static/mail-logo.png'
    if logo.is_file():story.extend([Image(str(logo),width=14*mm,height=14*mm),Spacer(1,4*mm)])
    story.extend([Paragraph(values['title'],styles['Title']),Paragraph('MTA Audio Editor · '+values['release']+' · '+values['effective_date'],styles['LegalText'])])
    for tag,content in re.findall(r'<(h2|h3|p|li)\b[^>]*>(.*?)</\1>',body,re.S):
        content=re.sub(r'<br\s*/?>','<br/>',content)
        content=content.replace('<strong>','<b>').replace('</strong>','</b>').replace('<em>','<i>').replace('</em>','</i>').replace('<code>','<font name="Courier">').replace('</code>','</font>')
        # Anchors, emphasis and escaped configured facts are supported by Paragraph.
        if tag=='li':content='• '+content
        story.append(Paragraph(content,styles['Heading2'] if tag=='h2' else styles['Heading3'] if tag=='h3' else styles['LegalText']))
    def footer(canvas,document):
        canvas.saveState();canvas.setFont('Helvetica',8);canvas.setFillColor(colors.HexColor('#506176'))
        canvas.drawString(19*mm,11*mm,'MTA Audio Editor · '+values['document_version'])
        canvas.drawRightString(191*mm,11*mm,('Pagina ' if language=='it' else 'Page ')+str(document.page));canvas.restoreState()
    doc.build(story,onFirstPage=footer,onLaterPages=footer)
    return Response(output.getvalue(),media_type='application/pdf',headers={'Content-Language':language,'Cache-Control':'no-store','X-MTA-Legal-Version':values['document_version'],'Content-Disposition':f'inline; filename="mta-{kind}-{language}.pdf"'})
