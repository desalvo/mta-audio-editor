"""Email OTP as a server-controlled alternative to authenticator TOTP."""
import hashlib
import hmac
import secrets
import time
from . import auth


def init(con):
    con.execute('''CREATE TABLE IF NOT EXISTS account_email_mfa(
      user_id INTEGER NOT NULL,purpose TEXT NOT NULL,digest TEXT NOT NULL,salt TEXT NOT NULL,
      expires INTEGER NOT NULL,attempts INTEGER NOT NULL DEFAULT 0,sent_at INTEGER NOT NULL,
      PRIMARY KEY(user_id,purpose),FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE)''')


def digest(uid,purpose,salt,code):
    return hmac.new(auth._app_key(),f'{uid}:{purpose}:{salt}:{code}'.encode(),hashlib.sha256).hexdigest()


def send(uid,purpose):
    if purpose not in ('enroll','login'):raise ValueError('Scopo OTP non valido')
    from . import account_lifecycle as life
    user=auth.get_user(uid)
    if not user or not user['email_confirmed']:raise ValueError('Verifica prima la tua email')
    if purpose=='login' and not user['active']:raise ValueError('Account non attivo')
    cfg=auth.get_smtp_config()
    if not cfg.get('host') or not cfg.get('from_email'):raise ValueError('SMTP non configurato: chiedi all’amministratore o usa Authenticator per la registrazione')
    now=int(time.time());code=f'{secrets.randbelow(1000000):06d}';salt=secrets.token_hex(16)
    with auth.db() as con:
        life.init(con);init(con);con.execute('BEGIN IMMEDIATE')
        prior=con.execute('SELECT sent_at FROM account_email_mfa WHERE user_id=? AND purpose=?',(uid,purpose)).fetchone()
        if prior and now-prior[0]<60:raise ValueError('Attendi 60 secondi prima di richiedere un altro codice')
        con.execute('INSERT INTO account_email_mfa VALUES(?,?,?,?,?,0,?) ON CONFLICT(user_id,purpose) DO UPDATE SET digest=excluded.digest,salt=excluded.salt,expires=excluded.expires,attempts=0,sent_at=excluded.sent_at',(uid,purpose,digest(uid,purpose,salt,code),salt,now+600,now))
        life.enqueue(con,'otp:'+str(uid)+':'+purpose+':'+salt,user['email'],'Codice di verifica MTA',f'Il tuo codice è {code}. Scade tra 10 minuti. Non condividerlo. Se non hai richiesto questo accesso ignora il messaggio.',uid=uid)
    life.send_pending()


def verify(uid,purpose,code):
    with auth.db() as con:
        init(con);con.execute('BEGIN IMMEDIATE')
        row=con.execute('SELECT * FROM account_email_mfa WHERE user_id=? AND purpose=?',(uid,purpose)).fetchone()
        if not row or row['expires']<time.time() or row['attempts']>=5:return False
        con.execute('UPDATE account_email_mfa SET attempts=attempts+1 WHERE user_id=? AND purpose=?',(uid,purpose))
        if not hmac.compare_digest(row['digest'],digest(uid,purpose,row['salt'],str(code))):return False
        con.execute('DELETE FROM account_email_mfa WHERE user_id=? AND purpose=?',(uid,purpose));return True
