
from __future__ import annotations

import base64
import hashlib
import hmac
import html
import io
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
from urllib.parse import quote

import qrcode
import qrcode.image.svg
from fastapi import HTTPException, Request

SESSION_COOKIE = "mta_session"
SESSION_SECONDS = 12 * 3600
TOKEN_SECONDS = 24 * 3600
PBKDF2_ITERS = 310_000
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
DATA_ROOT: Path | None = None


def data_root() -> Path:
    if DATA_ROOT is not None:
        return Path(DATA_ROOT).resolve()
    return Path(os.getenv("MTA_DATA_DIR", "/data/projects")).resolve()


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
    con.execute("PRAGMA foreign_keys=ON")
    try:
        yield con
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
          totp_secret_enc TEXT NOT NULL DEFAULT '',
          totp_pending_enc TEXT NOT NULL DEFAULT '',
          totp_enabled INTEGER NOT NULL DEFAULT 0,
          created_at INTEGER NOT NULL,
          updated_at INTEGER NOT NULL,
          approved_at INTEGER,
          approved_by INTEGER,
          last_login_at INTEGER,
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
        CREATE TABLE IF NOT EXISTS sessions(
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          user_id INTEGER NOT NULL,
          token_hash TEXT NOT NULL UNIQUE,
          created_at INTEGER NOT NULL,
          expires_at INTEGER NOT NULL,
          user_agent_hash TEXT NOT NULL DEFAULT '',
          FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
        );
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
            "totp_secret_enc TEXT NOT NULL DEFAULT ''",
            "totp_pending_enc TEXT NOT NULL DEFAULT ''",
            "updated_at INTEGER NOT NULL DEFAULT 0",
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
            """INSERT INTO users(username,email,display_name,password_hash,role,active,email_confirmed,created_at,updated_at,approved_at)
               VALUES(?,?,?,?, 'admin',1,1,?,?,?)""",
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


def public_user(row) -> dict:
    return {
        "id": row["id"],
        "username": row["username"],
        "email": row["email"],
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


def _send_verification_email(user_id: int, token: str, base_url: str = "") -> None:
    row = get_user(user_id)
    if not row:
        return
    link = _verification_link(token, base_url)
    send_mail(
        [row["email"]],
        "Conferma la tua email · MTA Audio Editor",
        f"Conferma la tua email aprendo questo link:\n{link}\n\nIl link scade tra 24 ore.",
        f"<p>Conferma la tua email per <b>MTA Audio Editor</b>.</p><p><a href='{html.escape(link)}'>Conferma email</a></p><p>Il link scade tra 24 ore.</p>",
    )


def register_user(username: str, email: str, display_name: str, password: str, base_url: str = ""):
    username = username.strip()
    email = email.strip().lower()
    display_name = display_name.strip()[:120]
    if not (3 <= len(username) <= 64) or not re.fullmatch(r"[A-Za-z0-9._-]+", username):
        raise ValueError("Username non valido: usa 3-64 caratteri, lettere, numeri, '.', '_' o '-'.")
    if not EMAIL_RE.fullmatch(email):
        raise ValueError("Indirizzo email obbligatorio e non valido.")
    ts = now_ts()
    try:
        with db() as con:
            cur = con.execute(
                """INSERT INTO users(username,email,display_name,password_hash,role,active,email_confirmed,created_at,updated_at)
                   VALUES(?,?,?,?, 'user',0,0,?,?)""",
                (username,email,display_name,_password_hash(password),ts,ts),
            )
            user_id = cur.lastrowid
    except sqlite3.IntegrityError as exc:
        raise ValueError("Username o email già registrati.") from exc
    token = _create_email_token(user_id)
    # Registration remains successful even if SMTP is not configured; the admin can
    # configure SMTP and the user can request a resend afterwards.
    try:
        _send_verification_email(user_id, token, base_url)
    except Exception:
        pass
    return public_user(get_user(user_id)), token


def confirm_email(token: str) -> bool:
    row = _consume_email_token(token)
    if not row:
        return False
    with db() as con:
        con.execute("UPDATE users SET email_confirmed=1,updated_at=? WHERE id=?", (now_ts(),row["user_id"]))
    return True


def resend_verification(identifier: str, base_url: str = "") -> None:
    row = _find_user(identifier)
    if not row or row["email_confirmed"]:
        return
    token = _create_email_token(row["id"])
    try:
        _send_verification_email(row["id"],token,base_url)
    except Exception:
        pass


def authenticate(identifier: str, password: str, code: str = ""):
    init_auth_db()
    row = _find_user(identifier)
    if not row or not _verify_password(password,row["password_hash"]):
        return None, "Credenziali non valide."
    if not row["email_confirmed"]:
        return None, "Conferma prima il tuo indirizzo email."
    if not row["active"]:
        return None, "Account in attesa dell'approvazione di un amministratore."
    if row["totp_enabled"]:
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
    if os.getenv("MTA_ALLOW_INSECURE_NO_AUTH", "").lower() in {"1","true","yes","on"}:
        return {"id":0,"username":"dev","email":"dev@localhost.invalid","display_name":"Development","role":"admin","active":1,"email_confirmed":1,"totp_enabled":0,"created_at":now_ts(),"updated_at":now_ts(),"approved_at":now_ts(),"last_login_at":None}
    init_auth_db()
    token = request.cookies.get(SESSION_COOKIE,"")
    if not token:
        return None
    ua = hashlib.sha256(request.headers.get("user-agent","").encode()).hexdigest()
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


def update_profile(user_id: int, *, display_name: str | None = None, email: str | None = None, base_url: str = ""):
    row = get_user(user_id)
    if not row:
        raise ValueError("Utente non trovato.")
    ts = now_ts()
    email_changed = False
    with db() as con:
        if display_name is not None:
            con.execute("UPDATE users SET display_name=?,updated_at=? WHERE id=?", (display_name.strip()[:120],ts,user_id))
        if email is not None:
            email = email.strip().lower()
            if not EMAIL_RE.fullmatch(email):
                raise ValueError("Indirizzo email non valido.")
            if email != row["email"].lower():
                try:
                    con.execute(
                        "UPDATE users SET email=?,email_confirmed=0,active=0,updated_at=? WHERE id=?",
                        (email,ts,user_id),
                    )
                except sqlite3.IntegrityError as exc:
                    raise ValueError("Email già utilizzata.") from exc
                email_changed = True
    token = None
    if email_changed:
        token = _create_email_token(user_id)
        try:
            _send_verification_email(user_id,token,base_url)
        except Exception:
            pass
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
        try: client.quit()
        except Exception: pass


def send_mail(recipients: list[str], subject: str, plain: str, html_body: str | None = None) -> None:
    cfg=_smtp_full()
    if not cfg["host"] or not cfg["from_email"]:
        raise RuntimeError("SMTP non configurato.")
    recipients=[x for x in recipients if x]
    if not recipients:
        return
    msg=EmailMessage()
    msg["Subject"]=subject
    msg["From"]=f"{cfg['from_name']} <{cfg['from_email']}>"
    msg["To"]=", ".join(recipients)
    msg.set_content(plain)
    if html_body:
        msg.add_alternative(html_body,subtype="html")
    client=_smtp_client(cfg)
    try:
        if cfg["username"]:
            client.login(cfg["username"],cfg["password"])
        client.send_message(msg)
    finally:
        try: client.quit()
        except Exception: pass


def _notify_admins_activated(user) -> None:
    with db() as con:
        admins=con.execute(
            "SELECT email FROM users WHERE role='admin' AND active=1 AND email_confirmed=1 AND email<>''"
        ).fetchall()
    recipients=[x["email"] for x in admins]
    if not recipients:
        return
    send_mail(
        recipients,
        "Utente attivato · MTA Audio Editor",
        f"L'utente {user['username']} ({user['email']}) è stato attivato.",
        f"<p>L'utente <b>{html.escape(user['username'])}</b> ({html.escape(user['email'])}) è stato attivato.</p>",
    )


def update_user_admin(target_id: int, actor_id: int, *, active: bool | None = None, role: str | None = None) -> dict[str, Any]:
    row = get_user(target_id)
    if not row:
        raise ValueError("Utente non trovato.")
    if role is not None and role not in {"admin", "user"}:
        raise ValueError("Ruolo non valido.")
    if active is True and not row["email_confirmed"]:
        raise ValueError("L'utente deve prima confermare il proprio indirizzo email.")
    if target_id == actor_id and active is False:
        raise ValueError("Non puoi disattivare il tuo account amministratore.")
    if target_id == actor_id and role == "user":
        raise ValueError("Non puoi rimuovere il ruolo admin dal tuo stesso account.")
    if (active is False or role == "user") and row["role"] == "admin" and row["active"]:
        with db() as con:
            active_admins = con.execute(
                "SELECT COUNT(*) FROM users WHERE role='admin' AND active=1 AND email_confirmed=1"
            ).fetchone()[0]
        if active_admins <= 1:
            raise ValueError("Deve rimanere almeno un amministratore attivo.")
    ts = now_ts()
    became_active = active is True and not bool(row["active"])
    with db() as con:
        if role is not None:
            con.execute("UPDATE users SET role=?, updated_at=? WHERE id=?", (role, ts, target_id))
        if active is not None:
            con.execute(
                "UPDATE users SET active=?, approved_at=?, approved_by=?, updated_at=? WHERE id=?",
                (1 if active else 0, ts if active else None, actor_id if active else None, ts, target_id),
            )
    updated = get_user(target_id)
    if became_active:
        try:
            send_mail(
                [updated["email"]],
                "MTA Audio Editor - account attivato",
                f"Ciao {updated['display_name'] or updated['username']},\n\nil tuo account è stato approvato ed è ora attivo.\n",
            )
        except Exception:
            pass
        try:
            _notify_admins_activated(updated)
        except Exception:
            pass
    return public_user(updated)


def delete_user_admin(user_id: int, actor_id: int) -> None:
    if user_id==actor_id:
        raise ValueError("Non puoi eliminare il tuo stesso account.")
    row=get_user(user_id)
    if not row:
        raise ValueError("Utente non trovato.")
    if row["role"]=="admin":
        with db() as con:
            admins=con.execute("SELECT COUNT(*) FROM users WHERE role='admin' AND active=1").fetchone()[0]
        if admins<=1:
            raise ValueError("Non puoi eliminare l'ultimo amministratore attivo.")
    with db() as con:
        con.execute("DELETE FROM users WHERE id=?",(user_id,))


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
        pass


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
