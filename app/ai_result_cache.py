"""Opt-in bounded result replay for idempotent AI jobs.

Only the authenticated request owner can obtain an artifact through the API.
Temporary outputs are *not* counted as persistent user storage; operators
must configure retention and filesystem cleanup separately.
"""
from __future__ import annotations

import hashlib
import contextlib
from . import platform_file_lock as fcntl
import stat
import json
import os
from pathlib import Path
import tempfile
import time

from .ai_payload_limits import MAX_RESULT_BYTES as MAX_BYTES
ALLOWED = {'audio/wav', 'application/zip', 'application/json'}


def _root() -> Path | None:
    configured = os.environ.get('MTA_AI_RESULT_CACHE_DIR', '').strip()
    if not configured:
        return None
    root = Path(configured).expanduser().resolve()
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    if Path(configured).expanduser().is_symlink():
        raise ValueError('Unsafe result cache directory')
    return root


def _paths(root: Path, user_id: int, key: str) -> tuple[Path, Path]:
    if not isinstance(user_id, int) or user_id <= 0:
        raise ValueError('Invalid user')
    from .ai_request_dedup import _KEY
    if not _KEY.fullmatch(key):
        raise ValueError('Invalid AI idempotency key')
    opaque = hashlib.sha256(f'{user_id}:{key}'.encode()).hexdigest()
    return root / (opaque + '.bin'), root / (opaque + '.json')


@contextlib.contextmanager
def _entry_lock(root: Path, blob: Path):
    """Serialize writes/readers of a single cached request across API workers."""
    path = root / (blob.stem + '.lock')
    if path.is_symlink():
        raise ValueError('Unsafe cache lock')
    fd = os.open(path, os.O_CREAT | os.O_RDWR | getattr(os, 'O_NOFOLLOW', 0), 0o600)
    try:
        if path.is_symlink() or not stat.S_ISREG(os.fstat(fd).st_mode):
            raise ValueError('Unsafe cache lock')
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


def _read_regular(path: Path, limit: int) -> bytes:
    if path.is_symlink():
        raise ValueError('Unsafe cached artifact')
    fd = os.open(path, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_NONBLOCK', 0))
    try:
        metadata = os.fstat(fd)
        if path.is_symlink() or not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1 or metadata.st_size > limit:
            raise ValueError('Unsafe cached artifact')
        with os.fdopen(fd, 'rb', closefd=False) as stream:
            data = stream.read(metadata.st_size + 1)
        if len(data) != metadata.st_size or os.fstat(fd).st_size != metadata.st_size:
            raise ValueError('Oversized cached artifact')
        return data
    finally:
        os.close(fd)


def save(user_id: int, key: str, payload: bytes, media_type: str, job_id: str, *, metering_envelope: dict | None = None) -> bool:
    root = _root()
    if root is None:
        return False
    if media_type not in ALLOWED or not 0 < len(payload) <= MAX_BYTES:
        raise ValueError('Invalid cached AI artifact')
    if not isinstance(job_id, str) or not job_id or len(job_id) > 128:
        raise ValueError('Invalid AI job id')
    cleanup_if_due()
    blob, metadata = _paths(root, user_id, key)
    ttl = max(60, min(604800, int(os.getenv('MTA_AI_RESULT_CACHE_TTL', '86400'))))
    details = {'job_id': job_id, 'media_type': media_type,
               'sha256': hashlib.sha256(payload).hexdigest(), 'expires_at': int(time.time()) + ttl}
    if metering_envelope is not None:
        from .ai_remote_metering_attestation import verify_rotating
        from .ai_remote_keyring import active_keyring
        worker_id = metering_envelope.get('worker_id') if isinstance(metering_envelope, dict) else None
        verify_rotating(active_keyring(), metering_envelope, job_id=job_id, request_id=key, worker_id=worker_id)
        details['metering_envelope'] = metering_envelope
    # The payload and its signed-by-digest metadata become visible under one
    # per-key lock. A crash between replacements remains fail-closed on load.
    with _entry_lock(root, blob):
        for path, content in ((blob, payload), (metadata, json.dumps(details).encode())):
            fd, temp_path = tempfile.mkstemp(prefix='.mta-ai-', dir=root)
            try:
                with os.fdopen(fd, 'wb') as handle:
                    handle.write(content)
                    handle.flush()
                    os.fsync(handle.fileno())
                os.replace(temp_path, path)
            finally:
                if os.path.exists(temp_path):
                    os.unlink(temp_path)
        if hasattr(os, 'O_DIRECTORY'):
            dirfd = os.open(root, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(dirfd)
            finally:
                os.close(dirfd)
        # Windows has no POSIX directory FD; files were fsynced before replace.
    return True


def load(user_id: int, key: str, expected_job_id: str) -> tuple[bytes, str] | None:
    root = _root()
    if root is None:
        return None
    blob, metadata = _paths(root, user_id, key)
    try:
        with _entry_lock(root, blob):
            details = json.loads(_read_regular(metadata, 4096))
            if details['job_id'] != expected_job_id or int(details['expires_at']) < time.time():
                return None
            if details['media_type'] not in ALLOWED:
                return None
            content = _read_regular(blob, MAX_BYTES)
            if not content or hashlib.sha256(content).hexdigest() != details['sha256']:
                return None
            return content, details['media_type']
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError):
        return None


def load_with_metering(user_id: int, key: str, expected_job_id: str) -> tuple[bytes, str, dict | None] | None:
    """Replay a result and its authenticated evidence under one per-request lock.

    Revoked signing keys invalidate the evidence; never send an unverified
    envelope. Unlike ``load``, this method explicitly requires matching
    persisted metering when metadata contains an envelope.
    """
    root = _root()
    if root is None:
        return None
    blob, metadata = _paths(root, user_id, key)
    try:
        with _entry_lock(root, blob):
            details = json.loads(_read_regular(metadata, 8192))
            if details.get('job_id') != expected_job_id or type(details.get('expires_at')) is not int or details['expires_at'] < time.time():
                return None
            if details.get('media_type') not in ALLOWED:
                return None
            contents = _read_regular(blob, MAX_BYTES)
            if not contents or hashlib.sha256(contents).hexdigest() != details.get('sha256'):
                return None
            envelope = details.get('metering_envelope')
            if envelope is not None:
                from .ai_remote_metering_attestation import verify_rotating
                from .ai_remote_keyring import active_keyring
                if not isinstance(envelope, dict):
                    return None
                verify_rotating(active_keyring(), envelope, job_id=expected_job_id,
                                request_id=key, worker_id=envelope.get('worker_id'))
            return contents, details['media_type'], envelope
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError):
        return None


def purge_expired(*, now: int | None = None, dry_run: bool = True) -> dict:
    """Remove expired opaque cache entries only; never follow symlinks.

    Run periodically from a systemd timer/cron. Fresh or unreadable entries
    are retained conservatively for operator investigation.
    """
    root = _root()
    if root is None:
        return {'examined': 0, 'expired': 0, 'removed': 0}
    instant = int(time.time()) if now is None else int(now)
    examined = expired = removed = 0
    for metadata in root.glob('*.json'):
        if len(metadata.stem) != 64 or any(ch not in '0123456789abcdef' for ch in metadata.stem):
            continue
        examined += 1
        blob = root / (metadata.stem + '.bin')
        # The same lock is used by save() and load(). Without it the cleaner
        # can delete a newly committed result after reading an old expiry.
        try:
            with _entry_lock(root, blob):
                details = json.loads(_read_regular(metadata, 4096))
                expiry = details.get('expires_at')
                if type(expiry) is not int or expiry >= instant:
                    continue
                expired += 1
                if dry_run:
                    continue
                # Refuse symlinks and multiply-linked inodes before unlinking.
                # Missing blobs are acceptable after an interrupted write.
                if blob.exists() or blob.is_symlink():
                    _read_regular(blob, MAX_BYTES)
                metadata.unlink()
                if blob.exists():
                    blob.unlink()
                removed += 1
        except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError):
            continue
    return {'examined': examined, 'expired': expired, 'removed': removed}


def cleanup_if_due(*, now: int | None = None) -> dict:
    """Throttled automatic cleanup; safe for concurrent API workers.

    A separate timer remains recommended when requests are infrequent.
    """
    root = _root()
    if root is None:
        return {'examined': 0, 'expired': 0, 'removed': 0}
    interval = max(60, min(86400, int(os.getenv('MTA_AI_RESULT_CACHE_CLEANUP_INTERVAL', '3600'))))
    instant = int(time.time()) if now is None else int(now)
    marker = root / '.last-cleanup'
    try:
        if marker.is_symlink():
            raise ValueError('Unsafe cleanup marker')
        if marker.exists() and 0 <= instant - int(marker.stat().st_mtime) < interval:
            return {'examined': 0, 'expired': 0, 'removed': 0}
        # Exclusive creation avoids multiple workers performing the same pass.
        lock = root / '.cleanup-lock'
        try:
            fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError:
            return {'examined': 0, 'expired': 0, 'removed': 0}
        try:
            os.close(fd)
            result = purge_expired(now=instant, dry_run=False)
            marker.touch()
            return result
        finally:
            lock.unlink(missing_ok=True)
    except (OSError, ValueError):
        return {'examined': 0, 'expired': 0, 'removed': 0}


def recover_completed_job_id(user_id: int, key: str) -> str | None:
    """Recover a published result's job identity without executing inference.

    Both metadata and payload must pass the same ownership, expiry, inode and
    SHA-256 checks as normal GET replay. Never trust metadata alone.
    """
    root = _root()
    if root is None:
        return None
    blob, metadata = _paths(root, user_id, key)
    try:
        with _entry_lock(root, blob):
            details = json.loads(_read_regular(metadata, 8192))
            job_id = details.get('job_id')
            if not isinstance(job_id, str) or not 1 <= len(job_id) <= 128:
                return None
            if details.get('media_type') not in ALLOWED:
                return None
            if type(details.get('expires_at')) is not int or details['expires_at'] < time.time():
                return None
            contents = _read_regular(blob, MAX_BYTES)
            if not contents or hashlib.sha256(contents).hexdigest() != details.get('sha256'):
                return None
            # Crash recovery is an authoritative completed-state transition.
            # Never finalize the ledger from a cached payload whose signed
            # metering evidence cannot pass the same checks as result replay.
            envelope = details.get('metering_envelope')
            if envelope is not None:
                if not isinstance(envelope, dict):
                    return None
                from .ai_remote_metering_attestation import verify_rotating
                from .ai_remote_keyring import active_keyring
                verify_rotating(active_keyring(), envelope, job_id=job_id,
                                request_id=key, worker_id=envelope.get('worker_id'))
            return job_id
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError):
        return None
