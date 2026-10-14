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
    if state == 'completed' and (not isinstance(job_id, str) or not 1 <= len(job_id) <= 128):
        raise ValueError('Completed request requires a valid worker job id')
    if state == 'failed' and job_id is not None:
        raise ValueError('Failed request must not bind a completed job')
    with db() as c:
        c.execute('BEGIN IMMEDIATE')
        result = c.execute('UPDATE ai_request_dedup SET state=?,job_id=? '
                  "WHERE user_id=? AND request_key=? AND state='admitted'",
                  (state, job_id, user_id, key))
        if result.rowcount != 1:
            previous = c.execute('SELECT state,job_id FROM ai_request_dedup '
                                 'WHERE user_id=? AND request_key=?', (user_id, key)).fetchone()
            if previous is None or previous['state'] != state or previous['job_id'] != job_id:
                raise ValueError('Conflicting or missing durable request finalization')



def cancel_admitted(user_id: int, key: str) -> dict | None:
    """Durably tombstone a request; a late worker cannot complete it.

    This is a cooperative protocol request, not a claim that an already
    executing model has been physically stopped. Never delete the claim.
    """
    if not isinstance(key, str) or not _KEY.fullmatch(key):
        raise ValueError('Invalid AI idempotency key')
    with db() as c:
        c.execute('BEGIN IMMEDIATE')
        exists = c.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='ai_request_dedup'").fetchone()
        if not exists:
            return None
        row = c.execute('SELECT state,job_id,created_at FROM ai_request_dedup '
                        'WHERE user_id=? AND request_key=?', (user_id, key)).fetchone()
        if row is None:
            return None
        if row['state'] == 'admitted':
            c.execute("UPDATE ai_request_dedup SET state='cancelled' "
                      "WHERE user_id=? AND request_key=? AND state='admitted'", (user_id, key))
            return {'state': 'cancelled', 'job_id': None, 'created_at': row['created_at']}
        return {'state': row['state'], 'job_id': row['job_id'], 'created_at': row['created_at']}


def is_cancelled(user_id: int, key: str) -> bool:
    current = request_status(user_id, key)
    return current is not None and current['state'] == 'cancelled'

def request_status(user_id: int, key: str) -> dict | None:
    """Return only the authenticated owner's non-secret request status.

    This does not claim that result artifacts are retained. Clients may check
    ambiguous timeouts without submitting a new job or reusing credentials.
    """
    if not isinstance(key, str) or not _KEY.fullmatch(key):
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


def reconcile_published(user_id: int, key: str) -> dict | None:
    """Repair crash after durable cache publication but before SQL finalization.

    This only transitions an admitted request to completed after the owner's
    immutable cached result has been fully verified. It never starts a worker.
    """
    current = request_status(user_id, key)
    if current is None or current['state'] != 'admitted':
        return current
    from .ai_result_cache import recover_completed_job_id
    worker_id = recover_completed_job_id(user_id, key)
    if worker_id is None:
        return current
    # Cancellation or failure may win the race after the initial status read.
    # The terminal state is authoritative; never overwrite it or raise a 500
    # from an otherwise read-only status/recovery operation.
    try:
        finalize(user_id, key, job_id=worker_id)
    except ValueError:
        latest = request_status(user_id, key)
        if latest is None or latest['state'] == 'admitted':
            raise
        return latest
    return request_status(user_id, key)


def list_requests(user_id: int, *, limit: int = 50, offset: int = 0,
                  state: str | None = None) -> dict:
    """List a user's durable remote request claims, even after client restart.

    The caller must be authenticated before passing its user id. Results are
    bounded, stable, and never include request fingerprints or other owners.
    """
    if type(user_id) is not int or user_id <= 0:
        raise ValueError('Invalid AI request owner')
    if type(limit) is not int or not 1 <= limit <= 100:
        raise ValueError('Limit must be between 1 and 100')
    if type(offset) is not int or not 0 <= offset <= 1000000:
        raise ValueError('Invalid request offset')
    allowed = {'admitted', 'completed', 'failed', 'cancelled'}
    if state is not None and state not in allowed:
        raise ValueError('Invalid AI request state filter')
    with db() as c:
        exists = c.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='ai_request_dedup'").fetchone()
        if not exists:
            return {'items': [], 'total': 0, 'limit': limit, 'offset': offset}
        where = 'WHERE user_id=?'
        params = [user_id]
        if state is not None:
            where += ' AND state=?'
            params.append(state)
        total = c.execute('SELECT COUNT(*) FROM ai_request_dedup ' + where, params).fetchone()[0]
        rows = c.execute('SELECT request_key,state,job_id,created_at FROM ai_request_dedup '
                         + where + ' ORDER BY created_at DESC,request_key DESC LIMIT ? OFFSET ?',
                         (*params, limit, offset)).fetchall()
    items = []
    for row in rows:
        if (row['state'] not in allowed or
                (row['state'] == 'completed') != (row['job_id'] is not None) or
                type(row['created_at']) is not int or row['created_at'] <= 0 or
                not isinstance(row['request_key'], str) or not _KEY.fullmatch(row['request_key'])):
            raise ValueError('Corrupt durable AI request history')
        items.append({'request_key': row['request_key'], 'state': row['state'],
                      'job_id': row['job_id'], 'created_at': row['created_at']})
    return {'items': items, 'total': total, 'limit': limit, 'offset': offset}
