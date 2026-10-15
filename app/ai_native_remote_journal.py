"""Crash-durable native remote request keys.

A pending request must be recovered read-only rather than resubmitted after a
network failure. Entries are scoped to endpoint, token, worker and input bytes.
"""


import hashlib
import json
import os
from pathlib import Path

import uuid
import time
import re


def _root() -> Path:
    from .native_ai_routing import _file
    return Path(os.getenv('MTA_NATIVE_REMOTE_JOURNAL', str(_file().parent / 'remote-pending'))).expanduser()


def _fingerprint(url: str, token: str, kind: str, wav: bytes, options: dict | None) -> str:
    canonical = json.dumps(options or {}, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()
    h = hashlib.sha256()
    for data in (url.encode(), token.encode(), kind.encode(), canonical, wav):
        h.update(len(data).to_bytes(8, 'big'))
        h.update(data)
    return h.hexdigest()


def _entry(fingerprint: str) -> Path:
    return _root() / (fingerprint + '.json')


def begin(url: str, token: str, kind: str, wav: bytes, options: dict | None) -> tuple[str, bool, str]:
    """Return (request_id, already_pending, fingerprint). Never erase pending work."""
    fingerprint = _fingerprint(url, token, kind, wav, options)
    directory = _root()
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    path = _entry(fingerprint)
    request_id = uuid.uuid4().hex
    try:
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        try:
            saved = json.loads(path.read_text(encoding='utf-8'))
        except (OSError, ValueError) as exc:
            raise RuntimeError('Native remote pending request journal is damaged; not resubmitting') from exc
        value = saved.get('request_id') if isinstance(saved, dict) else None
        if not isinstance(value, str) or len(value) != 32 or any(ch not in '0123456789abcdef' for ch in value):
            raise RuntimeError('Invalid native remote pending request; not resubmitting')
        return value, True, fingerprint
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            json.dump({'request_id': request_id, 'kind': kind, 'url': url, 'created_at': int(time.time())}, stream)
            stream.flush()
            os.fsync(stream.fileno())
    except BaseException:
        # Preserve even partially written record: do not risk duplicate billing.
        raise
    return request_id, False, fingerprint


def finish(fingerprint: str, request_id: str) -> None:
    """Remove only our own journal after the result was validated and consumed."""
    path = _entry(fingerprint)
    try:
        saved = json.loads(path.read_text(encoding='utf-8'))
        if saved.get('request_id') == request_id:
            path.unlink()
    except FileNotFoundError:
        return


def list_pending() -> list[dict]:
    """List native in-flight requests without exposing bearer tokens or source data.

    Corrupt records remain visible so an operator can diagnose them, but are
    never removed or silently resubmitted.
    """
    directory = _root()
    if not directory.is_dir():
        return []
    result = []
    for path in sorted(directory.glob('*.json')):
        if not re.fullmatch(r'[0-9a-f]{64}\.json', path.name) or path.is_symlink():
            continue
        try:
            if path.stat().st_size > 2048:
                raise ValueError('Oversized entry')
            data = json.loads(path.read_text(encoding='utf-8'))
            if not isinstance(data, dict) or not re.fullmatch(r'[0-9a-f]{32}', data.get('request_id', '')):
                raise ValueError('Invalid entry')
            kind = data.get('kind')
            if not isinstance(kind, str) or kind not in ('whisper','chords-ml','demucs','drumsep','sam-audio','singer-separation','backing-vocals'):
                kind = None
            result.append({'request_id': data['request_id'], 'kind': kind,
                           'created_at': data.get('created_at') if isinstance(data.get('created_at'), int) else None,
                           'recoverable': kind is not None})
        except (OSError, ValueError, TypeError):
            result.append({'request_id': None, 'kind': None, 'created_at': None,
                           'recoverable': False, 'damaged': True})
    return result


def read_owned_pending(request_id: str) -> dict:
    """Return metadata only for a request present in this native journal."""
    if not isinstance(request_id, str) or not re.fullmatch(r'[0-9a-f]{32}', request_id):
        raise ValueError('Invalid request identifier')
    for path in _root().glob('*.json') if _root().is_dir() else ():
        if not re.fullmatch(r'[0-9a-f]{64}\.json', path.name) or path.is_symlink():
            continue
        try:
            if path.stat().st_size > 2048:
                continue
            data = json.loads(path.read_text(encoding='utf-8'))
            if isinstance(data, dict) and data.get('request_id') == request_id:
                return data
        except (OSError, ValueError, TypeError):
            continue
    raise ValueError('Request not present in native pending journal')
