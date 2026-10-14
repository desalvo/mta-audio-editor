"""Durable, replayable generated-audio publication outbox.

This is a filesystem/project publication saga, NOT a distributed ACID commit
with the separate billing ledger.  The consumer must be idempotent by job_id.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import sqlite3
import stat
import tempfile
import time

try:
    import fcntl
except ImportError:  # pragma: no cover - Windows must not silently bypass locking
    fcntl = None

from . import ai_arranger_runtime as queue


def _root():
    root = queue._ROOT / 'publication'
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(root, 0o700)
    return root


def _check_outbox_file(path):
    try:
        mode = path.lstat().st_mode
    except FileNotFoundError:
        return
    if not stat.S_ISREG(mode):
        raise ValueError('Publication SQLite path must be a regular file')


def _open():
    db = _root() / 'outbox.sqlite3'
    for suffix in ('', '-wal', '-shm', '-journal'):
        _check_outbox_file(Path(str(db) + suffix))
    con = sqlite3.connect(db, isolation_level=None, timeout=30)
    try:
        con.row_factory = sqlite3.Row
        con.execute('PRAGMA journal_mode=WAL')
        con.execute('PRAGMA busy_timeout=30000')
        con.execute('''CREATE TABLE IF NOT EXISTS publications (
          job_id TEXT PRIMARY KEY, project_id TEXT NOT NULL,
          audio_sha256 TEXT NOT NULL, metadata TEXT NOT NULL,
          state TEXT NOT NULL CHECK(state IN ('pending','published')),
          staged_at REAL NOT NULL, published_at REAL
        )''')
        for suffix in ('', '-wal', '-shm', '-journal'):
            path = Path(str(db) + suffix)
            _check_outbox_file(path)
            if path.exists():
                os.chmod(path, 0o600, follow_symlinks=False)
        return con
    except BaseException:
        con.close()
        raise


def _stage_path(job_id):
    queue._validate_job_id(job_id)
    return _root() / (job_id + '.wav')


def _read_stage_regular(path):
    """Read a single regular staging inode without following a replacement symlink."""
    flags = os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_NONBLOCK', 0)
    fd = os.open(path, flags)
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode):
            raise ValueError('Staged audio must be a regular file')
        with os.fdopen(os.dup(fd), 'rb') as stream:
            contents = stream.read()
        current = path.lstat()
        if not stat.S_ISREG(current.st_mode) or (current.st_dev, current.st_ino) != (info.st_dev, info.st_ino):
            raise ValueError('Staged audio changed during read')
        return contents, (info.st_dev, info.st_ino)
    finally:
        os.close(fd)


def _stage_identity_matches(path, identity):
    try:
        info = path.lstat()
    except FileNotFoundError:
        return False
    return stat.S_ISREG(info.st_mode) and (info.st_dev, info.st_ino) == identity


def stage(job_id, project_id, audio, metadata):
    """Durably stage a WAV before its publication; repeated calls must agree."""
    queue._validate_job_id(job_id)
    if not isinstance(audio, bytes) or not audio:
        raise ValueError('Nonempty audio bytes required')
    if not isinstance(metadata, dict):
        raise ValueError('Publication metadata required')
    encoded = json.dumps(metadata, sort_keys=True, allow_nan=False)
    digest = hashlib.sha256(audio).hexdigest()
    path = _stage_path(job_id)
    with _open() as con:
        previous = con.execute('SELECT * FROM publications WHERE job_id=?', (job_id,)).fetchone()
        if previous:
            previous = _validated_publication(previous)
            if (previous['project_id'], previous['audio_sha256'], previous['metadata']) != (str(project_id), digest, encoded):
                raise ValueError('Conflicting staged publication replay')
            # A pending replay must not silently accept lost, swapped or tampered
            # staging: recovery would otherwise fail much later, after acceptance.
            if previous['state'] == 'pending':
                contents, _ = _read_stage_regular(path)
                if hashlib.sha256(contents).hexdigest() != digest:
                    raise ValueError('Staged WAV checksum mismatch on replay')
            return dict(previous)
    # Only ever publish a complete temporary file; never overwrite an existing stage.
    fd, tmp = tempfile.mkstemp(prefix='.stage-', suffix='.wav', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as stream:
            os.fchmod(stream.fileno(), 0o600)
            stream.write(audio)
            stream.flush()
            os.fsync(stream.fileno())
        if path.is_symlink() or path.exists():
            existing, _ = _read_stage_regular(path)
            if hashlib.sha256(existing).hexdigest() != digest:
                raise ValueError('Existing staged audio does not match job')
        else:
            # Atomic no-overwrite publish of the stage through hard-link.
            try:
                os.link(tmp, path)
            except FileExistsError:
                existing, _ = _read_stage_regular(path)
                if hashlib.sha256(existing).hexdigest() != digest:
                    raise ValueError('Conflicting staged audio')
        with _open() as con:
            con.execute('BEGIN IMMEDIATE')
            con.execute("INSERT OR IGNORE INTO publications(job_id,project_id,audio_sha256,metadata,state,staged_at) VALUES(?,?,?,?, 'pending',?)",
                        (job_id, str(project_id), digest, encoded, time.time()))
            row = con.execute('SELECT * FROM publications WHERE job_id=?', (job_id,)).fetchone()
            row = _validated_publication(row)
            if (row['project_id'], row['audio_sha256'], row['metadata']) != (str(project_id), digest, encoded):
                con.execute('ROLLBACK')
                raise ValueError('Conflicting publication registration')
            con.execute('COMMIT')
            return dict(row)
    finally:
        Path(tmp).unlink(missing_ok=True)


def recover(publish, *, job_id=None):
    """Replay pending staged publications with a process-shared per-job lock.

    Callback signature: publish(job_id, project_id, wav_bytes, metadata).
    The callback MUST recognize an already-published job; retries are expected.
    Failed callbacks stay pending. Only matching staged SHA-256 is consumed.
    """
    if fcntl is None:
        raise RuntimeError('Cross-process publication recovery requires POSIX flock')
    with _open() as con:
        if job_id is not None:
            queue._validate_job_id(job_id)
            rows = con.execute("SELECT job_id FROM publications WHERE state='pending' AND job_id=?", (job_id,)).fetchall()
        else:
            rows = con.execute("SELECT job_id FROM publications WHERE state='pending' ORDER BY staged_at").fetchall()
    published = 0
    for entry in rows:
        jid = entry['job_id']
        lock_path = _root() / (jid + '.lock')
        if lock_path.is_symlink():
            raise ValueError('Publication lock must not be a symlink')
        lock_fd = os.open(lock_path, os.O_CREAT | os.O_RDWR | getattr(os, 'O_NOFOLLOW', 0), 0o600)
        with os.fdopen(lock_fd, 'a+b') as lock:
            if not stat.S_ISREG(os.fstat(lock.fileno()).st_mode):
                raise ValueError('Publication lock must be a regular file')
            os.fchmod(lock.fileno(), 0o600)
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
            with _open() as con:
                row = con.execute('SELECT * FROM publications WHERE job_id=?', (jid,)).fetchone()
            if row is None:
                continue
            row = _validated_publication(row)
            if row['state'] != 'pending':
                continue
            path = _stage_path(jid)
            contents, identity = _read_stage_regular(path)
            if hashlib.sha256(contents).hexdigest() != row['audio_sha256']:
                raise ValueError('Staged WAV checksum mismatch for ' + jid)
            publish(jid, row['project_id'], contents, json.loads(row['metadata']))
            if not _stage_identity_matches(path, identity):
                raise ValueError('Staged audio replaced during publication for ' + jid)
            with _open() as con:
                con.execute('BEGIN IMMEDIATE')
                updated = con.execute("UPDATE publications SET state='published', published_at=? WHERE job_id=? AND state='pending' AND project_id=? AND audio_sha256=? AND metadata=? AND staged_at=? AND published_at IS NULL", (time.time(), jid, row['project_id'], row['audio_sha256'], row['metadata'], row['staged_at']))
                if updated.rowcount != 1:
                    con.execute('ROLLBACK')
                    raise ValueError('Publication record changed during callback for ' + jid)
                con.execute('COMMIT')
            if _stage_identity_matches(path, identity):
                path.unlink(missing_ok=True)
            published += 1
    return published


def _validated_publication(row):
    """Fail closed before publication state is exposed to queue/billing consumers."""
    import math
    item = dict(row)
    queue._validate_job_id(item['job_id'])
    if not isinstance(item['project_id'], str) or not item['project_id'].strip():
        raise ValueError('Invalid publication project identity')
    digest = item['audio_sha256']
    if not isinstance(digest, str) or len(digest) != 64 or any(ch not in '0123456789abcdef' for ch in digest):
        raise ValueError('Invalid publication audio digest')
    try:
        metadata = json.loads(item['metadata'], parse_constant=lambda value: (_ for _ in ()).throw(ValueError('Nonfinite metadata')))
    except (TypeError, ValueError) as exc:
        raise ValueError('Invalid publication metadata') from exc
    if not isinstance(metadata, dict) or json.dumps(metadata, sort_keys=True, allow_nan=False) != item['metadata']:
        raise ValueError('Inconsistent publication metadata')
    if item['state'] not in ('pending', 'published'):
        raise ValueError('Invalid publication state')
    staged = item['staged_at']
    completed = item['published_at']
    if not isinstance(staged, (int, float)) or not math.isfinite(staged) or staged <= 0:
        raise ValueError('Invalid publication staging timestamp')
    if item['state'] == 'pending' and completed is not None:
        raise ValueError('Pending publication has completion timestamp')
    if item['state'] == 'published' and (not isinstance(completed, (int, float)) or not math.isfinite(completed) or completed < staged):
        raise ValueError('Published state lacks valid completion timestamp')
    return item


def status(job_id):
    queue._validate_job_id(job_id)
    with _open() as con:
        row = con.execute('SELECT * FROM publications WHERE job_id=?', (job_id,)).fetchone()
        if row is None:
            return None
        item = _validated_publication(row)
        return {key: item[key] for key in ('job_id', 'project_id', 'state', 'audio_sha256')}


def published_jobs():
    """Read completed durable publications for scheduler crash reconciliation."""
    with _open() as con:
        rows = con.execute('SELECT * FROM publications').fetchall()
        records = [_validated_publication(row) for row in rows]
        return [item['job_id'] for item in records if item['state'] == 'published']
