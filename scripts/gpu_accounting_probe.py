#!/usr/bin/env python3
"""Non-invasive GPU accounting capability probe. No credentials or project files read.

Run alongside a real AI job: python scripts/gpu_accounting_probe.py --duration 60
Results are diagnostics ONLY; sampled counters are not suitable for invoicing.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time

PROC = Path('/proc')
ENGINE = re.compile(r'^drm-engine-([\w-]+):\s*(\d+)\s*ns\s*$')
MEMORY = re.compile(r'^drm-(memory|resident)-([\w-]+):\s*(\d+)\s*(?:KiB|kB)\s*$')

def cmd_out(args):
    if not shutil.which(args[0]):
        return {'available': False}
    try:
        proc = subprocess.run(args, capture_output=True, text=True, timeout=8, check=False)
        return {'available': True, 'exit_code': proc.returncode, 'output': proc.stdout[:2500], 'error': proc.stderr[:500]}
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {'available': True, 'error': type(exc).__name__}

def drm_sample(pid):
    clients = {}
    directory = PROC / str(pid) / 'fdinfo'
    try:
        entries = list(directory.iterdir())
    except (FileNotFoundError, PermissionError):
        return None
    for entry in entries:
        try:
            rows = entry.read_text().splitlines()
        except (OSError, UnicodeError):
            continue
        fields = dict(row.split(':', 1) for row in rows if ':' in row)
        driver = fields.get('drm-driver', '').strip()
        client = fields.get('drm-client-id', '').strip()
        if not driver or not client:
            continue
        key = (driver, client)
        metrics = clients.setdefault(key, {})
        for row in rows:
            row = row.strip()
            engine = ENGINE.fullmatch(row)
            memory = MEMORY.fullmatch(row)
            if engine:
                label, count = 'engine_' + engine.group(1), int(engine.group(2))
            elif memory:
                label, count = memory.group(1) + '_' + memory.group(2), int(memory.group(3))
            else:
                continue
            metrics[label] = max(metrics.get(label, 0), count)
    return {'clients': len(clients), 'drivers': sorted({key[0] for key in clients}),
            'metrics': {k: sum(item.get(k, 0) for item in clients.values())
                        for k in sorted({name for item in clients.values() for name in item})}}

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--duration', type=int, default=30, help='Seconds to watch; launch an AI job separately during this period')
    parser.add_argument('--interval', type=float, default=0.5, help='Polling interval in seconds (>= 0.1)')
    parser.add_argument('--output', default='gpu-accounting-probe.json', help='Output JSON filename')
    args = parser.parse_args()
    if not sys.platform.startswith('linux'):
        parser.error('Linux only')
    if not 1 <= args.duration <= 900 or args.interval < 0.1:
        parser.error('duration must be 1..900 and interval >= 0.1')
    result = {'schema': 1, 'warning': 'Diagnostic, not complete process-lifetime billing telemetry',
              'python': sys.version.split()[0],
              'cgroup_v2': Path('/sys/fs/cgroup/cgroup.controllers').exists(),
              'drm_devices': sorted(p.name for p in Path('/dev/dri').glob('renderD*')),
              'amd_kfd': Path('/dev/kfd').exists(),
              'nvidia_smi': cmd_out(['nvidia-smi', '--query-gpu=name,driver_version', '--format=csv,noheader']),
              'rocm_smi': cmd_out(['rocm-smi', '--showdriverversion']),
              'observed': {}, 'processes_observed': 0, 'samples': 0, 'access_denied': 0}
    end = time.monotonic() + args.duration
    while time.monotonic() < end:
        result['samples'] += 1
        for entry in PROC.iterdir():
            if not entry.name.isdecimal():
                continue
            pid = int(entry.name)
            sample = drm_sample(pid)
            if sample is None:
                continue
            if not sample['clients']:
                continue
            # No command lines, environment, usernames, file paths, or tokens collected.
            key = str(pid)
            old = result['observed'].setdefault(key, {'drivers': sample['drivers'], 'clients_max': 0,
                                                     'first_sample': result['samples'], 'last_sample': 0,
                                                     'metrics_last': {}, 'metrics_max': {}})
            old['last_sample'] = result['samples']
            old['clients_max'] = max(old['clients_max'], sample['clients'])
            old['metrics_last'] = sample['metrics']
            for name, value in sample['metrics'].items():
                old['metrics_max'][name] = max(old['metrics_max'].get(name, 0), value)
        time.sleep(args.interval)
    result['processes_observed'] = len(result['observed'])
    out = Path(args.output)
    out.write_text(json.dumps(result, indent=2, sort_keys=True) + '\n')
    print(f'GPU capability report: {out} | observed processes: {result["processes_observed"]}')
    print('Review report before sharing. This is sampled diagnostic information, not billable GPU time.')

if __name__ == '__main__':
    main()
