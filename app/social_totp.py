"""Browser-bound, one-use social login second factor, bounded attempts."""
import hashlib
import secrets
import time
from fastapi import Request
from fastapi.responses import HTMLResponse, RedirectResponse
from . import auth


def table(con):
    con.execute('CREATE TABLE IF NOT EXISTS social_totp_challenges(hash TEXT PRIMARY KEY,user_id INTEGER NOT NULL,expires INTEGER NOT NULL,attempts INTEGER NOT NULL DEFAULT 0)')


def challenge(uid,request):
    token=secrets.token_urlsafe(32)
    with auth.db() as con:
        table(con);con.execute('DELETE FROM social_totp_challenges WHERE expires<?',(int(time.time()),))
        con.execute('INSERT INTO social_totp_challenges(hash,user_id,expires) VALUES(?,?,?)',(hashlib.sha256(token.encode()).hexdigest(),uid,int(time.time())+300))
    response=RedirectResponse('/oauth-second-factor',303,headers={'Cache-Control':'no-store'})
    response.set_cookie('mta_social_totp',token,max_age=300,secure=request.url.scheme=='https' or request.headers.get('x-forwarded-proto','').lower()=='https',httponly=True,samesite='strict',path='/oauth-second-factor')
    return response


def page():
    return HTMLResponse('<!doctype html><html lang="it"><meta name="viewport" content="width=device-width"><title>MTA · Verifica TOTP</title><body><main><h1>Verifica in due passaggi</h1><form method="post"><label>Codice autenticatore <input name="code" required inputmode="numeric" autocomplete="one-time-code" pattern="[0-9]{6}" maxlength="6"></label><button>Accedi</button></form><a href="/login">Torna al login</a></main></body></html>',headers={'Cache-Control':'no-store'})


async def submit(request: Request):
    token=request.cookies.get('mta_social_totp','');code=str((await request.form()).get('code',''))
    with auth.db() as con:
        table(con);con.execute('BEGIN IMMEDIATE')
        key=hashlib.sha256(token.encode()).hexdigest()
        row=con.execute('SELECT * FROM social_totp_challenges WHERE hash=?',(key,)).fetchone()
        if not row or row['expires']<time.time() or row['attempts']>=5:return HTMLResponse('Verifica scaduta. <a href="/login">Accedi di nuovo</a>',status_code=401)
        con.execute('UPDATE social_totp_challenges SET attempts=attempts+1 WHERE hash=?',(key,))
        user=con.execute('SELECT * FROM users WHERE id=?',(row['user_id'],)).fetchone()
        if not user or not user['active'] or not user['email_confirmed'] or not user['totp_enabled'] or not auth._verify_totp(auth._open(user['totp_secret_enc']),code):
            return HTMLResponse('Codice non valido. <a href="/oauth-second-factor">Riprova</a>',status_code=401)
        con.execute('DELETE FROM social_totp_challenges WHERE hash=?',(key,))
    from .admin_navigation import safe_next
    session=auth.create_session(user['id'],request);response=RedirectResponse(safe_next(request.cookies.get('mta_login_next','/')),303,headers={'Cache-Control':'no-store'})
    response.set_cookie('mta_session',session,max_age=12*3600,httponly=True,secure=request.url.scheme=='https' or request.headers.get('x-forwarded-proto','').lower()=='https',samesite='lax',path='/')
    response.delete_cookie('mta_login_next',path='/')
    response.delete_cookie('mta_social_totp',path='/oauth-second-factor');return response
