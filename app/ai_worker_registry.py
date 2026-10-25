"""Operator-controlled AI worker registry; never accept an executable from an API caller.

Every entry uses the existing --request JSON --output WAV subprocess protocol.
A configured model adapter must be installed independently and marked executable.
"""
from __future__ import annotations

import os
import re
import json
from pathlib import Path

WORKER_KINDS = frozenset({
    'ace-step', 'arranger', 'remix', 'whisper', 'demucs',
    'singer-separation', 'backing-vocals', 'drumsep', 'sam-audio', 'chords-ml', 'markers',
})


def extensions():
    value=os.getenv('MTA_AI_ENGINE_REGISTRY_FILE','')
    if not value:return {}
    path=Path(value)
    if not path.is_absolute() or path.is_symlink() or not path.is_file() or path.stat().st_size>65536:
        raise ValueError('Unsafe AI engine registry')
    document=json.loads(path.read_text())
    if not isinstance(document,list) or len(document)>64:raise ValueError('Invalid engine registry')
    result={}
    for item in document:
        if (not isinstance(item,dict) or set(item)-{'kind','executable','python','gpu_capable','label','metering_method'}
                or not isinstance(item.get('kind'),str) or not re.fullmatch(r'[a-z][a-z0-9-]{0,63}',item['kind'])
                or item['kind'] in WORKER_KINDS or item['kind'] in result):
            raise ValueError('Invalid or duplicate AI engine')
        if any(not isinstance(item.get(k,''),str) or len(item.get(k,''))>4096 for k in ('python','executable','label')):raise ValueError('Invalid registry field')
        if type(item.get('gpu_capable',False)) is not bool:raise ValueError('Invalid GPU capability')
        if item.get('metering_method') not in (None,'gpu-kernel-union-v1') or (item.get('metering_method') and not item.get('gpu_capable')):raise ValueError('Invalid metering provider')
        result[item['kind']]=item
    return result


def registered_kinds():
    from .studio_catalog import KINDS
    return WORKER_KINDS|extensions().keys()|KINDS


def worker_python(kind):
    import sys
    item=extensions().get(kind,{})
    from .studio_catalog import KINDS,python_for
    configured=os.getenv('MTA_AI_WORKER_'+kind.upper().replace('-','_')+'_PYTHON')
    studio_python=python_for(kind) if kind in KINDS and not item.get('python') and not configured else None
    value=item.get('python') or configured or studio_python or os.getenv('MTA_AI_DEFAULT_PYTHON') or sys.executable
    path=Path(value)
    if not path.is_absolute() or not path.is_file() or not os.access(path,os.X_OK):raise ValueError('Invalid operator-selected AI Python')
    return str(path)


def resolve_worker(kind: str) -> Path | None:
    """Resolve a fixed administrator-configured adapter from a known allowlist."""
    from .ai_worker_protocol import configured_worker
    extra=extensions()
    from .studio_catalog import KINDS,available
    if not isinstance(kind, str) or kind not in WORKER_KINDS|extra.keys()|KINDS:
        raise ValueError('Unsupported AI worker kind')
    env_name = 'MTA_AI_WORKER_' + re.sub(r'[^A-Z0-9]', '_', kind.upper()) + '_EXECUTABLE'
    value = os.environ.get(env_name, '') or extra.get(kind,{}).get('executable','')
    if not value and kind in {'whisper', 'chords-ml', 'demucs', 'drumsep', 'sam-audio', 'singer-separation', 'backing-vocals','markers'} and os.environ.get('MTA_AI_UNIFIED_WORKERS_ENABLED') == 'true':
        value = str(Path(__file__).with_name('ai_unified_adapter.py').resolve())
    if not value and kind in KINDS and available(kind):
        value=str(Path(__file__).with_name('ai_studio_adapter.py').resolve())
    if not value:
        # Backward compatibility for existing ACE-Step installations only.
        return configured_worker() if kind == 'ace-step' else None
    native_studio=kind in KINDS and os.getenv('MTA_NATIVE_SINGLE_USER','').lower()=='true'
    if os.environ.get('MTA_AI_WORKER_ENABLED', '').lower() != 'true' and not native_studio:
        return None
    path = Path(value)
    # Frozen bundles may extract data .py files without Unix execute bits.
    # Only our fixed internal Studio adapter is launched through the validated
    # Python interpreter; external configured executables keep the X_OK check.
    internal_studio=kind in KINDS and path==Path(__file__).with_name('ai_studio_adapter.py').resolve()
    if not path.is_absolute() or path.is_symlink() or not path.is_file() or (not internal_studio and not os.access(path, os.X_OK)):
        return None
    return path


def available_workers() -> dict[str, bool]:
    from . import ai_pull_coordinator as pull
    if pull.mode() == 'pull':
        return pull.available()
    return {kind: resolve_worker(kind) is not None for kind in sorted(registered_kinds())}


def execution_available(kind):
    """Actual authority execution capability; resolve_worker stays node-local."""
    from . import ai_pull_coordinator as pull
    if kind not in registered_kinds():
        raise ValueError('Unsupported AI worker kind')
    return pull.available().get(kind, False) if pull.mode() == 'pull' else resolve_worker(kind) is not None
