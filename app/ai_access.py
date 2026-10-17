"""Per-user, revocable AI gateway credentials and non-billable usage records.

This is a gateway ledger. Wall duration is measured per HTTP request; CPU/GPU
resource attribution requires worker-side instrumentation and is intentionally NULL.
"""
from __future__ import annotations
import hashlib
import secrets
import time
from .auth import db


def _init(con):
    con.executescript('''
    CREATE TABLE IF NOT EXISTS ai_access_tokens (
      id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL, label TEXT NOT NULL,
      token_hash TEXT NOT NULL UNIQUE, created_at INTEGER NOT NULL,
      revoked_at INTEGER, last_used_at INTEGER, client_id TEXT,
      FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE);
    CREATE TABLE IF NOT EXISTS ai_usage_events (
      id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL, token_id INTEGER,
      endpoint TEXT NOT NULL, status_code INTEGER NOT NULL,
      started_at INTEGER NOT NULL, wall_ms INTEGER NOT NULL,
      request_bytes INTEGER NOT NULL DEFAULT 0, response_bytes INTEGER NOT NULL DEFAULT 0,
      cpu_seconds REAL, gpu_seconds REAL, gpu_energy_joules REAL,
      FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE);
    CREATE INDEX IF NOT EXISTS idx_ai_usage_user_date ON ai_usage_events(user_id, started_at);
    ''')

    if 'client_id' not in {r[1] for r in con.execute('PRAGMA table_info(ai_access_tokens)')}:
        try:con.execute('ALTER TABLE ai_access_tokens ADD COLUMN client_id TEXT')
        except __import__('sqlite3').OperationalError as exc:
            if 'duplicate column' not in str(exc).lower():raise


def issue(user_id: int, label: str) -> dict:
    if not 1 <= len(label.strip()) <= 80:
        raise ValueError('Token label must contain 1-80 characters')
    raw = 'mta_ai_' + secrets.token_urlsafe(32)
    with db() as con:
        _init(con)
        if not con.execute('SELECT 1 FROM users WHERE id=? AND active=1', (user_id,)).fetchone():
            raise ValueError('User not active or missing')
        cur = con.execute('INSERT INTO ai_access_tokens(user_id,label,token_hash,created_at) VALUES(?,?,?,?)',
                          (user_id, label.strip(), hashlib.sha256(raw.encode()).hexdigest(), int(time.time())))
        return {'id':cur.lastrowid, 'token':raw, 'user_id':user_id, 'label':label.strip()}


def list_tokens(user_id: int | None = None) -> list[dict]:
    with db() as con:
        _init(con)
        if user_id is None:
            rows = con.execute('SELECT id,user_id,label,created_at,revoked_at,last_used_at,client_id FROM ai_access_tokens ORDER BY id DESC').fetchall()
        else:
            rows = con.execute('SELECT id,user_id,label,created_at,revoked_at,last_used_at,client_id FROM ai_access_tokens WHERE user_id=? ORDER BY id DESC', (user_id,)).fetchall()
        return [dict(row) for row in rows]


def revoke(token_id: int) -> bool:
    with db() as con:
        _init(con)
        cur = con.execute('UPDATE ai_access_tokens SET revoked_at=? WHERE id=? AND revoked_at IS NULL',
                          (int(time.time()), token_id))
        return cur.rowcount > 0


def authenticate(token: str) -> dict | None:
    if not token.startswith('mta_ai_') or len(token) > 180:
        return None
    digest = hashlib.sha256(token.encode()).hexdigest()
    with db() as con:
        _init(con)
        row = con.execute('''SELECT t.id,t.user_id,t.label,t.client_id FROM ai_access_tokens t
          JOIN users u ON u.id=t.user_id WHERE t.token_hash=? AND t.revoked_at IS NULL
          AND u.active=1''', (digest,)).fetchone()
        if row:
            con.execute('UPDATE ai_access_tokens SET last_used_at=? WHERE id=?', (int(time.time()), row['id']))
        return dict(row) if row else None


def usage(token_id: int, user_id: int, endpoint: str, started: float, status: int,
          req_bytes: int = 0, resp_bytes: int = 0) -> None:
    with db() as con:
        _init(con)
        con.execute('''INSERT INTO ai_usage_events
          (user_id,token_id,endpoint,status_code,started_at,wall_ms,request_bytes,response_bytes)
          VALUES(?,?,?,?,?,?,?,?)''',
          (user_id,token_id,endpoint,status,int(started),max(0,round((time.time()-started)*1000)),req_bytes,resp_bytes))


def summary(user_id: int | None = None) -> list[dict]:
    with db() as con:
        _init(con)
        sql = ('SELECT user_id,COUNT(*) requests,SUM(wall_ms) wall_ms, '
               'SUM(request_bytes) request_bytes,SUM(response_bytes) response_bytes '
               'FROM ai_usage_events')
        if user_id is None:
            rows = con.execute(sql + ' GROUP BY user_id ORDER BY user_id').fetchall()
        else:
            rows = con.execute(sql + ' WHERE user_id=? GROUP BY user_id ORDER BY user_id', (user_id,)).fetchall()
        return [dict(row) for row in rows]


def rotate(token_id):
    with db() as con:
        _init(con);con.execute('BEGIN IMMEDIATE')
        row=con.execute('SELECT * FROM ai_access_tokens WHERE id=? AND revoked_at IS NULL',(token_id,)).fetchone()
        if not row:raise ValueError('Active token not found')
        if not con.execute('SELECT 1 FROM users WHERE id=? AND active=1',(row['user_id'],)).fetchone():raise ValueError('User inactive')
        raw='mta_ai_'+secrets.token_urlsafe(32)
        con.execute('UPDATE ai_access_tokens SET revoked_at=? WHERE id=?',(int(time.time()),token_id))
        cur=con.execute('INSERT INTO ai_access_tokens(user_id,label,token_hash,created_at,client_id) VALUES(?,?,?,?,?)',
          (row['user_id'],row['label'],hashlib.sha256(raw.encode()).hexdigest(),int(time.time()),row['client_id']))
    return {'id':cur.lastrowid,'token':raw,'user_id':row['user_id'],'label':row['label']}
