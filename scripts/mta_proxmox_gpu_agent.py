#!/usr/bin/env python3
"""Optional rootless host-side AMD SMI agent. UNIX socket only, no TCP.

Run on a Proxmox host (not inside LXC). Mount the socket into the LXC if desired.
No GPU billing authorization, commands or user-supplied PID/cgroup paths.
"""
from __future__ import annotations
import argparse
import hmac
import json
import re
import os
import pathlib
import socket
import stat
import subprocess
import time

MAX_BYTES = 4096



def _process_details(pid, *, proc_root=pathlib.Path('/proc')):
    """Host-observed namespace identity and optional per-process DRM counters."""
    root = proc_root / str(pid)
    try:
        before = root.joinpath('stat').read_text().rsplit(')', 1)[1].split()[19]
        status = root.joinpath('status').read_text().splitlines()
        ns = next(line.split(':', 1)[1].split() for line in status if line.startswith('NSpid:'))
        inode = root.joinpath('ns/pid').stat().st_ino
        details = {'namespace_pid': int(ns[-1]), 'pid_namespace_inode': inode,
                   'process_start_ticks': before}
        # Distinct DRM clients; duplicate file descriptors must not double count.
        clients = {}
        try:
            for fd in root.joinpath('fdinfo').iterdir():
                try: lines = fd.read_text().splitlines()
                except OSError: continue
                props = dict(line.split(':', 1) for line in lines if ':' in line)
                client = props.get('drm-client-id', '').strip()
                driver = props.get('drm-driver', '').strip()
                device = props.get('drm-pdev', '').strip()
                if not client or not driver: continue
                counts = clients.setdefault((driver, device, client), {})
                for line in lines:
                    match = re.fullmatch(r'drm-engine-([a-zA-Z0-9_-]+):\s*(\d+)\s*ns\s*', line)
                    if match:
                        name, count = match[1], int(match[2])
                        counts[name] = max(counts.get(name, 0), count)
            if any(clients.values()):
                details['drm_engine_ns'] = sum(sum(c.values()) for c in clients.values())
        except OSError:
            pass
        after = root.joinpath('stat').read_text().rsplit(')', 1)[1].split()[19]
        return details if before == after else {}
    except (OSError, ValueError, IndexError, StopIteration):
        return {}


def _gfx_counter(info):
    value = info.get('usage', info.get('USAGE', {}))
    if not isinstance(value, dict): return None
    value = value.get('gfx', value.get('GFX'))
    if isinstance(value, dict):
        if value.get('unit') != 'ns': return None
        value = value.get('value')
    if type(value) is int and value >= 0: return value
    return None


def read_snapshot():
    result = subprocess.run(['amd-smi', 'process', '--json'],
                            capture_output=True, text=True, check=True, timeout=8)
    payload = json.loads(result.stdout)
    if not isinstance(payload, list) or len(payload) > 1024:
        raise ValueError('invalid AMD SMI snapshot')
    processes = []
    for device in payload:
        if not isinstance(device, dict):
            raise ValueError('invalid device')
        gpu = device.get('gpu')
        if isinstance(gpu, bool) or not isinstance(gpu, int) or not 0 <= gpu <= 255:
            raise ValueError('invalid GPU ID')
        # AMD SMI 24.5.2 emits one object per process with top-level
        # process_info; newer versions may emit a process_list per GPU.
        if device.get('process_info') == 'No running processes detected':
            process_list = []
        elif 'process_info' in device:
            process_list = [device]
        else:
            process_list = device.get('process_list', [])
        if not isinstance(process_list, list) or len(process_list) > 1024:
            raise ValueError('invalid process list')
        for p in process_list:
            if not isinstance(p, dict) or not isinstance(p.get('process_info'), dict):
                raise ValueError('invalid process record')
            pid = p.get('process_info', {}).get('pid')
            if not isinstance(pid, int) or isinstance(pid, bool) or pid <= 0:
                raise ValueError('invalid PID')
            try:
                cgroup = pathlib.Path('/proc', str(pid), 'cgroup').read_text()[:8192]
            except OSError:
                cgroup = None
            if any(rec['host_pid'] == pid and rec['gpu'] == gpu for rec in processes):
                raise ValueError('duplicate GPU process')
            record = {'host_pid': pid, 'gpu': gpu, 'host_cgroup': cgroup}
            record.update(_process_details(pid))
            counter = _gfx_counter(p['process_info'])
            if counter is not None: record['gfx_ns'] = counter
            processes.append(record)
    if len(processes) > 1024:
        raise ValueError('too many processes')
    return {'schema': 'mta-gpu-host-agent-v1', 'timestamp': int(time.time()),
            'processes': processes, 'source': 'host-amd-smi',
            'billing_eligible': False, 'capabilities': ['namespace-process-counters-v1']}


def serve(path: str, token: str):
    if len(token) < 24:
        raise ValueError('A random authentication token of at least 24 characters is required')
    target = pathlib.Path(path)
    if target.is_symlink():
        raise ValueError('Refusing symlink socket path')
    if target.exists():
        if not stat.S_ISSOCK(target.stat().st_mode):
            raise ValueError('Refusing to overwrite non-socket path')
        probe = socket.socket(socket.AF_UNIX)
        try:
            probe.settimeout(0.5)
            probe.connect(str(target))
        except ConnectionRefusedError:
            target.unlink()  # stale UNIX socket after host/service reboot
        else:
            raise ValueError('Another agent owns the socket')
        finally:
            probe.close()
    target.parent.mkdir(parents=True, exist_ok=True)
    with socket.socket(socket.AF_UNIX) as server:
        server.bind(path)
        os.chmod(path, 0o660)
        server.listen(8)
        try:
            while True:
                conn, _ = server.accept()
                with conn:
                    conn.settimeout(4)
                    try:
                        request = conn.recv(MAX_BYTES + 1)
                        if len(request) > MAX_BYTES:
                            continue
                        body = json.loads(request.split(b'\n', 1)[0])
                        if not isinstance(body, dict) or not isinstance(body.get('token'), str):
                            continue
                        if not hmac.compare_digest(body['token'], token):
                            continue
                        reply = read_snapshot()
                        conn.sendall((json.dumps(reply, separators=(',', ':')) + '\n').encode())
                    except (ValueError, OSError, subprocess.SubprocessError, KeyError):
                        continue
        finally:
            target.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--socket', default='/run/mta-gpu-agent/agent.sock')
    args = parser.parse_args()
    token = os.environ.get('MTA_GPU_AGENT_TOKEN', '') or pathlib.Path('/etc/mta-gpu-agent/token').read_text().strip()
    serve(args.socket, token)


if __name__ == '__main__':
    main()
