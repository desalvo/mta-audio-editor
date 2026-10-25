#!/usr/bin/env python3
"""Read-only LXC-side transport, identity and billing-boundary diagnostics.

No token, raw host cgroup, or process identifiers are printed by default.
This is not a GPU time, energy, job-attribution or billing measurement.
"""
from __future__ import annotations

import argparse
import json
import os
import socket
import sys
import time
from pathlib import Path


def probe(*, directory: str = '/opt/mta-gpu-agent-host') -> dict:
    base = Path(directory)
    socket_file = base / 'agent.sock'
    token_file = base / 'token'
    report = {
        'schema': 'mta-gpu-lxc-diagnostic-v1',
        'uid': os.geteuid(),
        'socket_present': socket_file.is_socket(),
        'socket_connectable': False,
        'token_readable': False,
        'authenticated': False,
        'process_count': None,
        'gpu_ids': [],
        'job_attribution_verified': False,
        'billable_gpu_time_verified': False,
        'billing_eligible': False,
    }
    try:
        token = token_file.read_text(encoding='utf-8').strip()
        report['token_readable'] = True
        if len(token) < 24:
            report['reason'] = 'invalid-token-length'
            return report
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as conn:
            conn.settimeout(4)
            conn.connect(str(socket_file))
            report['socket_connectable'] = True
            conn.sendall((json.dumps({'token': token}) + '\n').encode('utf-8'))
            buffer = b''
            while b'\n' not in buffer and len(buffer) < 262144:
                part = conn.recv(32768)
                if not part:
                    break
                buffer += part
        if len(buffer) >= 262144:
            raise ValueError('oversized-response')
        result = json.loads(buffer.split(b'\n', 1)[0])
        if not isinstance(result, dict) or result.get('schema') != 'mta-gpu-host-agent-v1':
            raise ValueError('invalid-agent-schema')
        stamp = result.get('timestamp')
        if type(stamp) is not int or abs(time.time() - stamp) > 30:
            raise ValueError('invalid-or-stale-timestamp')
        processes = result.get('processes')
        if not isinstance(processes, list) or len(processes) > 1024:
            raise ValueError('invalid-process-list')
        if result.get('source') != 'host-amd-smi' or result.get('billing_eligible') is not False:
            raise ValueError('invalid-telemetry-trust-boundary')
        gpu_ids = set()
        for item in processes:
            if not isinstance(item, dict) or type(item.get('gpu')) is not int or type(item.get('host_pid')) is not int or item['host_pid'] <= 0:
                raise ValueError('invalid-process-record')
            gpu_ids.add(item['gpu'])
        report.update(authenticated=True, process_count=len(processes), gpu_ids=sorted(gpu_ids), reason='ok')
    except (OSError, ValueError, UnicodeError, json.JSONDecodeError) as exc:
        report['reason'] = type(exc).__name__ if not isinstance(exc, ValueError) else str(exc)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', default=os.environ.get('MTA_AI_GPU_HOST_AGENT_DIR', '/opt/mta-gpu-agent-host'))
    args = parser.parse_args()
    outcome = probe(directory=args.directory)
    print(json.dumps(outcome, indent=2))
    return 0 if outcome['authenticated'] else 1


if __name__ == '__main__':
    sys.exit(main())
