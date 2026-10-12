"""Optional, read-only Proxmox GPU telemetry over an explicit UNIX socket.

No host agent is required for agentless GPU slot accounting. Telemetry is
never accepted as per-job certified GPU time or energy.
"""
from __future__ import annotations
import json
import os
import socket
import time


def snapshot(*, socket_path: str | None = None, token: str | None = None) -> dict:
    path = socket_path if socket_path is not None else os.getenv('MTA_AI_GPU_HOST_AGENT_SOCKET', '')
    token = token if token is not None else os.getenv('MTA_AI_GPU_HOST_AGENT_TOKEN', '')
    if not path:
        candidate = '/run/mta-gpu-agent/agent.sock'
        path = candidate if os.path.exists(candidate) else ''
    if not path:
        return {'available': False, 'reason': 'not-configured', 'billing_eligible': False}
    if not token:
        try:
            token = open('/run/mta-gpu-agent/token', encoding='utf-8').read().strip()
        except OSError:
            pass
    if not token or len(token) < 24:
        return {'available': False, 'reason': 'agent-token-not-configured', 'billing_eligible': False}
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as conn:
            conn.settimeout(3)
            conn.connect(path)
            conn.sendall((json.dumps({'token': token}) + '\n').encode())
            data = b''
            while b'\n' not in data and len(data) < 262144:
                chunk = conn.recv(65536)
                if not chunk:
                    break
                data += chunk
        if len(data) >= 262144:
            raise ValueError('oversized response')
        payload = json.loads(data.split(b'\n', 1)[0])
        if not isinstance(payload, dict) or payload.get('schema') != 'mta-gpu-host-agent-v1':
            raise ValueError('bad schema')
        # A valid schema alone is insufficient: reject replayed snapshots and
        # suspicious host process records; never infer container PID identity.
        stamp = payload.get('timestamp')
        if isinstance(stamp, bool) or not isinstance(stamp, int) or abs(int(time.time()) - stamp) > 30:
            raise ValueError('stale or invalid agent timestamp')
        processes = payload.get('processes')
        if not isinstance(processes, list) or len(processes) > 1024:
            raise ValueError('invalid process list')
        seen = set()
        for entry in processes:
            if not isinstance(entry, dict):
                raise ValueError('invalid process record')
            pid, gpu, group = (entry.get('host_pid'), entry.get('gpu'),
                               entry.get('host_cgroup'))
            if isinstance(pid, bool) or not isinstance(pid, int) or pid <= 0:
                raise ValueError('invalid host PID')
            if isinstance(gpu, bool) or not isinstance(gpu, int) or gpu < 0 or gpu > 255:
                raise ValueError('invalid GPU ID')
            if group is not None and (not isinstance(group, str) or len(group) > 8192):
                raise ValueError('invalid cgroup')
            if (gpu, pid) in seen:
                raise ValueError('duplicate process record')
            seen.add((gpu, pid))
        if payload.get('billing_eligible') is not False:
            raise ValueError('agent must not authorize billing')
        return {'available': True, 'billing_eligible': False, 'telemetry': payload}
    except (OSError, ValueError, UnicodeError) as exc:
        return {'available': False, 'reason': type(exc).__name__, 'billing_eligible': False}
