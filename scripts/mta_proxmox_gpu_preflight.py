#!/usr/bin/env python3
"""Read-only AMD GPU telemetry readiness check for Proxmox Debian hosts.

Exit status 0: GPU detected and JSON usable; 1: unavailable/unsupported.
Designed for systemd ExecCondition (skip instead of restart loop).
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys


def probe(run=subprocess.run):
    try:
        detected = run(['amd-smi', 'list'], capture_output=True, text=True,
                       check=True, timeout=8)
    except (OSError, subprocess.SubprocessError) as exc:
        return False, f'AMD SMI GPU discovery unavailable: {exc}'
    if not re.search(r'^\s*GPU:\s*\d+\s*$', detected.stdout, flags=re.MULTILINE):
        return False, 'No AMD GPU reported by amd-smi list'
    try:
        result = run(['amd-smi', 'process', '--json'], capture_output=True,
                     text=True, check=True, timeout=8)
        payload = json.loads(result.stdout)
    except (OSError, subprocess.SubprocessError, ValueError) as exc:
        return False, f'AMD SMI process JSON unavailable: {exc}'
    if not isinstance(payload, list) or len(payload) > 1024:
        return False, 'AMD SMI returned invalid process JSON: expected bounded list'
    for device in payload:
        if not isinstance(device, dict):
            return False, 'AMD SMI returned invalid process JSON object'
        gpu = device.get('gpu')
        if isinstance(gpu, bool) or not isinstance(gpu, int) or not 0 <= gpu <= 255:
            return False, 'AMD SMI returned invalid GPU identifier'
        info = device.get('process_info')
        # AMD SMI 24.x reports an idle device using a literal status string.
        # Only this explicit idle sentinel is accepted; other strings fail closed.
        if info == 'No running processes detected':
            continue
        records = [device] if 'process_info' in device else device.get('process_list', [])
        if not isinstance(records, list) or len(records) > 1024:
            return False, 'AMD SMI returned invalid process list'
        for rec in records:
            if not isinstance(rec, dict) or not isinstance(rec.get('process_info'), dict):
                return False, 'AMD SMI returned malformed process record'
            pid = rec['process_info'].get('pid')
            if type(pid) is not int or pid <= 0:
                return False, 'AMD SMI returned invalid process PID'
    return True, 'AMD GPU present and amd-smi process --json supported'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--quiet', action='store_true')
    args = parser.parse_args()
    ready, message = probe()
    if not args.quiet:
        print(f'MTA GPU telemetry: {message}', file=sys.stdout if ready else sys.stderr)
    return 0 if ready else 1


if __name__ == '__main__':
    sys.exit(main())
