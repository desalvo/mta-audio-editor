"""Authenticated final CPU usage envelopes for remote AI workers.

This provides a protocol primitive, not GPU invoice certification: possession
of a shared key authenticates a worker's assertion but cannot attest hardware
measurement provenance. GPU quantities are deliberately forbidden.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import math
import re

_VERSION = 1
_HEX = re.compile(r'[0-9a-f]{64}\Z')
_ID = re.compile(r'[a-zA-Z0-9_-]{1,128}\Z')
_ALLOWED = frozenset({'cpu_seconds', 'read_bytes', 'write_bytes'})
_KEY_ID = re.compile(r'[A-Za-z0-9_-]{1,64}\Z')


def _canonical(document: dict) -> bytes:
    return json.dumps(document, sort_keys=True, separators=(',', ':'), ensure_ascii=True,
                      allow_nan=False).encode('ascii')


def _secret(key: bytes) -> bytes:
    if not isinstance(key, bytes) or len(key) < 32:
        raise ValueError('Worker attestation key must contain at least 32 bytes')
    return key


def _payload(job_id: str, request_id: str, worker_id: str, usage: dict) -> dict:
    for name, value in (('job_id', job_id), ('request_id', request_id), ('worker_id', worker_id)):
        if not isinstance(value, str) or not _ID.fullmatch(value):
            raise ValueError('Invalid remote metering ' + name)
    if not isinstance(usage, dict) or not usage or set(usage) - _ALLOWED:
        raise ValueError('Remote metering requires supported CPU/IO counters')
    clean = {}
    for name, value in usage.items():
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError('Invalid remote usage counter')
        if not math.isfinite(value) or value < 0 or value > 1e15:
            raise ValueError('Out-of-range remote usage counter')
        if name.endswith('_bytes') and (not isinstance(value, int) or value > (1 << 53)):
            raise ValueError('IO byte counters must be exact integers')
        clean[name] = value
    if 'cpu_seconds' not in clean:
        raise ValueError('Remote CPU measurement is required')
    return {'schema_version': _VERSION, 'job_id': job_id, 'request_id': request_id,
            'worker_id': worker_id, 'usage': clean}


def sign(key: bytes, *, job_id: str, request_id: str, worker_id: str, usage: dict) -> dict:
    """Worker side: sign measured counters bound to one durable request."""
    body = _payload(job_id, request_id, worker_id, usage)
    signature = hmac.new(_secret(key), _canonical(body), hashlib.sha256).hexdigest()
    return {**body, 'signature': signature}


def verify(key: bytes, envelope: dict, *, job_id: str, request_id: str,
           worker_id: str) -> dict:
    """Server side: fail closed on replay, ambiguities and unknown counters."""
    _secret(key)
    if not isinstance(envelope, dict) or set(envelope) != {
        'schema_version', 'job_id', 'request_id', 'worker_id', 'usage', 'signature'
    } or type(envelope.get('schema_version')) is not int or envelope['schema_version'] != _VERSION:
        raise ValueError('Invalid remote metering envelope schema')
    if (envelope['job_id'], envelope['request_id'], envelope['worker_id']) != (job_id, request_id, worker_id):
        raise ValueError('Remote metering identity mismatch')
    body = _payload(job_id, request_id, worker_id, envelope['usage'])
    signature = envelope['signature']
    if not isinstance(signature, str) or not _HEX.fullmatch(signature):
        raise ValueError('Invalid remote metering signature')
    expected = hmac.new(key, _canonical(body), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(signature, expected):
        raise ValueError('Remote metering authentication failed')
    return dict(body['usage'])


# Rotation-aware envelopes bind a key ID into the signed payload. The original
# v1 protocol stays available for already-deployed workers, but must be opted
# into explicitly by the server using verify().
def sign_rotating(key: bytes, *, key_id: str, job_id: str,
                  request_id: str, worker_id: str, usage: dict) -> dict:
    if not isinstance(key_id, str) or not _KEY_ID.fullmatch(key_id):
        raise ValueError('Invalid metering signing key ID')
    body = _payload(job_id, request_id, worker_id, usage)
    body['key_id'] = key_id
    body['schema_version'] = 2
    signature = hmac.new(_secret(key), _canonical(body), hashlib.sha256).hexdigest()
    return {**body, 'signature': signature}


def verify_rotating(keyring: dict, envelope: dict, *, job_id: str,
                    request_id: str, worker_id: str) -> dict:
    """Authenticate a v2 envelope with an explicit, provisioned key ID.

    Never try every key or fall back to a default: key rotation is explicit.
    This API authenticates a worker assertion, not GPU hardware provenance.
    """
    if not isinstance(envelope, dict) or set(envelope) != {
        'schema_version', 'key_id', 'job_id', 'request_id', 'worker_id', 'usage', 'signature'
    } or type(envelope.get('schema_version')) is not int or envelope['schema_version'] != 2:
        raise ValueError('Invalid rotating metering envelope schema')
    key_id = envelope['key_id']
    if not isinstance(key_id, str) or not _KEY_ID.fullmatch(key_id):
        raise ValueError('Invalid metering signing key ID')
    if not isinstance(keyring, dict) or key_id not in keyring:
        raise ValueError('Unknown or revoked metering signing key')
    key = _secret(keyring[key_id])
    if (envelope['job_id'], envelope['request_id'], envelope['worker_id']) != (job_id, request_id, worker_id):
        raise ValueError('Remote metering identity mismatch')
    body = _payload(job_id, request_id, worker_id, envelope['usage'])
    body['key_id'] = key_id
    body['schema_version'] = 2
    signature = envelope['signature']
    if not isinstance(signature, str) or not _HEX.fullmatch(signature):
        raise ValueError('Invalid remote metering signature')
    expected = hmac.new(key, _canonical(body), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(signature, expected):
        raise ValueError('Remote metering authentication failed')
    return dict(body['usage'])
