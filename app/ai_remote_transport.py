"""Authenticated remote AI request metadata, independent of the worker type.

Remote callers never supply executable paths or local filesystem references.
"""
from __future__ import annotations

import base64
import json

MAX_OPTIONS_BYTES = 8192
FORBIDDEN = frozenset({'source_audio', 'input_path', 'output_path', 'command', 'executable', 'cwd', 'shell'})


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
        options = json.loads(data.decode('utf-8'))
    except (UnicodeError, ValueError, TypeError) as exc:
        raise ValueError('Invalid AI options header') from exc
    if not isinstance(options, dict):
        raise ValueError('AI options must be an object')
    if any(key in options for key in FORBIDDEN):
        raise ValueError('Filesystem and executable options are forbidden')
    if not all(isinstance(key, str) and len(key) <= 80 for key in options):
        raise ValueError('Invalid AI option key')
    return options
