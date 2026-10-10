"""Opt-in VST3 factory probe, always executed out-of-process.

This is not a VST3 host and does not process audio or open plugin editors.
"""
from __future__ import annotations

import json
from pathlib import Path
import platform
import subprocess

from app.vst3_host import validate_plugin_path


def resolve_module_binary(bundle: Path) -> Path:
    """Resolve only architecture-appropriate VST3 module binaries."""
    if bundle.is_file():
        return bundle.resolve()
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
    # The probe runs untrusted plugins; reject oversized diagnostics before parsing.
    # subprocess.run still bounds execution time; this bounds JSON processing only.
    if len(result.stdout) > 2_000_000:
        raise RuntimeError('VST3 probe diagnostic output exceeds 2 MB limit')
    payload = json.loads(result.stdout)
    if not isinstance(payload, dict):
        raise RuntimeError('VST3 probe returned a non-object JSON result')
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
    buses = payload.get('buses', []) if lifecycle else []
    if not isinstance(buses, list):
        buses = []
    safe_buses = []
    for bus in buses[:1024]:
        if not isinstance(bus, dict):
            continue
        if bus.get('media') not in ('audio', 'event') or bus.get('direction') not in ('input', 'output'):
            continue
        if any(not isinstance(bus.get(k), int) or isinstance(bus.get(k), bool) for k in ('index', 'channels', 'bus_type')):
            continue
        if not (0 <= bus['index'] <= 255 and 0 <= bus['channels'] <= 1024 and 0 <= bus['bus_type'] <= 16):
            continue
        safe_buses.append({k: bus[k] for k in ('media', 'direction', 'index', 'channels', 'bus_type')})
    return {'name': plugin.stem, 'factory_export': True,
            'instance_requested': instantiate_cid is not None,
            'instance_found': payload.get('instance_found') is True if instantiate_cid is not None else False,
            'instance_created': payload.get('instance_created') is True if instantiate_cid is not None else False,
            'lifecycle_requested': lifecycle,
            'host_context_provided': payload.get('host_context_provided') is True if lifecycle else False,
            'instance_initialized': payload.get('instance_initialized') is True if lifecycle else False,
            'instance_terminated': payload.get('instance_terminated') is True if lifecycle else False,
            'native_host_ready': False,
            'audio_processor_queried': payload.get('audio_processor_queried') is True if instantiate_cid else False,
            'audio_processor_available': payload.get('audio_processor_available') is True if instantiate_cid else False,
            'edit_controller_queried': payload.get('edit_controller_queried') is True if instantiate_cid else False,
            'edit_controller_available': payload.get('edit_controller_available') is True if instantiate_cid else False,
            'sample_size_queried': payload.get('sample_size_queried') is True if lifecycle else False,
            'supports_32_bit': payload.get('supports_32_bit') is True if lifecycle else False,
            'supports_64_bit': payload.get('supports_64_bit') is True if lifecycle else False,
            'latency_samples': (payload['latency_samples'] if lifecycle and
                                type(payload.get('latency_samples')) is int and
                                0 <= payload['latency_samples'] <= 10000000 else None),
            'tail_samples': (payload['tail_samples'] if lifecycle and
                             type(payload.get('tail_samples')) is int and
                             0 <= payload['tail_samples'] <= 10000000 else None),
            'buses': safe_buses, 'binary': str(binary), 'classes': classes,
            **({'factory_classes': payload['factory_classes']}
               if isinstance(payload.get('factory_classes'), int) and not isinstance(payload.get('factory_classes'), bool)
               and 0 <= payload['factory_classes'] <= 10000 else {})}
