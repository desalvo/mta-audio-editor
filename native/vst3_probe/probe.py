"""Opt-in VST3 factory probe, always executed out-of-process.

This is not a VST3 host and does not process audio or open plugin editors.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import platform
import subprocess

from app.vst3_host import validate_plugin_path


def resolve_module_binary(bundle: Path) -> Path:
    """Resolve only architecture-appropriate VST3 module binaries."""
    if bundle.is_file():
        return bundle
    system = platform.system()
    arch = platform.machine().lower()
    if system == 'Darwin':
        candidates = [bundle / 'Contents/MacOS' / bundle.stem]
    elif system == 'Windows':
        machine = 'arm64-win' if arch in ('arm64', 'aarch64') else 'x86_64-win'
        candidates = list((bundle / 'Contents' / machine).glob('*.vst3'))
    else:
        machine = 'aarch64-linux' if arch in ('arm64', 'aarch64') else 'x86_64-linux'
        candidates = list((bundle / 'Contents' / machine).glob('*.so'))
    for candidate in candidates:
        if candidate.is_file() and candidate.resolve().is_relative_to(bundle.resolve()):
            return candidate.resolve()
    raise FileNotFoundError(f'No VST3 binary matching {system} {arch}: {bundle.name}')


def probe_plugin(path: str, executable: str, timeout: float = 5,
                 instantiate_cid: str | None = None,
                 lifecycle: bool = False) -> dict:
    if lifecycle and instantiate_cid is None:
        raise ValueError('Lifecycle diagnostic requires an explicit class CID')
    plugin = validate_plugin_path(path)
    binary = resolve_module_binary(plugin)
    probe = Path(executable).resolve()
    if not probe.is_file():
        raise FileNotFoundError(f'VST3 probe executable not found: {probe}')
    if lifecycle and instantiate_cid is None:
        raise ValueError('Lifecycle diagnostic requires an explicit class CID')
    if instantiate_cid is not None:
        if not isinstance(instantiate_cid, str) or len(instantiate_cid) != 32 or any(
            char not in '0123456789abcdefABCDEF' for char in instantiate_cid
        ):
            raise ValueError('Expected a 32-character hexadecimal VST3 class CID')
    command = [str(probe), str(binary)]
    if instantiate_cid is not None:
        command.extend(['--lifecycle' if lifecycle else '--instantiate', instantiate_cid.lower()])
    result = subprocess.run(command, text=True, capture_output=True,
                            timeout=min(max(float(timeout), 0.5), 15), check=False)
    if result.returncode:
        raise RuntimeError(f'VST3 probe failed ({result.returncode}): {result.stderr.strip()[:300]}')
    payload = json.loads(result.stdout)
    if payload.get('factory_export') is not True:
        raise RuntimeError('VST3 factory export missing')
    classes = payload.get('classes', [])
    if not isinstance(classes, list):
        classes = []
    classes = [
        {'cid': entry['cid'], 'name': entry['name'], 'category': entry['category']}
        for entry in classes[:10000]
        if isinstance(entry, dict)
        and isinstance(entry.get('cid'), str) and len(entry['cid']) == 32
        and all(c in '0123456789abcdefABCDEF' for c in entry['cid'])
        and isinstance(entry.get('name'), str) and len(entry['name']) <= 512
        and isinstance(entry.get('category'), str) and len(entry['category']) <= 256
    ]
    # One unique class per CID; reject control characters from untrusted factories.
    seen = set()
    safe_classes = []
    for entry in classes:
        cid = entry['cid'].lower()
        if cid in seen or any(ord(c) < 32 or ord(c) == 127 for c in entry['name'] + entry['category']):
            continue
        seen.add(cid)
        safe_classes.append({**entry, 'cid': cid})
    classes = safe_classes
    return {'name': plugin.stem, 'factory_export': True,
            'instance_requested': instantiate_cid is not None,
            'instance_found': payload.get('instance_found') is True if instantiate_cid is not None else False,
            'instance_created': payload.get('instance_created') is True if instantiate_cid is not None else False,
            'lifecycle_requested': lifecycle,
            'instance_initialized': payload.get('instance_initialized') is True if lifecycle else False,
            'instance_terminated': payload.get('instance_terminated') is True if lifecycle else False,
            'native_host_ready': False, 'binary': str(binary), 'classes': classes,
            **({'factory_classes': payload['factory_classes']}
               if isinstance(payload.get('factory_classes'), int) and not isinstance(payload.get('factory_classes'), bool)
               and 0 <= payload['factory_classes'] <= 10000 else {})}
