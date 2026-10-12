#!/usr/bin/env python3
"""Read-only local readiness audit for a Proxmox AMD GPU telemetry agent.

Never prints authentication secrets or edits LXC configurations. Each node runs
this check independently; no host, guest or replication target is hardcoded.
"""
from __future__ import annotations
import json
import pathlib
import re
import subprocess
import sys

RUNTIME = pathlib.Path('/run/mta-gpu-agent')
CONF = pathlib.Path('/etc/pve/lxc')


def command(args, timeout=10):
    try:
        out = subprocess.run(args, capture_output=True, text=True, timeout=timeout, check=False)
        return {'ok': out.returncode == 0, 'output': out.stdout.strip()[:2000],
                'error': out.stderr.strip()[:300]}
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {'ok': False, 'output': '', 'error': str(exc)[:300]}


def audit():
    results = {'agent_service': command(['systemctl', 'is-active', 'mta-gpu-agent.service'])['output'],
               'timer': command(['systemctl', 'is-active', 'mta-gpu-agent-tag-sync.timer'])['output'],
               'socket_exists': (RUNTIME / 'agent.sock').is_socket(),
               'token_present': (RUNTIME / 'token').is_file(),
               'containers': []}
    if not CONF.is_dir():
        results['warning'] = 'Local Proxmox LXC config directory unavailable'
        return results
    try:
        from mta_proxmox_tag_sync import eligible, parse_config
    except ModuleNotFoundError:
        from scripts.mta_proxmox_tag_sync import eligible, parse_config
    for path in sorted(CONF.glob('*.conf')):
        if not path.stem.isdecimal():
            continue
        try:
            cfg = path.read_text()
        except OSError:
            continue
        if not eligible(cfg):
            continue
        parsed = parse_config(cfg)
        mounts = [val for key, val in parsed.items() if re.fullmatch(r'mp\d+', key)
                  and 'mp=/run/mta-gpu-agent' in val]
        mount_ok = any('replicate=0' in v and 'shared=1' in v and 'ro=1' in v for v in mounts)
        status = command(['pct', 'status', path.stem])
        results['containers'].append({'ctid': int(path.stem),
                                      'running': status['output'] == 'status: running',
                                      'mount_configured': bool(mounts),
                                      'mount_replication_safe_flags': mount_ok,
                                      'mount_requires_review': bool(mounts) and not mount_ok,
                                      'replication_jobs': [],
                                      'note': 'Mount cannot be verified inside a running LXC from this audit'})
    # Informative only: never change or disable replication.
    repl = command(['pvesr', 'list'])
    results['replication_list_available'] = repl['ok']
    for row in results['containers']:
        row['replication_jobs'] = [line.split()[0] for line in repl['output'].splitlines()[1:]
                                   if line.split() and line.split()[0].split('-')[0] == str(row['ctid'])]
    return results


def main():
    report = audit()
    print(json.dumps(report, indent=2))
    return 0


if __name__ == '__main__':
    sys.exit(main())
