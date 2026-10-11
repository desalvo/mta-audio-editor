"""Operator-controlled AI worker registry; never accept an executable from an API caller.

Every entry uses the existing --request JSON --output WAV subprocess protocol.
A configured model adapter must be installed independently and marked executable.
"""
from __future__ import annotations

import os
import re
from pathlib import Path

WORKER_KINDS = frozenset({
    'ace-step', 'arranger', 'remix', 'whisper', 'demucs',
    'singer-separation', 'backing-vocals', 'drumsep', 'sam-audio', 'chords-ml',
})


def resolve_worker(kind: str) -> Path | None:
    """Resolve a fixed administrator-configured adapter from a known allowlist."""
    from .ai_worker_protocol import configured_worker
    if not isinstance(kind, str) or kind not in WORKER_KINDS:
        raise ValueError('Unsupported AI worker kind')
    env_name = 'MTA_AI_WORKER_' + re.sub(r'[^A-Z0-9]', '_', kind.upper()) + '_EXECUTABLE'
    value = os.environ.get(env_name, '')
    if not value and kind in {'whisper', 'chords-ml', 'demucs', 'drumsep', 'sam-audio', 'singer-separation', 'backing-vocals'} and os.environ.get('MTA_AI_UNIFIED_WORKERS_ENABLED') == 'true':
        value = str(Path(__file__).with_name('ai_unified_adapter.py').resolve())
    if not value:
        # Backward compatibility for existing ACE-Step installations only.
        return configured_worker() if kind == 'ace-step' else None
    if os.environ.get('MTA_AI_WORKER_ENABLED', '').lower() != 'true':
        return None
    path = Path(value)
    if not path.is_absolute() or path.is_symlink() or not path.is_file() or not os.access(path, os.X_OK):
        return None
    return path


def available_workers() -> dict[str, bool]:
    return {kind: resolve_worker(kind) is not None for kind in sorted(WORKER_KINDS)}
