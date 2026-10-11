"""Durable per-user request admission for remote AI inference.

A repeated idempotency key never starts a second inference. Ambiguous calls
are intentionally not auto-retried; the operator can investigate outstanding
claims instead of risking duplicate billing.
"""
from __future__ import annotations

import hashlib
import re
import time
from .auth import db

_KEY = re.compile(r'^[A-Za-z0-9][A-Za-z0-9._:-]{15,127}$')


class DuplicateAIRequest(ValueError):
    def __init__(self, state: str, job_id: str | None = None):
        super().__init__('AI request already admitted; inference will not run again')
        self.state = state
        self.job_id = job_id


def fingerprint(kind: str, options: bytes, content: bytes) -> str:
    digest = hashlib.sha256()
    for part in (kind.encode('utf-8'), options, content):
        digest.update(len(part).to_bytes(8, 'big'))
        digest.update(part)
    return digest.hexdigest()


def admit(user_id: int, key: str, digest: str) -> None:
    if not _KEY.fullmatch(key):
        raise ValueError('Invalid AI idempotency key (16-128 URL-safe characters)')
    if not re.fullmatch(r'[0-9a-f]{64}', digest):
        raise ValueError('Invalid request fingerprint')
    with db() as c:
        c.execute('''CREATE TABLE IF NOT EXISTS ai_request_dedup (
            user_id INTEGER NOT NULL, request_key TEXT NOT NULL,
            fingerprint TEXT NOT NULL, state TEXT NOT NULL,
            job_id TEXT, created_at INTEGER NOT NULL,
            PRIMARY KEY(user_id, request_key))''')
        c.execute('BEGIN IMMEDIATE')
        previous = c.execute('SELECT fingerprint,state,job_id FROM ai_request_dedup '
                             'WHERE user_id=? AND request_key=?', (user_id, key)).fetchone()
        if previous:
            if previous['fingerprint'] != digest:
                raise ValueError('Idempotency key reused with different request content')
            raise DuplicateAIRequest(previous['state'], previous['job_id'])
        c.execute('INSERT INTO ai_request_dedup(user_id,request_key,fingerprint,state,created_at) '
                  'VALUES(?,?,?,?,?)', (user_id, key, digest, 'admitted', int(time.time())))


def finalize(user_id: int, key: str, *, job_id: str | None = None, state: str = 'completed') -> None:
    if state not in ('completed', 'failed'):
        raise ValueError('Invalid deduplication state')
    with db() as c:
        c.execute('BEGIN IMMEDIATE')
        c.execute('UPDATE ai_request_dedup SET state=?,job_id=? '
                  "WHERE user_id=? AND request_key=? AND state='admitted'",
                  (state, job_id, user_id, key))


def request_status(user_id: int, key: str) -> dict | None:
    """Return only the authenticated owner's non-secret request status.

    This does not claim that result artifacts are retained. Clients may check
    ambiguous timeouts without submitting a new job or reusing credentials.
    """
    if not _KEY.fullmatch(key):
        raise ValueError('Invalid AI idempotency key (16-128 URL-safe characters)')
    with db() as c:
        # The dedup table is created on first admission, not at startup.
        exists = c.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='ai_request_dedup'").fetchone()
        if not exists:
            return None
        row = c.execute('SELECT state,job_id,created_at FROM ai_request_dedup '
                        'WHERE user_id=? AND request_key=?', (user_id, key)).fetchone()
        if row is None:
            return None
        return {'state': row['state'], 'job_id': row['job_id'], 'created_at': row['created_at']}
