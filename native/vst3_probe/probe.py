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


def probe_plugin(path: str, executable: str, timeout: float = 5) -> dict:
    plugin = validate_plugin_path(path)
    binary = resolve_module_binary(plugin)
    probe = Path(executable).resolve()
    if not probe.is_file():
        raise FileNotFoundError(f'VST3 probe executable not found: {probe}')
    result = subprocess.run([str(probe), str(binary)], text=True, capture_output=True,
                            timeout=min(max(float(timeout), 0.5), 15), check=False)
    if result.returncode:
        raise RuntimeError(f'VST3 probe failed ({result.returncode}): {result.stderr.strip()[:300]}')
    payload = json.loads(result.stdout)
    if payload.get('factory_export') is not True:
        raise RuntimeError('VST3 factory export missing')
    return {'name': plugin.stem, 'factory_export': True,
            'native_host_ready': False, 'binary': str(binary)}
