"""Opt-in bounded result replay for idempotent AI jobs.

Only the authenticated request owner can obtain an artifact through the API.
Temporary outputs are *not* counted as persistent user storage; operators
must configure retention and filesystem cleanup separately.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import tempfile
import time

MAX_BYTES = 32 * 1024 * 1024
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


def save(user_id: int, key: str, payload: bytes, media_type: str, job_id: str) -> bool:
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
    return True


def load(user_id: int, key: str, expected_job_id: str) -> tuple[bytes, str] | None:
    root = _root()
    if root is None:
        return None
    blob, metadata = _paths(root, user_id, key)
    if not blob.is_file() or not metadata.is_file() or blob.is_symlink() or metadata.is_symlink():
        return None
    try:
        details = json.loads(metadata.read_text())
        if details['job_id'] != expected_job_id or int(details['expires_at']) < time.time():
            return None
        if details['media_type'] not in ALLOWED or blob.stat().st_size > MAX_BYTES:
            return None
        content = blob.read_bytes()
        if hashlib.sha256(content).hexdigest() != details['sha256']:
            return None
        return content, details['media_type']
    except (OSError, ValueError, KeyError, TypeError):
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
        if metadata.is_symlink() or len(metadata.stem) != 64 or any(c not in '0123456789abcdef' for c in metadata.stem):
            continue
        examined += 1
        blob = root / (metadata.stem + '.bin')
        if blob.is_symlink():
            continue
        try:
            details = json.loads(metadata.read_text())
            expiry = details.get('expires_at')
            if type(expiry) is not int or expiry >= instant:
                continue
            expired += 1
            if not dry_run:
                metadata.unlink()
                if blob.is_file() and not blob.is_symlink():
                    blob.unlink()
                removed += 1
        except (OSError, ValueError, TypeError):
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
