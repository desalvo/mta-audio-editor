"""Authenticated remote AI request metadata, independent of the worker type.

Remote callers never supply executable paths or local filesystem references.
"""
from __future__ import annotations

import base64
import json
import math

MAX_OPTIONS_BYTES = 8192
FORBIDDEN = frozenset({'source_audio', 'input_path', 'output_path', 'command', 'executable', 'cwd', 'shell'})


MAX_NESTING = 8
MAX_NODES = 512
MAX_COLLECTION = 128
MAX_STRING = 4096


def validate_audio_options(options: dict) -> dict:
    """Bound the entire remote worker option tree before transport or execution.

    Apply exactly the same rules to native submissions and decoded HTTP input.
    """
    if not isinstance(options, dict):
        raise ValueError('AI options must be an object')
    seen = 0

    def visit(item, depth):
        nonlocal seen
        seen += 1
        if seen > MAX_NODES or depth > MAX_NESTING:
            raise ValueError('AI options are too complex')
        if isinstance(item, dict):
            if len(item) > MAX_COLLECTION:
                raise ValueError('Too many AI option keys')
            for key, value in item.items():
                if (not isinstance(key, str) or not 1 <= len(key) <= 80
                        or not key.isprintable() or any(ord(c) < 33 or ord(c) == 127 for c in key)
                        or "\\" in key or key in FORBIDDEN):
                    raise ValueError('Invalid or forbidden AI option key')
                visit(value, depth + 1)
        elif isinstance(item, list):
            if len(item) > MAX_COLLECTION:
                raise ValueError('Too many AI option values')
            for value in item:
                visit(value, depth + 1)
        elif isinstance(item, str):
            if len(item) > MAX_STRING or any(0xD800 <= ord(c) <= 0xDFFF for c in item):
                raise ValueError('Invalid AI option string')
        elif item is None or isinstance(item, (bool, int)):
            pass
        elif isinstance(item, float):
            if not math.isfinite(item):
                raise ValueError('Nonfinite AI option value')
        else:
            raise ValueError('Unsupported AI option value')

    visit(options, 0)
    return options


def _unique_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Duplicate AI option key')
        result[key] = value
    return result


def decode_audio_options(header: str) -> dict:
    """Decode bounded base64url JSON options provided with a streamed WAV body."""
    if not header:
        return {}
    if not isinstance(header, str) or len(header) > 4 * MAX_OPTIONS_BYTES // 3 + 8:
        raise ValueError('AI options header too large')
    try:
        encoded = header.encode('ascii')
        data = base64.b64decode(encoded + b'=' * (-len(encoded) % 4), altchars=b'-_', validate=True)
        if len(data) > MAX_OPTIONS_BYTES:
            raise ValueError('AI options exceed size limit')
        options = json.loads(data.decode('utf-8'), object_pairs_hook=_unique_pairs,
                             parse_constant=lambda _: (_ for _ in ()).throw(ValueError('Nonfinite JSON value')))
    except (UnicodeError, ValueError, TypeError) as exc:
        raise ValueError('Invalid AI options header') from exc
    return validate_audio_options(options)
