"""Bounded, authenticated remote AI transport for desktop/native clients.

This module NEVER runs a local inference worker, including on network failures.
Callers must explicitly choose local execution via their settings to use one.
"""
from __future__ import annotations
from app.secure_https import https_urlopen

import base64
import json
import uuid
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit, urlunsplit
from urllib.request import Request

MAX_AUDIO_BYTES = 32 * 1024 * 1024
MAX_RESULT_BYTES = 32 * 1024 * 1024
ALLOWED_TYPES = {'audio/wav', 'application/zip', 'application/json'}


class RemoteAIError(RuntimeError):
    """Remote mode failed; do not fall back to local inference."""


def _endpoint(base_url: str, kind: str) -> str:
    from .ai_worker_registry import WORKER_KINDS
    if kind not in WORKER_KINDS:
        raise ValueError('Unsupported remote AI worker kind')
    parts = urlsplit(base_url)
    if parts.scheme != 'https' or not parts.netloc or parts.username or parts.password or parts.query or parts.fragment:
        raise ValueError('Remote AI server requires an HTTPS URL without credentials or query')
    path = parts.path.rstrip('/')
    if path in ('', '/api/ai-gateway'):
        path = '/api/ai-jobs'
    elif path != '/api/ai-jobs':
        raise ValueError('Expected MTA server URL or /api/ai-jobs or /api/ai-gateway')
    return urlunsplit((parts.scheme, parts.netloc, path + '/execute-audio/' + kind, '', ''))


def infer_audio(base_url: str, token: str, kind: str, wav: bytes, options: dict | None = None,
                *, timeout_seconds: float = 900, request_id: str | None = None,
                recover_on_failure: bool = True) -> tuple[bytes, str, str]:
    """Return (payload, MIME, job_id) or fail explicitly; never run local AI."""
    endpoint = _endpoint(base_url, kind)
    if not token or any(c in token for c in '\r\n'):
        raise ValueError('A valid remote AI bearer token is required')
    if not isinstance(wav, bytes) or not 0 < len(wav) <= MAX_AUDIO_BYTES:
        raise ValueError('Remote AI requires non-empty WAV bytes up to 32 MiB')
    from .ai_remote_transport import decode_audio_options
    encoded = base64.urlsafe_b64encode(json.dumps(options or {}, separators=(',', ':')).encode()).decode().rstrip('=')
    decode_audio_options(encoded)
    from .ai_request_dedup import _KEY
    key = request_id or uuid.uuid4().hex
    if not _KEY.fullmatch(key):
        raise ValueError('Invalid remote AI request id')
    headers = {'Authorization': 'Bearer ' + token, 'Content-Type': 'audio/wav',
               'Accept': 'audio/wav, application/zip, application/json', 'X-MTA-AI-Options': encoded,
               'X-MTA-AI-Idempotency-Key': key}
    req = Request(endpoint, data=wav, headers=headers, method='POST')  # noqa: S310 - HTTPS-only endpoint
    try:
        with https_urlopen(req, timeout=timeout_seconds) as response:  # noqa: S310 - _endpoint validates HTTPS and forbids credentials
            mime = response.headers.get('Content-Type', '').split(';', 1)[0].strip().lower()
            if mime not in ALLOWED_TYPES:
                raise RemoteAIError('Unsupported remote AI result type')
            declared = response.headers.get('Content-Length', '')
            if declared.isdecimal() and int(declared) > MAX_RESULT_BYTES:
                raise RemoteAIError('Remote AI result exceeds the size limit')
            payload = response.read(MAX_RESULT_BYTES + 1)
            if len(payload) > MAX_RESULT_BYTES:
                raise RemoteAIError('Remote AI result exceeds the size limit')
            job_id = response.headers.get('X-MTA-AI-Job-ID', '')
            if not job_id:
                raise RemoteAIError('Remote AI response lacks a job identifier')
            return payload, mime, job_id
    except (HTTPError, URLError, TimeoutError, OSError) as exc:
        # A lost response may hide a completed, already billed job. Never POST
        # again: a read-only replay uses the exact original idempotency key.
        # Do not attempt replay for explicit authentication/input failures.
        if recover_on_failure and not (isinstance(exc, HTTPError) and exc.code in (400, 401, 403, 413, 415, 422)):
            try:
                return recover_audio(base_url, token, key, timeout_seconds=min(30, timeout_seconds))
            except RemoteAIError:
                pass
        raise RemoteAIError('Remote AI request failed or result not yet recoverable; no local model was started') from exc


def recover_audio(base_url: str, token: str, request_id: str, *, timeout_seconds: float = 30) -> tuple[bytes, str, str]:
    """Retrieve an already-completed job without scheduling inference.

    Call only with the same request id used for a previous infer_audio call.
    An unavailable/expired result fails explicitly and never runs local AI.
    """
    from .ai_request_dedup import _KEY
    if not isinstance(request_id, str) or not _KEY.fullmatch(request_id):
        raise ValueError('Invalid remote AI request id')
    if not token or any(c in token for c in '\r\n'):
        raise ValueError('A valid remote AI bearer token is required')
    endpoint = _endpoint(base_url, 'whisper').split('/execute-audio/', 1)[0]
    req = Request(endpoint + '/request-result/' + request_id,  # noqa: S310 - HTTPS endpoint, validated id
                  headers={'Authorization': 'Bearer ' + token,
                           'Accept': 'audio/wav, application/zip, application/json'}, method='GET')  # noqa: S310 - HTTPS-only endpoint
    try:
        with https_urlopen(req, timeout=timeout_seconds) as response:  # noqa: S310 - HTTPS-only endpoint
            mime = response.headers.get('Content-Type', '').split(';', 1)[0].strip().lower()
            if mime not in ALLOWED_TYPES:
                raise RemoteAIError('Unsupported recovered AI result type')
            declared = response.headers.get('Content-Length', '')
            if declared.isdecimal() and int(declared) > MAX_RESULT_BYTES:
                raise RemoteAIError('Recovered AI result exceeds the size limit')
            payload = response.read(MAX_RESULT_BYTES + 1)
            if len(payload) > MAX_RESULT_BYTES:
                raise RemoteAIError('Recovered AI result exceeds the size limit')
            job_id = response.headers.get('X-MTA-AI-Job-ID', '')
            if not job_id:
                raise RemoteAIError('Recovered AI response lacks a job identifier')
            return payload, mime, job_id
    except (HTTPError, URLError, TimeoutError, OSError) as exc:
        raise RemoteAIError('Remote AI result unavailable; no local model was started') from exc
