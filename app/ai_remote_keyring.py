"""Operator-provisioned rotating HMAC keys for remote CPU metering.

No keys are exposed by diagnostics; configuration failures always fail closed.
The environment contains a JSON object mapping a key ID to a 64+-character
lowercase hex string; changing the active mapping revokes removed IDs.
"""
from __future__ import annotations

import json
import os
import re

_ID = re.compile(r'[A-Za-z0-9_-]{1,64}\Z')
_HEX = re.compile(r'[0-9a-f]{64,256}\Z')
_ENV = 'MTA_AI_REMOTE_METERING_KEYS_JSON'


def decode_keyring(raw: str) -> dict[str, bytes]:
    if not isinstance(raw, str) or not raw or len(raw) > 32768:
        raise ValueError('Missing or oversized remote metering keyring')

    def pairs_unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError('Duplicate remote metering key ID')
            result[key] = value
        return result

    try:
        keys = json.loads(raw, object_pairs_hook=pairs_unique)
    except (ValueError, UnicodeError, TypeError) as exc:
        raise ValueError('Invalid remote metering keyring JSON') from exc
    if not isinstance(keys, dict) or not 1 <= len(keys) <= 32:
        raise ValueError('Remote metering keyring requires 1 to 32 keys')
    decoded = {}
    seen_material = set()
    for key_id, material in keys.items():
        if not isinstance(key_id, str) or not _ID.fullmatch(key_id):
            raise ValueError('Invalid remote metering key ID')
        if not isinstance(material, str) or not _HEX.fullmatch(material) or len(material) % 2:
            raise ValueError('Remote metering keys must be strong lowercase hexadecimal')
        secret = bytes.fromhex(material)
        if secret in seen_material:
            raise ValueError('Duplicate remote metering secret')
        decoded[key_id] = secret
        seen_material.add(secret)
    return decoded


def active_keyring() -> dict[str, bytes]:
    """Load on each verification so revoked IDs do not survive in a cache."""
    return decode_keyring(os.environ.get(_ENV, ''))


def public_status() -> dict:
    """No key IDs or material in administrator diagnostics."""
    try:
        count = len(active_keyring())
    except ValueError:
        return {'configured': False, 'status': 'unavailable'}
    return {'configured': True, 'status': 'ready', 'active_key_count': count}
