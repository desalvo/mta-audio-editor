"""Server account lifecycle HTTP/UI endpoints; no administrative token access."""
import html
import time
from fastapi import HTTPException, Request
from fastapi.responses import HTMLResponse, FileResponse
from . import auth, account_lifecycle as life, account_mfa as mfa


def page(title,body):
    return HTMLResponse('<!doctype html><html lang="it"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>MTA · '+html.escape(title)+'</title><link rel="stylesheet" href="/static/auth.css"><body class="auth-body"><main class="single-auth"><section class="login-card glass compact"><img src="/static/logo.svg" class="login-logo" alt="MTA"><h1>'+html.escape(title)+'</h1>'+body+'<p><a href="/login">Torna al login</a></p></section></main></body></html>',headers={'Cache-Control':'no-store'})


def enrollment(uid):
    token=auth._create_email_token(uid,'enrollment')
    user=auth.get_user(uid)
    with auth.db() as con:
        life.init(con);life.enqueue(con,'enroll:'+auth._token_hash(token),user['email'],'Completa il secondo fattore MTA',auth._base_url()+'/registration-security?token='+token,uid=uid)
    return '/registration-security?token='+token


def enroll_user(token):
    with auth.db() as con:
        life.init(con)
        row=con.execute("SELECT user_id FROM email_tokens WHERE token_hash=? AND purpose='enrollment' AND used_at IS NULL AND expires_at>?",(auth._token_hash(token),int(time.time()))).fetchone()
    if not row:raise ValueError('Link scaduto o non valido. Usa Reinvia conferma email dalla pagina di login.')
    user=auth.get_user(row[0])
    if not user or not user['email_confirmed'] or life.info(row[0])['state']!='enrolling':raise ValueError('Registrazione non in fase di verifica del secondo fattore')
    return user


def register_routes(app):
    @app.get('/docs/admin/account-lifecycle',response_class=HTMLResponse)
    def guide(request: Request):
        auth.require_admin(request)
        from pathlib import Path
        return (Path(__file__).parent/'docs/account-lifecycle.html').read_text(encoding='utf-8')

    @app.get('/registration-availability')
    def availability(username: str='',email: str=''):
        try:return life.availability(username,email)
        except ValueError as exc:raise HTTPException(422,str(exc)) from exc

    @app.get('/registration-security')
    def security_page(token: str=''):
        try:
            user=enroll_user(token);method=life.info(user['id'])['mfa_method'];safe=html.escape(token,quote=True)
            body='<p>Email verificata. Completa il secondo fattore prima della richiesta di approvazione.</p>'
            if method=='totp':
                if not user['totp_pending_enc']:auth.begin_totp(user['id']);user=auth.get_user(user['id'])
                body+=auth.totp_qr_svg(auth.totp_uri(user)).decode()+'<p>Chiave manuale: <code>'+html.escape(auth._open(user['totp_pending_enc']))+'</code></p>'
            else:body+='<p>Il codice viene inviato alla tua email verificata. Scade dopo 10 minuti.</p>'
            body+='<form method="post" class="auth-form"><input type="hidden" name="token" value="'+safe+'">'
            if method=='email':body+='<button name="action" value="send" formnovalidate>Invia codice email</button>'
            body+='<label>Codice di verifica<input name="code" inputmode="numeric" autocomplete="one-time-code" pattern="[0-9]{6}" maxlength="6" required></label><button name="action" value="verify">Verifica e richiedi approvazione</button></form>'
            return page('Verifica secondo fattore',body)
        except ValueError as exc:return page('Verifica non disponibile','<p>'+html.escape(str(exc))+'</p>')

    @app.post('/registration-security')
    async def security_submit(request: Request):
        form=await request.form();token=str(form.get('token',''))
        try:
            user=enroll_user(token);method=life.info(user['id'])['mfa_method']
            if form.get('action')=='send':mfa.send(user['id'],'enroll');return page('Codice inviato','<a href="/registration-security?token='+html.escape(token,quote=True)+'">Inserisci il codice ricevuto</a>')
            if method=='email':
                if not mfa.verify(user['id'],'enroll',str(form.get('code',''))):raise ValueError('Codice non valido, scaduto o troppi tentativi')
            else:
                with auth.db() as con:
                    con.execute('CREATE TABLE IF NOT EXISTS account_enroll_attempts(token_hash TEXT PRIMARY KEY,attempts INTEGER NOT NULL)')
                    key=auth._token_hash(token);con.execute('INSERT OR IGNORE INTO account_enroll_attempts VALUES(?,0)',(key,))
                    count=con.execute('SELECT attempts FROM account_enroll_attempts WHERE token_hash=?',(key,)).fetchone()[0]
                    if count>=5:raise ValueError('Troppi tentativi; richiedi un nuovo link')
                    con.execute('UPDATE account_enroll_attempts SET attempts=attempts+1 WHERE token_hash=?',(key,))
                auth.enable_totp(user['id'],str(form.get('code','')))
            if not auth._consume_email_token(token,'enrollment'):raise ValueError('Verifica già completata')
            with auth.db() as con:con.execute("UPDATE account_lifecycle SET state='pending' WHERE user_id=? AND state='enrolling'",(user['id'],))
            life.ready(user['id'])
            return page('In attesa di approvazione','<p>Email e secondo fattore verificati. La richiesta è stata inoltrata agli amministratori; riceverai una comunicazione quando approvata.</p>')
        except ValueError as exc:return page('Verifica non riuscita','<p>'+html.escape(str(exc))+'</p><a href="/registration-security?token='+html.escape(token,quote=True)+'">Riprova</a>')

    @app.post('/login-email-code')
    async def login_code(request: Request):
        form=await request.form();user=auth._find_user(str(form.get('identifier','')))
        if user and user['active'] and auth._verify_password(str(form.get('password','')),user['password_hash']) and life.info(user['id']).get('mfa_method')=='email':
            try:mfa.send(user['id'],'login')
            except ValueError as exc:raise HTTPException(400,str(exc)) from exc
        return {'message':'Se credenziali e metodo email sono corretti, riceverai un codice. Inseriscilo nel campo codice e premi Accedi.'}

    @app.get('/reactivate-account')
    def reactivate(token: str=''):
        if token:return page('Richiesta riattivazione','<p>'+('Richiesta verificata: attendi approvazione admin.' if life.confirm_reactivation(token) else 'Link non valido o scaduto.')+'</p>')
        return page('Richiedi riattivazione','<form method="post" class="auth-form"><label>Email o username<input name="identifier" required></label><button>Invia richiesta</button></form>')

    @app.post('/reactivate-account')
    async def request_reactivate(request: Request):
        life.request_reactivation(str((await request.form()).get('identifier','')))
        return page('Richiesta ricevuta','<p>Se l’account è riattivabile riceverai una mail di verifica.</p>')

    @app.get('/account-projects/{token}')
    def download(token: str):
        with auth.db() as con:
            life.init(con);row=con.execute("SELECT * FROM account_archives WHERE token=? AND state='ready' AND expires_at>?",(token,int(time.time()))).fetchone()
        if not row:raise HTTPException(404,'Archivio non disponibile o scaduto')
        path=life.root()/(row['id']+'.zip')
        if path.is_symlink() or not path.is_file():raise HTTPException(404,'Archivio non disponibile')
        return FileResponse(path,media_type='application/zip',filename='MTA-projects.zip',headers={'Cache-Control':'private, no-store','Referrer-Policy':'no-referrer','X-Robots-Tag':'noindex, nofollow'})

    @app.get('/api/admin/account-lifecycle')
    def admin_list(request: Request):auth.require_admin(request);return life.listings()

    @app.put('/api/admin/account-lifecycle/settings')
    def admin_settings(request: Request,body: dict):
        auth.require_admin(request)
        try:return life.settings(body)
        except ValueError as exc:raise HTTPException(422,str(exc)) from exc

    @app.post('/api/admin/users/{uid}/purge')
    def admin_purge(uid: int,request: Request,body: dict):
        actor=auth.require_admin(request)
        try:return life.confirmation(actor['id'],uid,body)
        except ValueError as exc:raise HTTPException(409,str(exc)) from exc

    @app.post('/api/account/delete-request')
    def delete_self(request: Request,body: dict):
        user=auth.require_user(request)
        if user['role']=='admin':raise HTTPException(403,'Gli amministratori non possono richiedere la propria cancellazione')
        if body.get('username')!=user['username'] or body.get('confirm') is not True:raise HTTPException(422,'Conferma la cancellazione digitando lo username')
        try:return life.retire(user['id'],user['id'],privacy_request=body.get('privacy_request') is True)
        except ValueError as exc:raise HTTPException(409,str(exc)) from exc
