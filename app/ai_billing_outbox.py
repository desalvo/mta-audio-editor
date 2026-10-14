"""Durable, opt-in delivery of AI billing settlements.

An inference job must first be explicitly associated with an existing billing
job. No billable job, user or measurements are invented by this module.
Delivery uses the billing ledger's compare-and-set/idempotent finalizer and
retains the intent until acknowledgement is durably recorded. This is a saga,
not a distributed ACID transaction.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import sqlite3
import time

from . import ai_arranger_runtime as queue
from . import ai_billing

try:
    import fcntl
except ImportError:  # pragma: no cover
    fcntl = None


def _db():
    queue._ROOT.mkdir(parents=True, exist_ok=True, mode=0o700)
    path = queue._ROOT / 'billing-outbox.sqlite3'
    con = sqlite3.connect(path, isolation_level=None, timeout=30)
    con.row_factory = sqlite3.Row
    con.execute('PRAGMA journal_mode=WAL')
    con.execute('PRAGMA busy_timeout=30000')
    con.execute('''CREATE TABLE IF NOT EXISTS deliveries (
        job_id TEXT PRIMARY KEY, billing_job_id TEXT NOT NULL UNIQUE,
        intent_json TEXT NOT NULL, state TEXT NOT NULL CHECK(state IN ('pending','delivered')),
        created_at REAL NOT NULL, delivered_at REAL, last_error TEXT
    )''')
    for suffix in ('', '-wal', '-shm'):
        sidecar = Path(str(path) + suffix)
        if sidecar.exists() and not sidecar.is_symlink():
            os.chmod(sidecar, 0o600)
    return con


def register(job_id, billing_job_id, status, usage=None, *, source='unmetered', finished_at=None):
    """Persist a validated immutable settlement intent, without charging yet."""
    queue._validate_job_id(job_id)
    queue._validate_job_id(billing_job_id)
    if status not in ('done', 'failed', 'cancelled'):
        raise ValueError('Invalid settlement status')
    normalized = ai_billing._validate_usage(usage or {})
    if source not in ('unmetered', 'worker', 'cgroup', 'gpu-agent', 'remote-worker'):
        raise ValueError('Invalid metering source')
    if normalized and source == 'unmetered':
        raise ValueError('Measured resources need a trusted source')
    if {'gpu_seconds', 'gpu_energy_joules'} & normalized.keys() and source != 'gpu-agent':
        raise ValueError('GPU usage needs trusted GPU agent')
    if source == 'gpu-agent' and not {'gpu_seconds', 'gpu_energy_joules'} & normalized.keys():
        raise ValueError('GPU agent must supply measurements')
    if finished_at is not None and (type(finished_at) is not int or finished_at < 0):
        raise ValueError('Invalid finish timestamp')
    intent = json.dumps({'status': status, 'usage': normalized, 'source': source,
                         'finished_at': finished_at}, sort_keys=True, allow_nan=False)
    with _db() as con:
        con.execute('BEGIN IMMEDIATE')
        old = con.execute('SELECT job_id,billing_job_id,intent_json FROM deliveries WHERE job_id=? OR billing_job_id=?',
                          (job_id, billing_job_id)).fetchone()
        if old:
            if (old['job_id'], old['billing_job_id'], old['intent_json']) != (job_id, billing_job_id, intent):
                con.execute('ROLLBACK')
                raise ValueError('Conflicting settlement replay')
            con.execute('COMMIT')
            return False
        con.execute('INSERT INTO deliveries(job_id,billing_job_id,intent_json,state,created_at) VALUES(?,?,?,\'pending\',?)',
                    (job_id, billing_job_id, intent, time.time()))
        con.execute('COMMIT')
        return True



def register_verified(job_id, billing_job_id, user_id, status, usage=None, *,
                      source='unmetered', finished_at=None):
    """Bind an existing ledger job to a durable inference after ownership checks.

    This is an explicit opt-in boundary: neither a billing identity nor GPU
    consumption is synthesized from an audio inference. The immutable outbox
    intent is then safe to retry after a crash.
    """
    queue._validate_job_id(job_id)
    queue._validate_job_id(billing_job_id)
    if type(user_id) is not int or user_id <= 0:
        raise ValueError('Authenticated positive user ID required')
    with queue._db() as connection:
        inference = connection.execute(
            'SELECT operation,payload_json FROM jobs WHERE job_id=?', (job_id,)
        ).fetchone()
    if inference is None or inference['operation'] not in ('arranger', 'remix') or not inference['payload_json']:
        raise ValueError('Durable inference job required')
    # The account supplied by the caller must also be the account frozen
    # into the durable scheduler payload. Checking the ledger alone would
    # permit an unrelated inference to be attached to that account's job.
    try:
        payload = json.loads(inference['payload_json'])
    except (ValueError, TypeError) as exc:
        raise ValueError('Invalid durable inference payload') from exc
    if not isinstance(payload, dict):
        raise ValueError('Invalid durable inference payload')
    if 'schema_version' in payload:
        if type(payload['schema_version']) is not int or payload['schema_version'] != 1:
            raise ValueError('Unsupported durable inference schema')
        if type(payload.get('actor_user_id')) is not int or payload['actor_user_id'] != user_id:
            raise ValueError('Durable inference owner mismatch')
        if payload.get('adapter') != inference['operation']:
            raise ValueError('Durable inference adapter mismatch')
    elif payload.get('actor_user_id') is not None or payload.get('adapter') is not None:
        raise ValueError('Unversioned durable inference identity')
    with ai_billing.db() as connection:
        ai_billing._init(connection)
        ledger = connection.execute(
            'SELECT user_id,kind,status FROM ai_compute_jobs WHERE id=?', (billing_job_id,)
        ).fetchone()
    if ledger is None or int(ledger['user_id']) != user_id:
        raise ValueError('Billing job missing or belongs to another user')
    if ledger['kind'] != inference['operation']:
        raise ValueError('Billing job kind mismatch')
    if ledger['status'] not in ('running', status):
        raise ValueError('Billing job is in an incompatible state')
    return register(job_id, billing_job_id, status, usage, source=source, finished_at=finished_at)


def deliver(*, job_id=None, on_applied=None):
    """Retry durable settlements; callback enables isolated crash injection.

    Only an exact same-intent delivery may be retried after a crash between
    ledger commit and local acknowledgement. Failed deliveries stay pending.
    """
    if fcntl is None:
        raise RuntimeError('Billing outbox requires POSIX file locking')
    if job_id is not None:
        queue._validate_job_id(job_id)
    with _db() as con:
        if job_id:
            ids = [r[0] for r in con.execute("SELECT job_id FROM deliveries WHERE state='pending' AND job_id=?", (job_id,))]
        else:
            ids = [r[0] for r in con.execute("SELECT job_id FROM deliveries WHERE state='pending' ORDER BY created_at")]
    delivered = 0
    for jid in ids:
        lock_file = queue._ROOT / ('billing-' + jid + '.lock')
        with lock_file.open('a+b') as lock:
            os.chmod(lock_file, 0o600)
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
            with _db() as con:
                record = con.execute('SELECT * FROM deliveries WHERE job_id=?', (jid,)).fetchone()
            if record is None or record['state'] != 'pending':
                continue
            intent = json.loads(record['intent_json'])
            try:
                ai_billing.finish_job_idempotent(record['billing_job_id'], intent['status'], intent['usage'],
                                                  source=intent['source'], finished_at=intent['finished_at'])
                if on_applied is not None:
                    on_applied(jid)
            except Exception as exc:
                with _db() as con:
                    con.execute('UPDATE deliveries SET last_error=? WHERE job_id=? AND state=\'pending\'',
                                (str(exc)[:200], jid))
                raise
            with _db() as con:
                con.execute('BEGIN IMMEDIATE')
                result = con.execute("UPDATE deliveries SET state='delivered', delivered_at=?, last_error=NULL WHERE job_id=? AND state='pending'",
                                     (time.time(), jid))
                con.execute('COMMIT')
                delivered += result.rowcount
    return delivered


def inspect(job_id):
    queue._validate_job_id(job_id)
    with _db() as con:
        row = con.execute('SELECT job_id,billing_job_id,state,delivered_at,last_error FROM deliveries WHERE job_id=?',
                          (job_id,)).fetchone()
    return dict(row) if row else None
