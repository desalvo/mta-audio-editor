"""Bounded, authenticated remote AI transport for desktop/native clients.

This module NEVER runs a local inference worker, including on network failures.
Callers must explicitly choose local execution via their settings to use one.
"""
from __future__ import annotations
from app.secure_https import https_urlopen

import base64
import json
import hashlib
import math
import time
import re
import io
import zipfile
import uuid
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit, urlunsplit
from urllib.request import Request

from .ai_payload_limits import MAX_SOURCE_BYTES as MAX_AUDIO_BYTES, MAX_RESULT_BYTES
ALLOWED_TYPES = {'audio/wav', 'application/zip', 'application/json'}


class RemoteAIError(RuntimeError):
    """Remote mode failed; do not fall back to local inference."""


def _endpoint(base_url: str, kind: str) -> str:
    import re
    if not isinstance(kind,str) or not re.fullmatch(r'[a-z][a-z0-9-]{0,63}',kind):
        raise ValueError('Unsupported remote AI worker kind')
    parts = urlsplit(base_url)
    if parts.scheme != 'https' or not parts.netloc or parts.username or parts.password or parts.query or parts.fragment:
        raise ValueError('Remote AI server requires an HTTPS URL without credentials or query')
    try:
        port = parts.port
        hostname = parts.hostname
    except ValueError as exc:
        raise ValueError('Invalid remote AI host or port') from exc
    if not hostname or any(ord(c) < 33 or ord(c) == 127 for c in base_url) or '\\' in base_url:
        raise ValueError('Invalid remote AI URL characters')
    if port == 0 or (hostname.startswith('[') and hostname.endswith(']')):
        raise ValueError('Invalid remote AI authority')
    if '%' in parts.netloc or '%' in parts.path or parts.netloc.endswith(':'):
        raise ValueError('Remote AI URL cannot contain encoded authority or path aliases')
    path = parts.path.rstrip('/')
    if path in ('', '/api/ai-gateway'):
        path = '/api/ai-jobs'
    elif path != '/api/ai-jobs':
        raise ValueError('Expected MTA server URL or /api/ai-jobs or /api/ai-gateway')
    return urlunsplit((parts.scheme, parts.netloc, path + '/execute-audio/' + kind, '', ''))


def _cancel_admitted_if_requested(base_url, token, request_id, cancel_event):
    """Best-effort durable cancellation; never claim physical worker termination.

    A cancellation may race with POST delivery. The server-side idempotency
    barrier prevents a late response from being published after this request.
    """
    if cancel_event is None or not cancel_event.is_set():
        return False
    try:
        cancel_remote_request(base_url, token, request_id, timeout_seconds=2)
    except (RemoteAIError, ValueError):
        # The original cancellation remains authoritative locally. This does
        # not imply the remote request stopped or even reached the server.
        pass
    return True


def infer_audio(base_url: str, token: str, kind: str, wav: bytes, options: dict | None = None,
                *, timeout_seconds: float = 900, request_id: str | None = None,
                recover_on_failure: bool = True, require_attestation: bool = False,
                metering_sink=None, metering_keyring=None, cancel_event=None, source_format='wav') -> tuple[bytes, str, str]:
    """Return (payload, MIME, job_id) or fail explicitly; never run local AI."""
    if cancel_event is not None and cancel_event.is_set():
        raise RemoteAIError("Remote AI cancelled before submission")
    endpoint = _endpoint(base_url, kind)
    if options is not None and not isinstance(options, dict):
        raise ValueError('AI options must be an object')
    from .model_license_policy import authorize_remote_execution
    try:authorize_remote_execution(kind, options if options is not None else {})
    except (AttributeError,TypeError,KeyError) as exc:
        raise ValueError('Invalid remote model selection options') from exc
    if not isinstance(token, str) or not token or len(token) > 4096 or any(ord(c) < 33 or ord(c) > 126 for c in token):
        raise ValueError('A valid remote AI bearer token is required')
    if source_format not in ('wav','score') or (source_format=='score' and kind not in ('vocal-harmony','vocal-synthesis')):raise ValueError('Unsupported remote source format')
    if source_format=='score':
        from .studio_score import validate
        validate(wav)
    if not isinstance(wav, bytes) or not 0 < len(wav) <= (8*1024*1024 if source_format=='score' else MAX_AUDIO_BYTES):
        raise ValueError('Remote AI requires non-empty WAV bytes within the source size limit')
    from .ai_remote_transport import decode_audio_options, validate_audio_options
    if options is not None and not isinstance(options, dict):
        raise ValueError('Remote AI options must be an object')
    request_body=wav;studio_envelope=False
    try:
        validate_audio_options(options if options is not None else {})
        raw_options = json.dumps(options if options is not None else {}, separators=(',', ':'), allow_nan=False).encode('utf-8')
        if source_format=='score' and len(raw_options)>4096:raise ValueError('Use structured body for large score options')
        encoded = base64.urlsafe_b64encode(raw_options).decode().rstrip('=')
        decode_audio_options(encoded)
    except (TypeError, ValueError, OverflowError) as exc:
        if source_format!='score':raise ValueError('Remote AI options must be bounded finite JSON values') from exc
        from .studio_score import pack_request
        request_body=pack_request(wav,kind,options if options is not None else {})
        encoded='e30';studio_envelope=True
    from .ai_request_dedup import _KEY
    key = uuid.uuid4().hex if request_id is None else request_id
    if not isinstance(key, str) or not _KEY.fullmatch(key):
        raise ValueError('Invalid remote AI request id')
    if isinstance(timeout_seconds, bool) or not isinstance(timeout_seconds, (int, float)) or not math.isfinite(timeout_seconds) or timeout_seconds <= 0:
        raise ValueError('Remote AI timeout must be a positive finite number')
    headers = {'Authorization': 'Bearer ' + token, 'Content-Type': 'application/vnd.mta.studio-request+json' if studio_envelope else 'application/vnd.mta.score+json' if source_format=='score' else 'audio/wav',
               'Accept': 'audio/wav, application/zip, application/json', 'X-MTA-AI-Options': encoded,
               'X-MTA-AI-Idempotency-Key': key}
    req = Request(endpoint, data=request_body, headers=headers, method='POST')  # noqa: S310 - HTTPS-only endpoint
    try:
        with https_urlopen(req, timeout=timeout_seconds) as response:  # noqa: S310 - HTTPS endpoint
            return _read_verified_result(response, expected_request_id=key, require_attestation=require_attestation,
                                         metering_sink=metering_sink, metering_keyring=metering_keyring,
                                         cancel_event=cancel_event)
    except RemoteAIError:
        # A result rejected because of a concurrent cancellation must also
        # signal the remote persistent cancellation barrier where possible.
        _cancel_admitted_if_requested(base_url, token, key, cancel_event)
        raise
    except (HTTPError, URLError, TimeoutError, OSError) as exc:
        # A lost response may hide a completed, already billed job. Never POST
        # again: a read-only replay uses the exact original idempotency key.
        # Do not attempt replay for explicit authentication/input failures.
        if _cancel_admitted_if_requested(base_url, token, key, cancel_event):
            raise RemoteAIError("Remote AI cancelled; remote stop not guaranteed") from exc
        if recover_on_failure and not (isinstance(exc, HTTPError) and exc.code in (400, 401, 403, 409, 413, 415, 422)):
            try:
                return recover_audio(base_url, token, key, timeout_seconds=min(30, timeout_seconds),
                                     require_attestation=require_attestation, metering_sink=metering_sink,
                                     metering_keyring=metering_keyring, cancel_event=cancel_event)
            except RemoteAIError:
                pass
        raise RemoteAIError('Remote AI request failed or result not yet recoverable; no local model was started') from exc



def remote_request_status(base_url: str, token: str, request_id: str, *, timeout_seconds: float = 10) -> dict:
    """Read the owning user's durable remote claim without executing a model.

    This is intentionally not an inference retry. Missing or terminal claims
    remain terminal and are never silently resubmitted.
    """
    from .ai_request_dedup import _KEY
    if not isinstance(request_id, str) or not _KEY.fullmatch(request_id):
        raise ValueError('Invalid remote AI request id')
    if not isinstance(token, str) or not token or len(token) > 4096 or any(ord(c) < 33 or ord(c) > 126 for c in token):
        raise ValueError('A valid remote AI bearer token is required')
    if (isinstance(timeout_seconds, bool) or not isinstance(timeout_seconds, (int, float))
            or not math.isfinite(timeout_seconds) or timeout_seconds <= 0):
        raise ValueError('Remote AI timeout must be a positive finite number')
    endpoint = _endpoint(base_url, 'whisper').split('/execute-audio/', 1)[0]
    req = Request(endpoint + '/request-status/' + request_id,  # noqa: S310 - validated HTTPS endpoint
                  headers={'Authorization': 'Bearer ' + token, 'Accept': 'application/json'},
                  method='GET')
    try:
        with https_urlopen(req, timeout=timeout_seconds) as response:
            raw = response.read(4097)
    except (HTTPError, URLError, TimeoutError, OSError) as exc:
        raise RemoteAIError('Remote AI request status unavailable; inference was not retried') from exc
    if len(raw) > 4096:
        raise RemoteAIError('Oversized remote AI status response')
    try:
        result = json.loads(raw)
    except (ValueError, UnicodeError, TypeError) as exc:
        raise RemoteAIError('Invalid remote AI status response') from exc
    if not isinstance(result, dict) or result.get('state') not in ('admitted', 'completed', 'failed', 'cancelled'):
        raise RemoteAIError('Unrecognized remote AI request state')
    worker_id = result.get('job_id')
    if worker_id is not None and (not isinstance(worker_id, str) or not 1 <= len(worker_id) <= 128
                               or any(ord(ch) < 33 or ord(ch) > 126 for ch in worker_id)):
        raise RemoteAIError('Invalid remote AI job identity')
    if result['state'] == 'completed' and not worker_id:
        raise RemoteAIError('Completed remote AI request is missing a job identifier')
    if result['state'] != 'completed' and worker_id is not None:
        raise RemoteAIError('Non-completed remote AI request contains a job identifier')
    return {'state': result['state'], 'job_id': worker_id}


def recover_after_lost_response(base_url: str, token: str, request_id: str, *,
                                timeout_seconds: float = 10, max_wait_seconds: float = 0,
                                poll_interval_seconds: float = 1,
                                require_attestation: bool = False, metering_sink=None,
                                metering_keyring=None, cancel_event=None) -> tuple[bytes, str, str]:
    """Recover a completed, settled request, without ever repeating inference.

    A finite optional wait covers asynchronous completion following network
    failure; default performs a single status lookup. Metering verification and
    idempotent ledger delivery are performed by the original GET result path.
    """
    if (isinstance(max_wait_seconds, bool) or not isinstance(max_wait_seconds, (int, float))
            or not math.isfinite(max_wait_seconds) or max_wait_seconds < 0 or max_wait_seconds > 3600):
        raise ValueError('Recovery wait must be between 0 and 3600 seconds')
    if (isinstance(poll_interval_seconds, bool) or not isinstance(poll_interval_seconds, (int, float))
            or not math.isfinite(poll_interval_seconds) or poll_interval_seconds <= 0):
        raise ValueError('Recovery poll interval must be positive')
    deadline = time.monotonic() + max_wait_seconds
    while True:
        if cancel_event is not None and cancel_event.is_set():
            _cancel_admitted_if_requested(base_url, token, request_id, cancel_event)
            raise RemoteAIError('Remote AI recovery cancelled')
        status = remote_request_status(base_url, token, request_id, timeout_seconds=timeout_seconds)
        if status['state'] == 'completed':
            return recover_audio(base_url, token, request_id,
                                 timeout_seconds=timeout_seconds,
                                 require_attestation=require_attestation,
                                 metering_sink=metering_sink,
                                 metering_keyring=metering_keyring, cancel_event=cancel_event)
        if status['state'] in ('failed', 'cancelled'):
            raise RemoteAIError('Remote AI request is ' + status['state'] + '; inference will not be repeated')
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise RemoteAIError('Remote AI request is still admitted; inference was not repeated')
        # Event wait permits cancellation during the wait without busy polling.
        delay = min(poll_interval_seconds, remaining)
        if cancel_event is not None:
            if cancel_event.wait(delay):
                _cancel_admitted_if_requested(base_url, token, request_id, cancel_event)
                raise RemoteAIError('Remote AI recovery cancelled')
        else:
            time.sleep(delay)


def recover_audio(base_url: str, token: str, request_id: str, *, timeout_seconds: float = 30,
                  require_attestation: bool = False, metering_sink=None,
                  metering_keyring=None, cancel_event=None) -> tuple[bytes, str, str]:
    """Retrieve an already-completed job without scheduling inference.

    Call only with the same request id used for a previous infer_audio call.
    An unavailable/expired result fails explicitly and never runs local AI.
    """
    if cancel_event is not None and cancel_event.is_set():
        raise RemoteAIError("Remote AI cancelled before result recovery")
    from .ai_request_dedup import _KEY
    if not isinstance(request_id, str) or not _KEY.fullmatch(request_id):
        raise ValueError('Invalid remote AI request id')
    if not isinstance(token, str) or not token or len(token) > 4096 or any(ord(c) < 33 or ord(c) > 126 for c in token):
        raise ValueError('A valid remote AI bearer token is required')
    if isinstance(timeout_seconds, bool) or not isinstance(timeout_seconds, (int, float)) or not math.isfinite(timeout_seconds) or timeout_seconds <= 0:
        raise ValueError('Remote AI timeout must be a positive finite number')
    endpoint = _endpoint(base_url, 'whisper').split('/execute-audio/', 1)[0]
    req = Request(endpoint + '/request-result/' + request_id,  # noqa: S310 - HTTPS endpoint, validated id
                  headers={'Authorization': 'Bearer ' + token,
                           'Accept': 'audio/wav, application/zip, application/json'}, method='GET')  # noqa: S310 - HTTPS-only endpoint
    try:
        with https_urlopen(req, timeout=timeout_seconds) as response:  # noqa: S310 - HTTPS endpoint
            return _read_verified_result(response, expected_request_id=request_id,
                                         require_attestation=require_attestation, metering_sink=metering_sink,
                                         metering_keyring=metering_keyring, cancel_event=cancel_event)
    except (HTTPError, URLError, TimeoutError, OSError) as exc:
        raise RemoteAIError('Remote AI result unavailable; no local model was started') from exc


def _read_verified_result(response, *, expected_request_id: str | None = None,
                          require_attestation: bool = False, metering_sink=None,
                          metering_keyring=None, cancel_event=None) -> tuple[bytes, str, str]:
    """Validate the complete response before exposing an inferred artifact.

    Apply identical rules on first delivery and idempotent GET recovery.
    No metadata from a remote worker is trusted merely because TLS succeeded.
    """
    if cancel_event is not None and cancel_event.is_set():
        raise RemoteAIError("Remote AI cancelled before result acceptance")
    mime = response.headers.get('Content-Type', '').split(';', 1)[0].strip().lower()
    if mime not in ALLOWED_TYPES:
        raise RemoteAIError('Unsupported remote AI result type')
    declared = response.headers.get('Content-Length', '')
    if not isinstance(declared, str) or len(declared) > 12:
        raise RemoteAIError('Invalid remote AI result length')
    if declared:
        if not declared.isdecimal():
            raise RemoteAIError('Invalid remote AI result length')
        if int(declared) > MAX_RESULT_BYTES:
            raise RemoteAIError('Remote AI result exceeds the size limit')
    job_id = response.headers.get('X-MTA-AI-Job-ID', '')
    if (not isinstance(job_id, str) or not 1 <= len(job_id) <= 128
            or any(ord(ch) < 33 or ord(ch) > 126 for ch in job_id)):
        raise RemoteAIError('Remote AI response lacks a valid job identifier')
    bound_request = response.headers.get('X-MTA-AI-Request-ID')
    if require_attestation and not bound_request:
        raise RemoteAIError('Remote AI result lacks required request binding')
    if bound_request is not None and (not isinstance(bound_request, str) or len(bound_request) > 128 or bound_request != expected_request_id):
        raise RemoteAIError('Remote AI result belongs to a different request')
    # Read actual chunks rather than asking an unlengthened HTTP stream to
    # allocate the entire operator-configurable ceiling for a small response.
    parts = []
    total = 0
    while total <= MAX_RESULT_BYTES:
        requested = min(1024 * 1024, MAX_RESULT_BYTES + 1 - total)
        chunk = response.read(requested)
        if not chunk:
            break
        parts.append(chunk)
        total += len(chunk)
        if len(chunk) < requested:
            break
    payload = b''.join(parts)
    if not payload or len(payload) > MAX_RESULT_BYTES:
        raise RemoteAIError('Remote AI result is empty or exceeds the size limit')
    if declared and len(payload) != int(declared):
        raise RemoteAIError('Truncated or inconsistent remote AI result')
    # Current servers attest the delivered bytes on POST and GET replay.
    # Preserve compatibility with older servers which omit the header.
    digest = response.headers.get('X-MTA-AI-Result-SHA256')
    if require_attestation and digest is None:
        raise RemoteAIError('Remote AI result lacks required digest')
    if digest is not None:
        if not isinstance(digest, str) or re.fullmatch(r'[0-9a-f]{64}', digest) is None:
            raise RemoteAIError('Malformed remote AI result digest')
        if hashlib.sha256(payload).hexdigest() != digest:
            raise RemoteAIError('Remote AI result integrity mismatch')
    if require_attestation:
        _validate_attested_artifact(payload, mime)
    if cancel_event is not None and cancel_event.is_set():
        raise RemoteAIError("Remote AI cancelled before settlement")
    if metering_sink is not None:
        if not callable(metering_sink):
            raise ValueError('Metering sink must be callable')
        raw = response.headers.get('X-MTA-AI-Metering-V2')
        if not raw or len(raw) > 4096 or not bound_request or metering_keyring is None:
            raise RemoteAIError('Authenticated remote metering evidence required')
        from .ai_remote_metering_attestation import verify_rotating
        try:
            envelope = json.loads(raw)
            if not isinstance(envelope, dict):
                raise ValueError('Invalid envelope')
            worker_id = envelope.get('worker_id')
            usage = verify_rotating(metering_keyring, envelope, job_id=job_id,
                                    request_id=expected_request_id, worker_id=worker_id)
        except (ValueError, TypeError) as exc:
            raise RemoteAIError('Invalid authenticated remote metering evidence') from exc
        # Called only after verifying the result's bytes, request identity and
        # worker HMAC. Sink owns local durable-job authorization and persistence.
        if cancel_event is not None and cancel_event.is_set():
            raise RemoteAIError("Remote AI cancelled before metering persistence")
        metering_sink(envelope, usage)
    return payload, mime, job_id


def _validate_attested_artifact(payload: bytes, mime: str) -> None:
    """Check the *type* of bytes covered by a required delivery attestation.

    Strict mode applies content checks on both original POST and replay GET.
    This is not a guarantee that an authenticated server executed a real model.
    """
    if mime == 'audio/wav':
        if (len(payload) < 44 or payload[:4] != b'RIFF'
                or payload[8:12] != b'WAVE'
                or int.from_bytes(payload[4:8], 'little') != len(payload) - 8):
            raise RemoteAIError('Attested WAV result has an invalid RIFF envelope')
    elif mime == 'application/json':
        try:
            document = json.loads(payload.decode('utf-8'),
                                  object_pairs_hook=_strict_unique_pairs,
                                  parse_constant=lambda _: (_ for _ in ()).throw(ValueError('Nonfinite JSON constant')))
        except (ValueError, UnicodeError, RecursionError) as exc:
            raise RemoteAIError('Attested JSON result is invalid') from exc
        if not isinstance(document, (dict, list)):
            raise RemoteAIError('Attested JSON result must be an object or array')
    elif mime == 'application/zip':
        try:
            with zipfile.ZipFile(io.BytesIO(payload)) as archive:
                infos = archive.infolist()
                if not infos or len(infos) > 512:
                    raise RemoteAIError('Attested ZIP result has an invalid entry count')
                total = 0
                names = set()
                for info in infos:
                    name = info.filename
                    components = name.replace('\\', '/').split('/')
                    if (not name or name.startswith(('/', '\\')) or
                            any(part in ('.', '..', '') for part in components[:-1]) or
                            '\\' in name or '\x00' in name or name in names):
                        raise RemoteAIError('Attested ZIP contains an unsafe entry')
                    names.add(name)
                    if ((info.external_attr >> 16) & 0o170000) == 0o120000:
                        raise RemoteAIError('Attested ZIP contains a symlink')
                    total += info.file_size
                    if info.file_size > MAX_RESULT_BYTES or total > MAX_RESULT_BYTES:
                        raise RemoteAIError('Attested ZIP exceeds uncompressed size limit')
                bad = archive.testzip()
                if bad:
                    raise RemoteAIError('Attested ZIP contains a corrupted entry')
        except (zipfile.BadZipFile, OSError, RuntimeError, EOFError) as exc:
            raise RemoteAIError('Attested ZIP result is invalid') from exc


def _strict_unique_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Duplicate JSON key')
        result[key] = value
    return result


def cancel_remote_request(base_url: str, token: str, request_id: str, *, timeout_seconds: float = 10) -> dict:
    """Request a durable remote cancellation barrier without resubmitting inference.

    The server may already be executing the model; the response explicitly
    distinguishes a cancellation claim from a physical worker stop.
    """
    from .ai_request_dedup import _KEY
    if not isinstance(request_id, str) or not _KEY.fullmatch(request_id):
        raise ValueError('Invalid remote AI request id')
    if not isinstance(token, str) or not token or len(token) > 4096 or any(ord(c) < 33 or ord(c) > 126 for c in token):
        raise ValueError('A valid remote AI bearer token is required')
    if isinstance(timeout_seconds, bool) or not isinstance(timeout_seconds, (int, float)) or not math.isfinite(timeout_seconds) or timeout_seconds <= 0:
        raise ValueError('Remote AI timeout must be a positive finite number')
    endpoint = _endpoint(base_url, 'whisper').split('/execute-audio/', 1)[0]
    req = Request(endpoint + '/request-cancel/' + request_id,  # noqa: S310 - validated HTTPS endpoint
                  headers={'Authorization': 'Bearer ' + token, 'Accept': 'application/json'},
                  data=b'', method='POST')
    try:
        with https_urlopen(req, timeout=timeout_seconds) as response:
            result = response.read(4097)
        if len(result) > 4096:
            raise RemoteAIError('Remote cancellation response too large')
        data = json.loads(result)
        if (not isinstance(data, dict) or data.get('state') not in
                ('cancelled', 'completed', 'failed') or
                data.get('worker_stop_guaranteed') is not False):
            raise RemoteAIError('Invalid remote cancellation response')
        return data
    except (HTTPError, URLError, TimeoutError, OSError, ValueError) as exc:
        raise RemoteAIError('Remote cancellation not confirmed; do not infer worker stopped') from exc


def list_remote_requests(base_url: str, token: str, *, limit: int = 50,
                         offset: int = 0, state: str | None = None,
                         timeout_seconds: float = 10) -> dict:
    """Discover server-retained requests after a client restart; never infer."""
    from urllib.parse import urlencode
    from .ai_request_dedup import _KEY
    if not isinstance(token, str) or not token or len(token) > 4096 or any(ord(c) < 33 or ord(c) > 126 for c in token):
        raise ValueError('A valid remote AI bearer token is required')
    if type(limit) is not int or not 1 <= limit <= 100 or type(offset) is not int or not 0 <= offset <= 1000000:
        raise ValueError('Invalid remote AI request pagination')
    if state is not None and state not in ('admitted', 'completed', 'failed', 'cancelled'):
        raise ValueError('Invalid remote AI request state filter')
    if isinstance(timeout_seconds, bool) or not isinstance(timeout_seconds, (int, float)) or not math.isfinite(timeout_seconds) or timeout_seconds <= 0:
        raise ValueError('Invalid remote AI timeout')
    endpoint = _endpoint(base_url, 'whisper').split('/execute-audio/', 1)[0]
    query = {'limit': limit, 'offset': offset}
    if state is not None:
        query['state'] = state
    req = Request(endpoint + '/requests?' + urlencode(query),  # noqa: S310 - validated HTTPS endpoint
                  headers={'Authorization': 'Bearer ' + token, 'Accept': 'application/json'}, method='GET')
    try:
        with https_urlopen(req, timeout=timeout_seconds) as response:
            raw = response.read(65537)
    except (HTTPError, URLError, TimeoutError, OSError) as exc:
        raise RemoteAIError('Remote AI request discovery unavailable; inference was not retried') from exc
    if len(raw) > 65536:
        raise RemoteAIError('Oversized remote AI request history')
    try:
        result = json.loads(raw)
    except (ValueError, UnicodeError, TypeError) as exc:
        raise RemoteAIError('Invalid remote AI request history') from exc
    if (not isinstance(result, dict) or type(result.get('total')) is not int or result['total'] < 0
            or result.get('limit') != limit or result.get('offset') != offset
            or not isinstance(result.get('items'), list) or len(result['items']) > limit):
        raise RemoteAIError('Invalid remote AI request history structure')
    for item in result['items']:
        if not isinstance(item, dict) or not isinstance(item.get('request_key'), str) or not _KEY.fullmatch(item['request_key']):
            raise RemoteAIError('Invalid remote AI history request identity')
        if item.get('state') not in ('admitted', 'completed', 'failed', 'cancelled'):
            raise RemoteAIError('Invalid remote AI history state')
        worker = item.get('job_id')
        if (item['state'] == 'completed') != (isinstance(worker, str) and 1 <= len(worker) <= 128):
            raise RemoteAIError('Invalid remote AI history job identity')
        if type(item.get('created_at')) is not int or item['created_at'] <= 0:
            raise RemoteAIError('Invalid remote AI history timestamp')
    return result


def remote_resources(base_url,token,job_id,*,timeout_seconds=10):
    """Owner/token-bound HTTPS ledger counters for display; no local settlement."""
    if not isinstance(job_id,str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,128}',job_id):raise ValueError('Invalid remote job identifier')
    if not isinstance(token,str) or not token or any(ord(c)<33 or ord(c)>126 for c in token):raise ValueError('Invalid remote token')
    endpoint=_endpoint(base_url,'whisper').split('/execute-audio/',1)[0]+'/resources/'+job_id
    request=Request(endpoint,headers={'Authorization':'Bearer '+token,'Accept':'application/json'})  # noqa: S310 - _endpoint enforces HTTPS  # noqa: S310 -- validated HTTPS endpoint
    try:
        with https_urlopen(request,timeout=timeout_seconds) as response:raw=response.read(65537)
        if len(raw)>65536:raise ValueError('Oversized ledger receipt')
        value=json.loads(raw)
        if value.get('job_id')!=job_id or not isinstance(value.get('usage'),dict):raise ValueError('Mismatched ledger receipt')
        usage=value['usage']
        for key in ('cpu_seconds','gpu_seconds'):
            if key in usage and (type(usage[key]) not in (int,float) or not math.isfinite(usage[key]) or usage[key]<0):raise ValueError('Invalid resource counter')
        return value
    except (HTTPError,URLError,TimeoutError,OSError,ValueError,TypeError) as exc:
        raise RemoteAIError('Server resource receipt unavailable; result is retained for recovery') from exc


def studio_capabilities(base_url,token):
    """Read token-scoped Studio asset IDs; never expose or copy credentials."""
    if not isinstance(token,str) or not token or len(token)>4096 or any(ord(c)<33 or ord(c)>126 for c in token):
        raise ValueError('A valid remote AI bearer token is required')
    endpoint=_endpoint(base_url,'vocal-synthesis').split('/execute-audio/')[0]+'/worker-capabilities'
    request=Request(endpoint,headers={'Authorization':'Bearer '+token,'Accept':'application/json'})  # noqa: S310 - _endpoint enforces HTTPS
    try:
        with https_urlopen(request,timeout=15) as response:raw=response.read(2*1024*1024+1)
        if len(raw)>2*1024*1024:raise RemoteAIError('Remote Studio capability response too large')
        result=json.loads(raw)
        if not isinstance(result,dict) or not isinstance(result.get('studio'),dict):raise RemoteAIError('Remote server does not expose Studio asset capabilities; update the server')
        return result['studio']
    except (OSError,ValueError) as exc:
        raise RemoteAIError('Remote Studio capabilities unavailable; no local fallback was selected') from exc
