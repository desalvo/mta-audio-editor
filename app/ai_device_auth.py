"""Bounded device approval: a native instance receives one user-owned AI token."""
from __future__ import annotations
import hashlib
import html
import secrets
import time
import re
from urllib.parse import quote
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
from . import auth, ai_access

router = APIRouter()
TTL = 900
CLIENT = re.compile(r'[a-f0-9]{32}\Z')


def _init(con):
    ai_access._init(con)
    columns = {row[1] for row in con.execute('PRAGMA table_info(ai_access_tokens)')}
    if 'client_id' not in columns:
        con.execute('ALTER TABLE ai_access_tokens ADD COLUMN client_id TEXT')
    con.execute('''CREATE UNIQUE INDEX IF NOT EXISTS ai_token_native_instance
      ON ai_access_tokens(user_id,client_id) WHERE client_id IS NOT NULL AND revoked_at IS NULL''')
    con.execute('''CREATE TABLE IF NOT EXISTS ai_device_requests (
      device_hash TEXT PRIMARY KEY, user_code TEXT UNIQUE NOT NULL, client_id TEXT NOT NULL,
      label TEXT NOT NULL, created_at INTEGER NOT NULL, expires_at INTEGER NOT NULL,
      state TEXT NOT NULL DEFAULT 'pending', user_id INTEGER, token_id INTEGER,
      token_enc TEXT, last_poll INTEGER NOT NULL DEFAULT 0)''')


def begin(client_id, label='MTA native application'):
    if not isinstance(client_id,str) or not CLIENT.fullmatch(client_id):
        raise ValueError('Invalid native instance ID')
    if not isinstance(label,str) or not 1 <= len(label.strip()) <= 80 or any(ord(c)<32 for c in label):
        raise ValueError('Invalid instance label')
    secret=secrets.token_urlsafe(40); now=int(time.time())
    with auth.db() as con:
        _init(con)
        con.execute('BEGIN IMMEDIATE')
        # Expired secrets are never retained as recoverable credentials.
        con.execute('DELETE FROM ai_device_requests WHERE expires_at<?',(now,))
        if con.execute('SELECT COUNT(*) FROM ai_device_requests').fetchone()[0]>=2000:
            raise ValueError('Device authorization capacity reached; retry later')
        code='-'.join(secrets.token_hex(3).upper() for _ in range(2))
        con.execute('INSERT INTO ai_device_requests(device_hash,user_code,client_id,label,created_at,expires_at) VALUES(?,?,?,?,?,?)',
          (hashlib.sha256(secret.encode()).hexdigest(),code,client_id,label.strip(),now,now+TTL))
    return {'device_code':secret,'user_code':code,'expires_in':TTL,'interval':5}


def approve(user, code, *, allow=True):
    user=dict(user)
    if not isinstance(code,str) or not re.fullmatch(r'[A-F0-9]{6}-[A-F0-9]{6}',code):raise ValueError('Invalid approval code')
    if int(user['id'])<=0 or not user.get('active') or not user.get('email_confirmed'):
        raise ValueError('An active account with a verified email is required')
    with auth.db() as con:
        _init(con);con.execute('BEGIN IMMEDIATE')
        row=con.execute('SELECT * FROM ai_device_requests WHERE user_code=?',(code,)).fetchone()
        if not row or row['expires_at']<=int(time.time()) or row['state']!='pending':
            raise ValueError('Request expired or already processed')
        if not allow:
            con.execute("UPDATE ai_device_requests SET state='denied' WHERE user_code=?",(code,));return
        # Only one pending request per instance may be approved: a stale browser
        # tab cannot unexpectedly rotate credentials issued by a newer approval.
        con.execute("UPDATE ai_device_requests SET state='denied',token_enc=NULL WHERE client_id=? AND user_code<>? AND state IN ('pending','approved')",(row['client_id'],code))
        # Reapproval of the SAME instance rotates, never creates two active tokens.
        con.execute('UPDATE ai_access_tokens SET revoked_at=? WHERE user_id=? AND client_id=? AND revoked_at IS NULL',
          (int(time.time()),user['id'],row['client_id']))
        raw='mta_ai_'+secrets.token_urlsafe(32)
        cur=con.execute('INSERT INTO ai_access_tokens(user_id,label,token_hash,created_at,client_id) VALUES(?,?,?,?,?)',
          (user['id'],row['label'],hashlib.sha256(raw.encode()).hexdigest(),int(time.time()),row['client_id']))
        con.execute("UPDATE ai_device_requests SET state='approved',user_id=?,token_id=?,token_enc=? WHERE user_code=?",
          (user['id'],cur.lastrowid,auth._seal(raw),code))


def poll(device_code):
    if not isinstance(device_code,str) or not 32<=len(device_code)<=100:
        raise ValueError('Invalid device code')
    now=int(time.time())
    with auth.db() as con:
        _init(con);con.execute('BEGIN IMMEDIATE')
        row=con.execute('SELECT * FROM ai_device_requests WHERE device_hash=?',
          (hashlib.sha256(device_code.encode()).hexdigest(),)).fetchone()
        if not row or row['expires_at']<=now:return {'state':'expired'}
        if row['last_poll'] and now-row['last_poll']<4:return {'state':'slow_down','interval':5}
        con.execute('UPDATE ai_device_requests SET last_poll=? WHERE device_hash=?',(now,row['device_hash']))
        if row['state']!='approved':return {'state':row['state']}
        token=auth._open(row['token_enc'])
        active=con.execute('''SELECT t.id FROM ai_access_tokens t JOIN users u ON u.id=t.user_id
          WHERE t.id=? AND t.revoked_at IS NULL AND u.active=1 AND u.email_confirmed=1''',(row['token_id'],)).fetchone()
        if not active:return {'state':'denied'}
        # Retain encrypted token until expiry for an idempotent lost poll reply.
        return {'state':'approved','token':token,'token_id':row['token_id'],'user_id':row['user_id']}


@router.post('/api/ai-device/start')
def start_request(request:Request,body:dict):
    try:
        result=begin(body.get('client_id'),body.get('label','MTA native application'))
        result['verification_uri']='/ai-device?code='+quote(result['user_code'])
        return result
    except ValueError as exc:raise HTTPException(400,str(exc)) from exc


@router.post('/api/ai-device/poll')
def poll_request(request:Request,body:dict):
    try:return poll(body.get('device_code'))
    except ValueError as exc:raise HTTPException(400,str(exc)) from exc


@router.get('/ai-device',response_class=HTMLResponse)
def approval_page(request:Request,code:str=''):
    user=auth.session_user(request)
    safe=html.escape(code,quote=True)
    with auth.db() as con:
        _init(con)
        row=con.execute('SELECT label,expires_at,state FROM ai_device_requests WHERE user_code=?',(code,)).fetchone()
    if not row or row['expires_at']<=int(time.time()):
        content='<p>Richiesta assente o scaduta. Ripeti il collegamento dall’app nativa.</p>'
    elif not user or int(user['id'])<=0:
        nxt=quote('/ai-device?code='+code,safe='')
        content=f'<p>Accedi al tuo account per autorizzare questa app. Se non hai un account, registrati e completa conferma email e approvazione amministrativa; poi torna qui.</p><p><a href="/login?next={nxt}">Accedi</a> · <a href="/register" target="_blank" rel="noopener">Registrati</a></p>'
    else:
        content=f'''<p>Istanza: <strong>{html.escape(row['label'])}</strong></p><p>Codice: <strong>{safe}</strong></p>
        <p>Account: {html.escape(user['username'])}. Autorizza solo se questo codice coincide con quello mostrato nella tua app. Il token consente inferenze AI associate al tuo account e ai suoi consumi.</p>
        <button id="approve">Autorizza istanza</button> <button id="deny">Rifiuta</button><p id="result" role="status"></p>
        <script>for(const action of ['approve','deny'])document.getElementById(action).onclick=async()=>{{
        const r=await fetch('/api/account/ai-device/approve',{{method:'POST',headers:{{'content-type':'application/json','x-mta-request':'1'}},body:JSON.stringify({{code:{__import__('json').dumps(code)},allow:action==='approve'}})}});
        const d=await r.json();document.getElementById('result').textContent=r.ok?'Richiesta elaborata. Torna nell’app.':d.detail;
        if(r.ok)for(const id of ['approve','deny'])document.getElementById(id).disabled=true;}};</script>'''
    return HTMLResponse('<!doctype html><html lang="it"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>MTA · Collega app</title><link rel="stylesheet" href="/static/ai_admin.css"></head><body><header><h1>Collega MTA Audio Editor</h1></header><main><section>'+content+'</section></main></body></html>',headers={'Cache-Control':'no-store','Referrer-Policy':'no-referrer'})


@router.post('/api/account/ai-device/approve')
def approve_request(request:Request,body:dict):
    user=auth.require_user(request)
    if type(body.get('allow')) is not bool:raise HTTPException(400,'Invalid decision')
    try:approve(user,body.get('code',''),allow=body['allow']);return {'ok':True}
    except ValueError as exc:raise HTTPException(400,str(exc)) from exc
