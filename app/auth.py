from __future__ import annotations

from app.secure_https import https_urlopen

import base64
import hashlib
import hmac
import html
import io
import logging
import os
import re
import secrets
import smtplib
import sqlite3
import ssl
import struct
import time
from contextlib import contextmanager
from email.message import EmailMessage
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlencode, urlsplit
from urllib.request import Request as UrlRequest

import qrcode
import qrcode.image.svg
from fastapi import HTTPException, Request

LOGGER = logging.getLogger(__name__)

SESSION_COOKIE = "mta_session"
SESSION_SECONDS = 12 * 3600
TOKEN_SECONDS = 24 * 3600
MODEL_TOKEN_SECONDS = int(os.getenv("MTA_MODEL_TOKEN_SECONDS", str(30 * 24 * 3600)))
PBKDF2_ITERS = 310_000
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
DATA_ROOT: Path | None = None


def data_root() -> Path:
    if DATA_ROOT is not None:
        return Path(DATA_ROOT).resolve()
    from .runtime_paths import application_data_root
    return application_data_root()


def db_path() -> Path:
    return data_root() / "auth.sqlite3"


def secret_path() -> Path:
    return data_root() / ".auth-secret"


def now_ts() -> int:
    return int(time.time())


@contextmanager
def db():
    root = data_root()
    root.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(db_path())
    con.row_factory = sqlite3.Row
    # Immutable subscription records can only be removed by a separately
    # authorized, owner-scoped account erasure on this exact connection.
    con.create_function('mta_subscription_erasure',2,lambda table,key:0)
    con.create_function('mta_nc_erasure',2,lambda table,key:0)
    con.create_function('mta_worker_erasure',2,lambda table,key:0)
    con.create_function('mta_worker_loss_erasure',1,lambda key:0)
    con.create_function('mta_operator_refund_erasure',1,lambda key:0)
    con.execute("PRAGMA foreign_keys=ON")
    try:
        yield con
    except BaseException:
        con.rollback()
        raise
    else:
        con.commit()
    finally:
        con.close()


def _app_key() -> bytes:
    path = secret_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raw = path.read_bytes()
        if len(raw) >= 32:
            return raw[:32]
    key = secrets.token_bytes(32)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as fh:
        fh.write(key)
    return key


def _seal(value: str) -> str:
    if not value:
        return ""
    key = _app_key()
    nonce = secrets.token_bytes(16)
    raw = value.encode("utf-8")
    stream = bytearray()
    counter = 0
    while len(stream) < len(raw):
        stream.extend(hmac.new(key, b"enc:"+nonce+struct.pack(">I", counter), hashlib.sha256).digest())
        counter += 1
    cipher = bytes(a ^ b for a, b in zip(raw, stream))
    tag = hmac.new(key, b"tag:"+nonce+cipher, hashlib.sha256).digest()
    return base64.urlsafe_b64encode(nonce+cipher+tag).decode("ascii")


def _open(value: str) -> str:
    if not value:
        return ""
    try:
        blob = base64.urlsafe_b64decode(value.encode("ascii"))
        nonce, cipher, tag = blob[:16], blob[16:-32], blob[-32:]
        key = _app_key()
        expected = hmac.new(key, b"tag:"+nonce+cipher, hashlib.sha256).digest()
        if not hmac.compare_digest(tag, expected):
            return ""
        stream = bytearray()
        counter = 0
        while len(stream) < len(cipher):
            stream.extend(hmac.new(key, b"enc:"+nonce+struct.pack(">I", counter), hashlib.sha256).digest())
            counter += 1
        return bytes(a ^ b for a, b in zip(cipher, stream)).decode("utf-8")
    except Exception:
        return ""


def _add_column(con: sqlite3.Connection, table: str, definition: str) -> None:
    name = definition.split()[0]
    cols = {row[1] for row in con.execute(f"PRAGMA table_info({table})")}
    if name not in cols:
        con.execute(f"ALTER TABLE {table} ADD COLUMN {definition}")
        if table=='users' and name=='workspace_quota_explicit':
            con.execute("UPDATE users SET workspace_quota_explicit=1 WHERE role='admin' AND workspace_quota_bytes NOT IN (0,5368709120)")


def init_auth_db() -> None:
    with db() as con:
        con.executescript("""
        CREATE TABLE IF NOT EXISTS users(
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          username TEXT NOT NULL UNIQUE COLLATE NOCASE,
          email TEXT NOT NULL UNIQUE COLLATE NOCASE,
          display_name TEXT NOT NULL DEFAULT '',
          password_hash TEXT NOT NULL,
          role TEXT NOT NULL DEFAULT 'user',
          active INTEGER NOT NULL DEFAULT 0,
          email_confirmed INTEGER NOT NULL DEFAULT 0,
          pending_email TEXT NOT NULL DEFAULT '',
          totp_secret_enc TEXT NOT NULL DEFAULT '',
          totp_pending_enc TEXT NOT NULL DEFAULT '',
          totp_enabled INTEGER NOT NULL DEFAULT 0,
          created_at INTEGER NOT NULL,
          updated_at INTEGER NOT NULL,
          approved_at INTEGER,
          approved_by INTEGER,
          last_login_at INTEGER,
          workspace_quota_bytes INTEGER NOT NULL DEFAULT 5368709120,
          language TEXT NOT NULL DEFAULT 'auto',
          browser_language TEXT NOT NULL DEFAULT 'en',
          limits_expanded INTEGER NOT NULL DEFAULT 0,
          FOREIGN KEY(approved_by) REFERENCES users(id)
        );
        CREATE TABLE IF NOT EXISTS email_tokens(
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          user_id INTEGER NOT NULL,
          purpose TEXT NOT NULL,
          token_hash TEXT NOT NULL UNIQUE,
          expires_at INTEGER NOT NULL,
          used_at INTEGER,
          FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS social_identities(
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          user_id INTEGER NOT NULL,
          provider TEXT NOT NULL,
          subject TEXT NOT NULL,
          created_at INTEGER NOT NULL,
          UNIQUE(provider,subject),
          FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS sessions(
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          user_id INTEGER NOT NULL,
          token_hash TEXT NOT NULL UNIQUE,
          created_at INTEGER NOT NULL,
          expires_at INTEGER NOT NULL,
          user_agent_hash TEXT NOT NULL DEFAULT '',
          FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS model_access_tokens(
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          user_id INTEGER NOT NULL,
          token_hash TEXT NOT NULL UNIQUE,
          scopes TEXT NOT NULL DEFAULT 'models:read',
          label TEXT NOT NULL DEFAULT '',
          created_at INTEGER NOT NULL,
          expires_at INTEGER NOT NULL,
          revoked_at INTEGER,
          FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_model_access_tokens_user ON model_access_tokens(user_id);
        CREATE TABLE IF NOT EXISTS smtp_config(
          id INTEGER PRIMARY KEY CHECK(id=1),
          host TEXT NOT NULL DEFAULT '',
          port INTEGER NOT NULL DEFAULT 587,
          security TEXT NOT NULL DEFAULT 'starttls',
          username TEXT NOT NULL DEFAULT '',
          password_enc TEXT NOT NULL DEFAULT '',
          from_email TEXT NOT NULL DEFAULT '',
          from_name TEXT NOT NULL DEFAULT 'MTA Audio Editor'
        );
        INSERT OR IGNORE INTO smtp_config(id) VALUES(1);
        """)
        # Migration safety for early development DBs.
        for definition in (
            "display_name TEXT NOT NULL DEFAULT ''",
            "pending_email TEXT NOT NULL DEFAULT ''",
            "totp_secret_enc TEXT NOT NULL DEFAULT ''",
            "totp_pending_enc TEXT NOT NULL DEFAULT ''",
            "updated_at INTEGER NOT NULL DEFAULT 0",
            "workspace_quota_bytes INTEGER NOT NULL DEFAULT 0",
            "workspace_quota_explicit INTEGER NOT NULL DEFAULT 0",
            "language TEXT NOT NULL DEFAULT 'auto'",
            "browser_language TEXT NOT NULL DEFAULT 'en'",
            "limits_expanded INTEGER NOT NULL DEFAULT 0",
        ):
            _add_column(con, "users", definition)

    _bootstrap_admin()


def _password_hash_unchecked(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, PBKDF2_ITERS)
    return "pbkdf2_sha256${}${}${}".format(
        PBKDF2_ITERS,
        base64.urlsafe_b64encode(salt).decode(),
        base64.urlsafe_b64encode(digest).decode(),
    )


def _password_hash(password: str) -> str:
    if len(password) < 10:
        raise ValueError("La password deve contenere almeno 10 caratteri.")
    return _password_hash_unchecked(password)


def _verify_password(password: str, encoded: str) -> bool:
    try:
        algo, iterations, salt_s, digest_s = encoded.split("$", 3)
        if algo != "pbkdf2_sha256":
            return False
        salt = base64.urlsafe_b64decode(salt_s)
        expected = base64.urlsafe_b64decode(digest_s)
        actual = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, int(iterations))
        return hmac.compare_digest(actual, expected)
    except Exception:
        return False


def _bootstrap_admin() -> None:
    username = os.getenv("MTA_ADMIN_USERNAME", "admin").strip() or "admin"
    password = os.getenv("MTA_ADMIN_PASSWORD", "")
    email = os.getenv("MTA_ADMIN_EMAIL", "").strip().lower() or f"{username}@localhost.invalid"
    with db() as con:
        if con.execute("SELECT COUNT(*) FROM users").fetchone()[0]:
            return
        if not password:
            return
        ts = now_ts()
        con.execute(
            """INSERT INTO users(username,email,display_name,password_hash,role,active,email_confirmed,created_at,updated_at,approved_at,workspace_quota_bytes)
               VALUES(?,?,?,?, 'admin',1,1,?,?,?,0)""",
            (username, email, "Administrator", _password_hash_unchecked(password), ts, ts, ts),
        )


def get_user(user_id: int):
    init_auth_db()
    with db() as con:
        return con.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()


def _find_user(identifier: str):
    init_auth_db()
    value = identifier.strip()
    with db() as con:
        return con.execute(
            "SELECT * FROM users WHERE username=? COLLATE NOCASE OR email=? COLLATE NOCASE",
            (value, value),
        ).fetchone()


def social_providers_for_user(user_id: int) -> list[str]:
    init_auth_db()
    with db() as con:
        rows=con.execute("SELECT provider FROM social_identities WHERE user_id=? ORDER BY provider",(user_id,)).fetchall()
    return [row["provider"] for row in rows]


def public_user(row) -> dict:
    return {
        "id": row["id"],
        "username": row["username"],
        "email": row["email"],
        "pending_email": row["pending_email"] if "pending_email" in row.keys() else "",
        "display_name": row["display_name"] or "",
        "role": row["role"],
        "active": bool(row["active"]),
        "email_confirmed": bool(row["email_confirmed"]),
        "totp_enabled": bool(row["totp_enabled"]),
        "totp_pending": bool(row["totp_pending_enc"]),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "approved_at": row["approved_at"],
        "last_login_at": row["last_login_at"],
        "workspace_quota_bytes": (int(row["workspace_quota_bytes"] or 0) if row["role"]!="admin" or ("workspace_quota_explicit" in row.keys() and row["workspace_quota_explicit"]) else 0) if "workspace_quota_bytes" in row.keys() else 0,
        "limits_expanded": bool(row["limits_expanded"]) if "limits_expanded" in row.keys() else False,
        "language": row["language"] if "language" in row.keys() else "auto",
        "browser_language": row["browser_language"] if "browser_language" in row.keys() else "en",
        "social_providers": social_providers_for_user(row["id"]),
    }


def find_user(identifier: str):
    return _find_user(identifier)


def list_users() -> list[dict]:
    init_auth_db()
    with db() as con:
        rows = con.execute("SELECT * FROM users ORDER BY created_at DESC,id DESC").fetchall()
    return [public_user(row) for row in rows]


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _create_email_token(user_id: int, purpose: str = "verify-email") -> str:
    token = secrets.token_urlsafe(32)
    with db() as con:
        con.execute("DELETE FROM email_tokens WHERE user_id=? AND purpose=? AND used_at IS NULL", (user_id,purpose))
        con.execute(
            "INSERT INTO email_tokens(user_id,purpose,token_hash,expires_at) VALUES(?,?,?,?)",
            (user_id,purpose,_token_hash(token),now_ts()+TOKEN_SECONDS),
        )
    return token


def _consume_email_token(token: str, purpose: str = "verify-email"):
    with db() as con:
        row = con.execute(
            """SELECT * FROM email_tokens
               WHERE token_hash=? AND purpose=? AND used_at IS NULL AND expires_at>?""",
            (_token_hash(token),purpose,now_ts()),
        ).fetchone()
        if not row:
            return None
        con.execute("UPDATE email_tokens SET used_at=? WHERE id=?", (now_ts(),row["id"]))
        return row


def _base_url() -> str:
    return os.getenv("MTA_PUBLIC_URL", "").rstrip("/")


def _verification_link(token: str, base_url: str = "") -> str:
    path = f"/verify-email?token={quote(token)}"
    base = (_base_url() or base_url).rstrip("/")
    return (base + path) if base else path


def _send_verification_email(user_id: int, token: str, base_url: str = "", recipient: str | None = None) -> None:
    row = get_user(user_id)
    if not row:
        return
    link = _verification_link(token, base_url)
    send_mail(
        [recipient or row["email"]],
        "Conferma la tua email · MTA Audio Editor",
        f"Conferma la tua email aprendo questo link:\n{link}\n\nIl link scade tra 24 ore.",
        f"<p>Conferma la tua email per <b>MTA Audio Editor</b>.</p><p><a href='{html.escape(link)}'>Conferma email</a></p><p>Il link scade tra 24 ore.</p>",
    )


def _notify_admins_registration(user, provider: str = "local") -> None:
    with db() as con:
        admins=con.execute("SELECT email FROM users WHERE role='admin' AND active=1 AND email_confirmed=1 AND email<>''").fetchall()
    recipients=[x["email"] for x in admins]
    if not recipients:
        return
    source = provider if provider != "local" else "registrazione locale"
    from .admin_navigation import action, settings_target
    plain=f"Nuovo utente {user['username']} ({user['email']}) tramite {source}. L'account richiede approvazione amministratore."
    plain,link=action(plain,settings_target('pending',user['id']),'Apri richiesta di approvazione')
    send_mail(recipients,"Nuovo utente in attesa · MTA Audio Editor",plain,'<p>'+html.escape(plain.split('\n\n',1)[0])+'</p>'+link)


def register_user(username: str, email: str, display_name: str, password: str, base_url: str = "", *, require_second_factor: bool=False, mfa_method: str="email"):
    username = username.strip()
    email = email.strip().lower()
    display_name = display_name.strip()[:120]
    if not (3 <= len(username) <= 64) or not re.fullmatch(r"[A-Za-z0-9._-]+", username):
        raise ValueError("Username non valido: usa 3-64 caratteri, lettere, numeri, '.', '_' o '-'.")
    if not EMAIL_RE.fullmatch(email):
        raise ValueError("Indirizzo email obbligatorio e non valido.")
    from . import account_lifecycle as lifecycle
    if mfa_method not in ('email','totp'):raise ValueError('Metodo secondo fattore non valido')
    available=lifecycle.availability(username,email)
    if not available['username_available'] or not available['email_available']:raise ValueError('Username o email già utilizzati. Richiedi la riattivazione se sei il titolare.')
    ts = now_ts()
    try:
        with db() as con:
            cur = con.execute(
                """INSERT INTO users(username,email,display_name,password_hash,role,active,email_confirmed,created_at,updated_at,workspace_quota_bytes)
                   VALUES(?,?,?,?, 'user',0,0,?,?,5368709120)""",
                (username,email,display_name,_password_hash(password),ts,ts),
            )
            user_id = cur.lastrowid
            from .i18n import current_language
            con.execute("UPDATE users SET browser_language=? WHERE id=?",(current_language.get(),user_id))
            lifecycle.reserve(con,user_id,username,email)
    except sqlite3.IntegrityError as exc:
        raise ValueError("Username o email già registrati.") from exc
    lifecycle.register(user_id,require_second_factor,mfa_method)
    token = _create_email_token(user_id)
    # Registration remains successful even if SMTP is not configured; the admin can
    # configure SMTP and the user can request a resend afterwards.
    try:
        _send_verification_email(user_id, token, base_url)
    except Exception:
        LOGGER.exception("Unable to send registration verification email for user_id=%s", user_id)
    user=public_user(get_user(user_id))
    try:
        if not require_second_factor:_notify_admins_registration(user)
    except Exception:
        LOGGER.exception("Unable to notify administrators about registration user_id=%s", user_id)
    return user, token


def confirm_email(token: str) -> bool:
    """Promote a pending address atomically; never deactivate an existing user."""
    with db() as con:
        tok = con.execute(
            """SELECT * FROM email_tokens WHERE token_hash=? AND purpose IN
               ('verify-email', 'verify-email-change') AND used_at IS NULL AND expires_at>?""",
            (_token_hash(token), now_ts()),
        ).fetchone()
        if tok is None:
            return False
        user = con.execute("SELECT * FROM users WHERE id=?", (tok["user_id"],)).fetchone()
        if user is None:
            return False
        if tok["purpose"] == "verify-email-change":
            if not user["pending_email"]:
                return False
            try:
                con.execute("UPDATE users SET email=?,pending_email='',email_confirmed=1,updated_at=? WHERE id=?",
                            (user["pending_email"], now_ts(),user["id"]))
            except sqlite3.IntegrityError:
                return False
        else:
            con.execute("UPDATE users SET email_confirmed=1,updated_at=? WHERE id=?", (now_ts(),user["id"]))
        con.execute("UPDATE email_tokens SET used_at=? WHERE id=?", (now_ts(),tok["id"]))
    return True


def resend_verification(identifier: str, base_url: str = "") -> None:
    row = _find_user(identifier)
    if not row or row["email_confirmed"]:
        return
    token = _create_email_token(row["id"])
    try:
        _send_verification_email(row["id"],token,base_url)
    except Exception:
        LOGGER.exception("Unable to resend verification email for user_id=%s", row["id"])


OAUTH_PROVIDERS = {
    "google": {
        "label": "Google", "enabled_env": "MTA_OAUTH_GOOGLE_ENABLED", "client_env": "MTA_OAUTH_GOOGLE_CLIENT_ID", "secret_env": "MTA_OAUTH_GOOGLE_CLIENT_SECRET",
        "authorize": "https://accounts.google.com/o/oauth2/v2/auth", "token": "https://oauth2.googleapis.com/token", "userinfo": "https://openidconnect.googleapis.com/v1/userinfo", "scope": "openid email profile",
    },
    "github": {
        "label": "GitHub", "enabled_env": "MTA_OAUTH_GITHUB_ENABLED", "client_env": "MTA_OAUTH_GITHUB_CLIENT_ID", "secret_env": "MTA_OAUTH_GITHUB_CLIENT_SECRET",
        "authorize": "https://github.com/login/oauth/authorize", "token": "https://github.com/login/oauth/access_token", "userinfo": "https://api.github.com/user", "scope": "read:user user:email",
    },
    "facebook": {
        "label": "Facebook", "enabled_env": "MTA_OAUTH_FACEBOOK_ENABLED", "client_env": "MTA_OAUTH_FACEBOOK_CLIENT_ID", "secret_env": "MTA_OAUTH_FACEBOOK_CLIENT_SECRET",
        "authorize": "https://www.facebook.com/dialog/oauth", "token": "https://graph.facebook.com/oauth/access_token", "userinfo": "https://graph.facebook.com/me?fields=id,name,email", "scope": "email,public_profile",
    },
}

def oauth_enabled(provider: str) -> bool:
    from .social_settings import provider as configuration
    return bool(configuration(provider))

def oauth_public_providers() -> list[dict]:
    return [{"id":key,"label":cfg["label"]} for key,cfg in OAUTH_PROVIDERS.items() if oauth_enabled(key)]

def oauth_redirect_uri(provider: str, request: Request) -> str:
    from .social_settings import full
    base=(full()['public_url'] or _base_url() or str(request.base_url).rstrip('/')).rstrip('/')
    return f"{base}/oauth/{provider}/callback"

def oauth_make_state(provider: str) -> tuple[str,str]:
    init_auth_db()
    nonce=secrets.token_urlsafe(24); payload=f"{provider}|{now_ts()+600}|{nonce}".encode()
    raw=base64.urlsafe_b64encode(payload).decode().rstrip('=');sig=hmac.new(_app_key(),raw.encode(),hashlib.sha256).hexdigest()
    with db() as con:
        con.execute('CREATE TABLE IF NOT EXISTS oauth_nonces(hash TEXT PRIMARY KEY,expires INTEGER NOT NULL)')
        con.execute('DELETE FROM oauth_nonces WHERE expires<?',(now_ts(),))
        con.execute('INSERT INTO oauth_nonces VALUES(?,?)',(_token_hash(nonce),now_ts()+600))
    return f"{raw}.{sig}",nonce

def oauth_verify_state(provider: str, state: str, cookie_nonce: str) -> bool:
    try:
        raw,sig=state.split('.',1); expected=hmac.new(_app_key(),raw.encode(),hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig,expected): return False
        payload=base64.urlsafe_b64decode(raw+'='*(-len(raw)%4)).decode(); p,exp,nonce=payload.split('|',2)
        if not (p==provider and now_ts()<=int(exp)<=now_ts()+600 and bool(cookie_nonce) and hmac.compare_digest(nonce,cookie_nonce)):return False
        with db() as con:
            return con.execute('DELETE FROM oauth_nonces WHERE hash=? AND expires>=?',(_token_hash(nonce),now_ts())).rowcount==1
    except Exception: return False

def oauth_authorize_url(provider: str, request: Request) -> tuple[str,str]:
    if not oauth_enabled(provider): raise ValueError("Provider social non abilitato.")
    from .social_settings import provider as credentials
    cfg=OAUTH_PROVIDERS[provider]; state,nonce=oauth_make_state(provider)
    params={"client_id":credentials(provider)["client_id"],"redirect_uri":oauth_redirect_uri(provider,request),"response_type":"code","scope":cfg["scope"],"state":state}
    if provider in ('google','github'):
        verifier=oauth_pkce(nonce)
        params.update(code_challenge=base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip('='),code_challenge_method='S256')
    if provider=="google": params["prompt"]="select_account"
    return cfg["authorize"]+'?'+urlencode(params),nonce

OAUTH_HTTPS_HOSTS = frozenset({
    "oauth2.googleapis.com",
    "openidconnect.googleapis.com",
    "github.com",
    "api.github.com",
    "graph.facebook.com",
})


def _validate_oauth_endpoint(url: str) -> str:
    parsed = urlsplit(url)
    if parsed.scheme != "https" or not parsed.hostname or parsed.hostname.lower() not in OAUTH_HTTPS_HOSTS:
        raise ValueError("Endpoint OAuth non consentito: sono ammessi solo gli endpoint HTTPS dei provider configurati.")
    if parsed.username or parsed.password or parsed.port not in (None, 443):
        raise ValueError("Endpoint OAuth non consentito.")
    return url


def _oauth_json(url: str, *, data: dict | None = None, headers: dict | None = None) -> dict | list:
    safe_url = _validate_oauth_endpoint(url)
    body = urlencode(data).encode() if data is not None else None
    request_headers = {"Accept": "application/json", "User-Agent": "MTA-Audio-Editor"}
    request_headers.update(headers or {})
    request = UrlRequest(safe_url, data=body, headers=request_headers)  # noqa: S310
    # S310 is intentionally suppressed only after strict HTTPS + provider-host validation above.
    with https_urlopen(request, timeout=15) as resp:  # noqa: S310
        payload=resp.read(1024*1024+1)
        if len(payload)>1024*1024:raise ValueError("Risposta OAuth troppo grande")
        return __import__("json").loads(payload.decode())

def oauth_pkce(nonce):
    return base64.urlsafe_b64encode(hmac.new(_app_key(),('pkce:'+nonce).encode(),hashlib.sha256).digest()).decode().rstrip('=')


def oauth_exchange_profile(provider: str, code: str, request: Request) -> dict:
    if not oauth_enabled(provider): raise ValueError("Provider social non abilitato.")
    from .social_settings import provider as credentials
    cfg=OAUTH_PROVIDERS[provider]
    data={"client_id":credentials(provider)["client_id"],"client_secret":credentials(provider)["client_secret"],"code":code,"redirect_uri":oauth_redirect_uri(provider,request),"grant_type":"authorization_code"}
    if provider in ('google','github'):data['code_verifier']=oauth_pkce(request.cookies.get('mta_oauth_state',''))
    token=_oauth_json(cfg['token'],data=data)
    access=token.get("access_token") if isinstance(token,dict) else None
    if not access: raise ValueError("Il provider non ha restituito un access token valido.")
    profile=_oauth_json(cfg["userinfo"],headers={"Authorization":f"Bearer {access}"})
    if not isinstance(profile,dict):raise ValueError("Profilo OAuth non valido")
    if provider=="github":
        subject=str(profile.get("id",'')); emails=_oauth_json("https://api.github.com/user/emails",headers={"Authorization":f"Bearer {access}"})
        if not isinstance(emails,list):raise ValueError("Email OAuth non valide")
        choices=[e for e in emails if isinstance(e,dict) and e.get("verified") is True]; primary=next((e for e in choices if e.get("primary")),choices[0] if choices else None)
        email=str(primary.get("email",'')).lower() if primary else ''; verified=bool(primary)
        name=str(profile.get("name") or profile.get("login") or '')
    elif provider=="google":
        subject=str(profile.get("sub",''));email=str(profile.get("email") or '').lower();verified=profile.get("email_verified") is True;name=str(profile.get("name") or '')
    else:
        subject=str(profile.get("id",''));email=str(profile.get("email") or '').lower();verified=bool(email);name=str(profile.get("name") or '')
    if not subject or not EMAIL_RE.fullmatch(email) or not verified: raise ValueError("Il provider non ha fornito un indirizzo email verificato utilizzabile.")
    return {"subject":subject,"email":email,"name":name[:120],"email_verified":provider!="facebook"}

def _social_username(provider: str, email: str) -> str:
    base=re.sub(r"[^A-Za-z0-9._-]","-",email.split('@',1)[0]).strip('-._') or provider
    base=(base[:48]+'-'+provider)[:60]; candidate=base;i=1
    with db() as con:
        while con.execute("SELECT 1 FROM users WHERE username=? COLLATE NOCASE",(candidate,)).fetchone(): i+=1;candidate=f"{base[:55]}-{i}"
    return candidate

def social_login_or_register(provider: str, profile: dict):
    init_auth_db(); subject=profile["subject"]
    from . import account_lifecycle as lifecycle
    with db() as setup:lifecycle.init(setup)
    with db() as con:
        con.execute('BEGIN IMMEDIATE')
        identity=con.execute("SELECT user_id FROM social_identities WHERE provider=? AND subject=?",(provider,subject)).fetchone()
        if identity:
            con.commit()  # Release the write reservation before nested public-user lookups.
            return public_user(get_user(identity["user_id"])),False
        if con.execute("SELECT 1 FROM users WHERE email=? COLLATE NOCASE",(profile["email"],)).fetchone(): raise ValueError("Esiste già un account con questa email. Accedi con il metodo già associato all'account.")
        reserved=con.execute('SELECT user_id FROM account_identity_reservations WHERE kind="email" AND digest=?',(lifecycle.identity("email",profile["email"]),)).fetchone()
        if reserved:raise ValueError("Email già utilizzata: richiedi la riattivazione dell’account")
        ts=now_ts();cur=con.execute("INSERT INTO users(username,email,display_name,password_hash,role,active,email_confirmed,created_at,updated_at,workspace_quota_bytes) VALUES(?,?,?,?, 'user',0,?, ?,?,5368709120)",(_social_username(provider,profile["email"]),profile["email"],profile["name"],"social$"+provider,int(profile.get("email_verified",True)),ts,ts));uid=cur.lastrowid
        from .i18n import current_language
        con.execute("UPDATE users SET browser_language=? WHERE id=?",(current_language.get(),uid))
        lifecycle.reserve(con,uid,con.execute("SELECT username FROM users WHERE id=?",(uid,)).fetchone()[0],profile["email"])
        con.execute("INSERT INTO social_identities(user_id,provider,subject,created_at) VALUES(?,?,?,?)",(uid,provider,subject,ts))
    from .account_lifecycle import register as register_lifecycle
    register_lifecycle(uid)
    user=public_user(get_user(uid))
    if not user['email_confirmed']:
        try:_send_verification_email(uid,_create_email_token(uid))
        except Exception:LOGGER.warning('Unable to send social email verification user_id=%s',uid)
    return user,True

def authenticate(identifier: str, password: str, code: str = ""):
    init_auth_db()
    row = _find_user(identifier)
    if not row or not _verify_password(password,row["password_hash"]):
        return None, "Credenziali non valide."
    if not row["email_confirmed"]:
        return None, "Conferma prima il tuo indirizzo email."
    if not row["active"]:
        return None, "Account in attesa dell'approvazione di un amministratore."
    from .account_lifecycle import info
    life=info(row['id'])
    if life.get('second_factor_required') and life.get('mfa_method')=='email':
        from .account_mfa import verify
        if not verify(row['id'],'login',code):return None,'Codice email richiesto, non valido o scaduto. Usa Invia codice email.'
    if row["totp_enabled"] and not (life.get("second_factor_required") and life.get("mfa_method")=="email"):
        secret = _open(row["totp_secret_enc"])
        if not _verify_totp(secret, code):
            return None, "Codice TOTP obbligatorio o non valido."
    with db() as con:
        con.execute("UPDATE users SET last_login_at=?,updated_at=? WHERE id=?", (now_ts(),now_ts(),row["id"]))
    return get_user(row["id"]), ""


def create_session(user_id: int, request: Request) -> str:
    token = secrets.token_urlsafe(40)
    ua = hashlib.sha256(request.headers.get("user-agent","").encode()).hexdigest()
    with db() as con:
        con.execute("DELETE FROM sessions WHERE expires_at<?",(now_ts(),))
        con.execute(
            "INSERT INTO sessions(user_id,token_hash,created_at,expires_at,user_agent_hash) VALUES(?,?,?,?,?)",
            (user_id,_token_hash(token),now_ts(),now_ts()+SESSION_SECONDS,ua),
        )
    return token


def delete_session(token: str | None) -> None:
    if not token:
        return
    with db() as con:
        con.execute("DELETE FROM sessions WHERE token_hash=?",(_token_hash(token),))


def session_user(request: Request):
    if os.getenv("MTA_NATIVE_SINGLE_USER", "").lower() in {"1","true","yes","on"}:
        ts = now_ts()
        return {
            "id": 0,
            "username": "local",
            "email": "",
            "display_name": "Local user",
            "role": "admin",
            "active": 1,
            "email_confirmed": 1,
            "totp_enabled": 0,
            "totp_pending_enc": None,
            "created_at": ts,
            "updated_at": ts,
            "approved_at": ts,
            "last_login_at": None,
        }
    if os.getenv("MTA_ALLOW_INSECURE_NO_AUTH", "").lower() in {"1","true","yes","on"}:
        ts = now_ts()
        return {
            "id":0,"username":"dev","email":"dev@localhost.invalid","display_name":"Development",
            "role":"admin","active":1,"email_confirmed":1,"totp_enabled":0,"totp_pending_enc":None,
            "created_at":ts,"updated_at":ts,"approved_at":ts,"last_login_at":None
        }
    init_auth_db()
    token = request.cookies.get(SESSION_COOKIE,"")
    if not token:
        return None
    with db() as con:
        row = con.execute(
            """SELECT u.* FROM sessions s JOIN users u ON u.id=s.user_id
               WHERE s.token_hash=? AND s.expires_at>?""",
            (_token_hash(token),now_ts()),
        ).fetchone()
        if not row or not row["active"] or not row["email_confirmed"]:
            return None
        # User-Agent binding is intentionally soft to avoid breaking reverse proxies
        # and mobile app upgrades; the token itself is high entropy, HttpOnly and SameSite.
        return row


def create_model_access_token(user_id: int, *, label: str = "client", scopes: tuple[str, ...] = ("models:read",), ttl_seconds: int | None = None) -> dict[str, Any]:
    """Issue a revocable bearer token limited to model download operations."""
    init_auth_db()
    allowed = {"models:read"}
    clean = sorted({scope for scope in scopes if scope in allowed})
    if not clean:
        raise ValueError("At least one valid model scope is required")
    ttl = MODEL_TOKEN_SECONDS if ttl_seconds is None else max(300, min(int(ttl_seconds), 90 * 24 * 3600))
    token = secrets.token_urlsafe(40)
    created = now_ts()
    expires = created + ttl
    with db() as con:
        con.execute(
            "INSERT INTO model_access_tokens(user_id,token_hash,scopes,label,created_at,expires_at) VALUES(?,?,?,?,?,?)",
            (user_id, _token_hash(token), " ".join(clean), label[:120], created, expires),
        )
    return {"token": token, "token_type": "Bearer", "scopes": clean, "expires_at": expires}


def model_access_token(request: Request, required_scope: str = "models:read"):
    """Return token metadata when Authorization carries a valid scoped model token."""
    header = request.headers.get("authorization", "")
    if not header.lower().startswith("bearer "):
        return None
    raw = header[7:].strip()
    if not raw:
        return None
    init_auth_db()
    with db() as con:
        row = con.execute(
            """SELECT t.*,u.username,u.role,u.active,u.email_confirmed
               FROM model_access_tokens t JOIN users u ON u.id=t.user_id
               WHERE t.token_hash=? AND t.expires_at>? AND t.revoked_at IS NULL""",
            (_token_hash(raw), now_ts()),
        ).fetchone()
        if not row or not row["active"] or not row["email_confirmed"]:
            return None
        scopes = set(str(row["scopes"] or "").split())
        if required_scope not in scopes:
            return None
        return row


def require_model_read(request: Request):
    """Allow an authenticated user session or a scoped models:read bearer token."""
    user = session_user(request)
    if user is not None:
        return user
    token = model_access_token(request, "models:read")
    if token is None:
        raise HTTPException(401, "Model download authentication required.")
    return token


def revoke_model_access_tokens(user_id: int) -> int:
    init_auth_db()
    with db() as con:
        cur = con.execute(
            "UPDATE model_access_tokens SET revoked_at=? WHERE user_id=? AND revoked_at IS NULL",
            (now_ts(), user_id),
        )
        return int(cur.rowcount or 0)


def require_user(request: Request):
    row = session_user(request)
    if not row:
        raise HTTPException(401,"Autenticazione richiesta.")
    return row


def require_admin(request: Request):
    row = require_user(request)
    if row["role"] != "admin":
        raise HTTPException(403,"Ruolo amministratore richiesto.")
    return row


def update_profile(user_id: int, *, display_name: str | None = None, email: str | None = None, base_url: str = "", language: str | None = None, limits_expanded: bool | None = None):
    if limits_expanded is not None and type(limits_expanded) is not bool:
        raise ValueError("Invalid limits panel preference")
    if language is not None and language not in ("auto","it","en"):
        raise ValueError("Invalid interface language")
    row = get_user(user_id)
    if not row:
        raise ValueError("Utente non trovato.")
    ts = now_ts()
    changed = False
    destination = ""
    if email is not None:
        destination = email.strip().lower()
        if not EMAIL_RE.fullmatch(destination):
            raise ValueError("Indirizzo email non valido.")
    from . import account_lifecycle as lifecycle
    with db() as setup:lifecycle.init(setup)
    with db() as con:
        if limits_expanded is not None:
            con.execute("UPDATE users SET limits_expanded=?,updated_at=? WHERE id=?",(int(limits_expanded),ts,user_id))
        if language is not None:
            con.execute("UPDATE users SET language=?,updated_at=? WHERE id=?", (language,ts,user_id))
        if display_name is not None:
            con.execute("UPDATE users SET display_name=?,updated_at=? WHERE id=?", (display_name.strip()[:120],ts,user_id))
        if destination and destination != row["email"].lower():
            duplicate = con.execute("SELECT id FROM users WHERE (email=? OR pending_email=?) AND id<>?",
                                    (destination, destination, user_id)).fetchone()
            if duplicate:
                raise ValueError("Email già utilizzata o in attesa di verifica.")
            lifecycle.reserve(con,user_id,row["username"],row["email"])
            lifecycle.reserve(con,user_id,row["username"],destination)
            con.execute("UPDATE users SET pending_email=?,updated_at=? WHERE id=?", (destination,ts,user_id))
            changed = True
    token = None
    if changed:
        # Existing account stays active and verified. The destination is committed
        # only after the new mailbox proves ownership of the confirmation token.
        token = _create_email_token(user_id, "verify-email-change")
        try:
            _send_verification_email(user_id, token, base_url, recipient=destination)
        except Exception:
            LOGGER.warning("Email change pending SMTP configuration for user_id=%s", user_id)
    return public_user(get_user(user_id)), token


def change_password(user_id: int, current: str, new_password: str) -> None:
    row = get_user(user_id)
    if not row or not _verify_password(current,row["password_hash"]):
        raise ValueError("Password attuale non valida.")
    with db() as con:
        con.execute("UPDATE users SET password_hash=?,updated_at=? WHERE id=?", (_password_hash(new_password),now_ts(),user_id))
        con.execute("DELETE FROM sessions WHERE user_id=?", (user_id,))


def _new_totp_secret() -> str:
    return base64.b32encode(secrets.token_bytes(20)).decode().rstrip("=")


def _totp(secret: str, counter: int | None = None) -> str:
    counter = int(time.time())//30 if counter is None else counter
    padded = secret + "="*((8-len(secret)%8)%8)
    key = base64.b32decode(padded,casefold=True)
    digest = hmac.new(key,struct.pack(">Q",counter),hashlib.sha1).digest()
    off = digest[-1]&0x0F
    value=(struct.unpack(">I",digest[off:off+4])[0]&0x7fffffff)%1_000_000
    return f"{value:06d}"


def _verify_totp(secret: str, code: str) -> bool:
    code = "".join(c for c in code if c.isdigit())
    if len(code)!=6:
        return False
    ctr=int(time.time())//30
    return any(hmac.compare_digest(_totp(secret,ctr+d),code) for d in (-1,0,1))


def verify_totp(secret: str, code: str) -> bool:
    return _verify_totp(secret, code)


def totp_uri(row) -> str:
    secret = _open(row["totp_pending_enc"] or row["totp_secret_enc"])
    issuer = "MTA Audio Editor"
    return f"otpauth://totp/{quote(issuer)}:{quote(row['email'])}?secret={secret}&issuer={quote(issuer)}&algorithm=SHA1&digits=6&period=30"


def begin_totp(user_id: int):
    secret = _new_totp_secret()
    with db() as con:
        con.execute("UPDATE users SET totp_pending_enc=?,updated_at=? WHERE id=?",(_seal(secret),now_ts(),user_id))
    row=get_user(user_id)
    return secret, totp_uri(row)


def totp_qr_svg(uri: str) -> str:
    qr=qrcode.make(uri,image_factory=qrcode.image.svg.SvgPathImage)
    buf=io.BytesIO()
    qr.save(buf)
    return buf.getvalue()


def enable_totp(user_id: int, code: str) -> None:
    row=get_user(user_id)
    if not row or not row["totp_pending_enc"]:
        raise ValueError("Avvia prima la configurazione TOTP.")
    secret=_open(row["totp_pending_enc"])
    if not _verify_totp(secret,code):
        raise ValueError("Codice TOTP non valido.")
    with db() as con:
        con.execute(
            "UPDATE users SET totp_secret_enc=?,totp_pending_enc='',totp_enabled=1,updated_at=? WHERE id=?",
            (_seal(secret),now_ts(),user_id),
        )


def disable_totp(user_id: int, password: str, code: str) -> None:
    from .account_lifecycle import info
    life=info(user_id)
    if life.get('second_factor_required') and life.get('mfa_method')=='totp':raise ValueError('Secondo fattore obbligatorio per questo account')
    row=get_user(user_id)
    if not row or not _verify_password(password,row["password_hash"]):
        raise ValueError("Password non valida.")
    if row["totp_enabled"] and not _verify_totp(_open(row["totp_secret_enc"]),code):
        raise ValueError("Codice TOTP non valido.")
    with db() as con:
        con.execute(
            "UPDATE users SET totp_secret_enc='',totp_pending_enc='',totp_enabled=0,updated_at=? WHERE id=?",
            (now_ts(),user_id),
        )


def get_smtp_config(include_password: bool = False) -> dict:
    with db() as con:
        row=con.execute("SELECT * FROM smtp_config WHERE id=1").fetchone()
    result = {
        "host":row["host"],"port":row["port"],"security":row["security"],
        "username":row["username"],"from_email":row["from_email"],"from_name":row["from_name"],
        "password_set":bool(row["password_enc"]),
        "password": _open(row["password_enc"]) if include_password else "",
    }
    return result


def _smtp_full(override: dict | None = None) -> dict:
    with db() as con:
        row=con.execute("SELECT * FROM smtp_config WHERE id=1").fetchone()
    cfg={
        "host":row["host"],"port":row["port"],"security":row["security"],"username":row["username"],
        "password":_open(row["password_enc"]),"from_email":row["from_email"],"from_name":row["from_name"],
    }
    if override:
        for key in ("host","port","security","username","from_email","from_name"):
            if key in override:
                cfg[key]=override[key]
        if override.get("password"):
            cfg["password"]=override["password"]
    cfg["port"]=int(cfg.get("port") or (465 if cfg.get("security")=="smtps" else 587))
    return cfg


def save_smtp_config(body: dict) -> dict:
    init_auth_db()
    security=str(body.get("security","starttls")).lower()
    if security not in {"starttls","smtps","none"}:
        raise ValueError("Sicurezza SMTP non valida.")
    current=_smtp_full()
    password=current["password"] if not body.get("password") else str(body["password"])
    cfg={
        "host":str(body.get("host","")).strip(),
        "port":int(body.get("port") or (465 if security=="smtps" else 587)),
        "security":security,
        "username":str(body.get("username","")).strip(),
        "password":password,
        "from_email":str(body.get("from_email","")).strip().lower(),
        "from_name":str(body.get("from_name","MTA Audio Editor")).strip() or "MTA Audio Editor",
    }
    if cfg["host"] and not EMAIL_RE.fullmatch(cfg["from_email"]):
        raise ValueError("Email mittente obbligatoria quando SMTP è configurato.")
    with db() as con:
        con.execute(
            """UPDATE smtp_config SET host=?,port=?,security=?,username=?,password_enc=?,from_email=?,from_name=? WHERE id=1""",
            (cfg["host"],cfg["port"],cfg["security"],cfg["username"],_seal(cfg["password"]),cfg["from_email"],cfg["from_name"]),
        )
    return get_smtp_config()


def _smtp_client(cfg: dict):
    if cfg["security"]=="smtps":
        return smtplib.SMTP_SSL(cfg["host"],cfg["port"],timeout=15,context=ssl.create_default_context())
    client=smtplib.SMTP(cfg["host"],cfg["port"],timeout=15)
    if cfg["security"]=="starttls":
        client.starttls(context=ssl.create_default_context())
    return client


def test_smtp_config(body: dict) -> None:
    cfg=_smtp_full(body)
    if not cfg["host"]:
        raise ValueError("Server SMTP non configurato.")
    client=_smtp_client(cfg)
    try:
        if cfg["username"]:
            client.login(cfg["username"],cfg["password"])
        client.noop()
    finally:
        try:
            client.quit()
        except Exception:
            LOGGER.debug("SMTP quit failed after connection test", exc_info=True)


def send_mail(recipients: list[str], subject: str, plain: str, html_body: str | None = None, *, inline_image: bytes | None = None, message_id: str | None = None, configuration: dict | None = None) -> None:
    from .i18n import recipient_language, translate, translate_html
    for recipient in dict.fromkeys(x for x in recipients if x):
        language=recipient_language(recipient)
        _send_mail_one([recipient],translate(subject,language),translate(plain,language),translate_html(html_body,language) if html_body else None,inline_image=inline_image,message_id=message_id,configuration=configuration)


def _send_mail_one(recipients: list[str], subject: str, plain: str, html_body: str | None = None, *, inline_image: bytes | None = None, message_id: str | None = None, configuration: dict | None = None) -> None:
    cfg=_smtp_full() if configuration is None else _smtp_full(configuration)
    if not cfg["host"] or not cfg["from_email"]:
        raise RuntimeError("SMTP non configurato.")
    recipients=[x for x in recipients if x]
    if not recipients:
        return
    msg=EmailMessage()
    if message_id:
        msg["Message-ID"]=message_id
    msg["Subject"]=subject
    msg["From"]=f"{cfg['from_name']} <{cfg['from_email']}>"
    msg["To"]=", ".join(recipients)
    msg.set_content(plain)
    if html_body:
        msg.add_alternative(html_body,subtype="html")
        if inline_image:
            msg.get_payload()[-1].add_related(inline_image,maintype="image",subtype="png",cid="<mta-logo>",filename="mta-logo.png",disposition="inline")
    client=_smtp_client(cfg)
    try:
        if cfg["username"]:
            client.login(cfg["username"],cfg["password"])
        if client.send_message(msg):raise RuntimeError("Destinatario rifiutato dal server SMTP")
    finally:
        try:
            client.quit()
        except Exception:
            LOGGER.debug("SMTP quit failed after sending email", exc_info=True)


def _notify_admins_activated(user) -> None:
    with db() as con:
        admins=con.execute(
            "SELECT email FROM users WHERE role='admin' AND active=1 AND email_confirmed=1 AND email<>''"
        ).fetchall()
    recipients=[x["email"] for x in admins]
    if not recipients:
        return
    from .admin_navigation import action, settings_target
    text=f"L'utente {user['username']} ({user['email']}) è stato attivato."
    plain,link=action(text,settings_target('users',user['id']),'Apri gestione utente')
    send_mail(recipients,"Utente attivato · MTA Audio Editor",plain,'<p>'+html.escape(text)+'</p>'+link)



def update_user_admin(target_id: int, actor_id: int, *, active: bool | None = None, role: str | None = None, workspace_quota_bytes: int | None = None) -> dict[str, Any]:
    row = get_user(target_id)
    if not row:
        raise ValueError("Utente non trovato.")
    if role is not None and role not in {"admin", "user"}:
        raise ValueError("Ruolo non valido.")
    if workspace_quota_bytes is not None and int(workspace_quota_bytes) < 0:
        raise ValueError("La quota workspace non può essere negativa.")
    if active is True:
        from .account_lifecycle import approval_guard
        approval_guard(target_id)
    if active is True and not row["email_confirmed"]:
        raise ValueError("L'utente deve prima confermare il proprio indirizzo email.")
    if target_id == actor_id and active is False:
        raise ValueError("Non puoi disattivare il tuo account amministratore.")
    if target_id == actor_id and role == "user":
        raise ValueError("Non puoi rimuovere il ruolo admin dal tuo stesso account.")
    ts = now_ts()
    became_active = active is True and not bool(row["active"])
    with db() as con:
        con.execute('BEGIN IMMEDIATE')
        current = con.execute('SELECT role FROM users WHERE id=?', (target_id,)).fetchone()
        if current and current['role'] == 'admin' and (active is False or role == 'user'):
            raise ValueError('Gli amministratori non possono essere disabilitati o privati del ruolo admin.')
        if current and (role == 'admin' or active is True) and con.execute("SELECT 1 FROM sqlite_master WHERE name='account_lifecycle'").fetchone():
            state = con.execute('SELECT state FROM account_lifecycle WHERE user_id=?', (target_id,)).fetchone()
            if state and state[0] in ('erasing', 'deleting', 'deleted', 'expired'):
                raise ValueError('Riattivare prima l’account')
        if role is not None:
            con.execute("UPDATE users SET role=?, updated_at=? WHERE id=?", (role, ts, target_id))
        if workspace_quota_bytes is not None:
            con.execute("UPDATE users SET workspace_quota_bytes=?, workspace_quota_explicit=1, updated_at=? WHERE id=?", (int(workspace_quota_bytes), ts, target_id))
        if active is not None:
            con.execute(
                "UPDATE users SET active=?, approved_at=?, approved_by=?, updated_at=? WHERE id=?",
                (1 if active else 0, ts if active else None, actor_id if active else None, ts, target_id),
            )
    updated = get_user(target_id)
    if became_active:
        from .account_lifecycle import approved
        approved(target_id)
        try:
            _notify_admins_activated(updated)
        except Exception:
            LOGGER.exception("Unable to notify administrators about activation of user_id=%s", target_id)
    return public_user(updated)


def delete_user_admin(user_id: int, actor_id: int) -> None:
    from .account_lifecycle import retire
    retire(user_id,actor_id)


def request_password_reset(identifier: str, base_url: str = "") -> None:
    row = _find_user(identifier)
    if not row or not row["email_confirmed"]:
        return
    token = _create_email_token(row["id"], "password-reset")
    link_path = f"/reset-password?token={quote(token)}"
    base = _base_url() or base_url.rstrip("/")
    link = (base + link_path) if base else link_path
    try:
        send_mail(
            [row["email"]],
            "Reimposta password · MTA Audio Editor",
            f"Reimposta la password aprendo questo link:\n{link}\n\nIl link scade tra 24 ore.",
            f"<p><a href='{html.escape(link)}'>Reimposta la password</a></p><p>Il link scade tra 24 ore.</p>",
        )
    except Exception:
        LOGGER.exception("Unable to send password reset email for user_id=%s", row["id"])


def reset_password(token: str, new_password: str) -> bool:
    row = _consume_email_token(token, "password-reset")
    if not row:
        return False
    with db() as con:
        con.execute(
            "UPDATE users SET password_hash=?,updated_at=? WHERE id=?",
            (_password_hash(new_password),now_ts(),row["user_id"]),
        )
        con.execute("DELETE FROM sessions WHERE user_id=?",(row["user_id"],))
    return True
