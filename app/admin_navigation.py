"""Safe administrative email destinations; navigation never performs an action."""
from contextlib import closing
import html
import json
import re
import sqlite3
from urllib.parse import parse_qsl, urlencode, urlsplit
from . import auth

TABS=frozenset(('web','storage','users','smtp','models','aiQueue','diagnostics','legal'))
SECTIONS=frozenset(('pending','archives','users'))


def safe_next(value):
    if not isinstance(value,str) or len(value)>2000 or any(ord(c)<32 for c in value) or '\\' in value:return '/'
    try:
        u=urlsplit(value)
        if u.scheme or u.netloc or u.fragment:return '/'
        pairs=parse_qsl(u.query,keep_blank_values=True)
        p=dict(pairs)
        if len(p)!=len(pairs):return '/'
        if u.path=='/ai-device' and set(p)=={'code'} and re.fullmatch(r'[A-Za-z0-9_-]{1,100}',p['code']):return value
        if u.path in ('/admin/ai-billing','/admin/ai-tokens','/account') and not p:return u.path
        if u.path!='/settings' or set(p)-{'tab','section','user','job'}:return '/'
        if ('tab' in p and p['tab'] not in TABS) or ('section' in p and p['section'] not in SECTIONS):return '/'
        if 'user' in p and not re.fullmatch(r'[1-9][0-9]{0,18}',p['user']):return '/'
        if 'job' in p and not re.fullmatch(r'[A-Za-z0-9_-]{1,160}',p['job']):return '/'
        return u.path+('?' +urlencode(pairs) if pairs else '')
    except ValueError:return '/'


def public_base():
    values=[auth._base_url()]
    path=auth.db_path()
    if not values[0] and path.is_file():
        try:
            with closing(sqlite3.connect(path.as_uri()+'?mode=ro',uri=True,timeout=1)) as con:
                if con.execute("SELECT 1 FROM sqlite_master WHERE name='social_login_settings'").fetchone():
                    row=con.execute('SELECT config_json FROM social_login_settings WHERE id=1').fetchone()
                    if row:values.append(json.loads(row[0]).get('public_url',''))
        except (sqlite3.Error,OSError,ValueError,TypeError):pass
    for value in values:
        if not isinstance(value,str) or any(c.isspace() or c in '\"<>\\' for c in value):continue
        try:
            u=urlsplit(value)
            if u.scheme in ('https','http') and u.hostname and not (u.username or u.password or u.query or u.fragment) and u.path in ('','/'):
                return value.rstrip('/')
        except ValueError:pass
    return ''


def settings_target(section,uid=None):
    if section not in SECTIONS:raise ValueError('Invalid administrative section')
    params={'tab':'users','section':section}
    if type(uid) is int and uid>0:params['user']=str(uid)
    return '/settings?'+urlencode(params)


def action(plain,path,label):
    """Append a visible absolute URL and an escaped HTML call to action."""
    base=public_base()
    target=safe_next(path)
    if not base or target=='/':return plain,''
    url=base+target
    link='<p><a style="display:inline-block;padding:12px 18px;background:#17689c;color:#fff;text-decoration:none;border-radius:6px" href="'+html.escape(url,quote=True)+'">'+html.escape(label)+'</a></p><p style="font-size:12px">Accesso autenticato richiesto. Le operazioni devono essere confermate nell’app.</p>'
    return plain+'\n\n'+label+': '+url,link


def outbox_action(event_id,uid):
    if event_id.startswith('pending:') and ':admin:' in event_id:return settings_target('pending',uid),'Apri richiesta di approvazione'
    if event_id.startswith('reactivation-admin:'):return settings_target('pending',uid),'Apri richiesta di riattivazione'
    if event_id.startswith('privacy-request:'):return settings_target('archives',uid),'Apri richiesta di cancellazione privacy'
    return None
