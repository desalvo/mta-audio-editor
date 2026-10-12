#!/usr/bin/env python3
"""Conservatively discover explicitly tagged Proxmox LXC containers.

No restart, no tag modification, and no implicit changes to unprivileged guests.
"""
from __future__ import annotations
import argparse
import json
import pathlib
import re
import subprocess
import shutil

TAG_RE = re.compile(r'^[a-zA-Z0-9][a-zA-Z0-9_.-]{0,62}$')
ENTRY = 'lxc.mount.entry: /run/mta-gpu-agent run/mta-gpu-agent none bind,create=dir,optional 0 0'


def parse_config(content: str) -> dict:
    values = {}
    for line in content.splitlines():
        if ':' in line and not line.lstrip().startswith('#'):
            k, v = line.split(':', 1)
            values[k.strip()] = v.strip()
    return values


def eligible(content: str, required=('mta-audio-editor', 'mta-gpu-agent')) -> bool:
    tags = set(re.split(r'[;,\s]+', parse_config(content).get('tags', '')))
    return all(t in tags for t in required)


def plan(configs: dict[str, str]) -> list[dict]:
    result = []
    for ctid, content in sorted(configs.items(), key=lambda kv: int(kv[0])):
        if not eligible(content):
            continue
        conf = parse_config(content)
        # Proxmox default unprivileged=0; do not grant host socket to id-mapped roots.
        privileged = conf.get('unprivileged', '0') == '0'
        default_uid_map = not any(ln.startswith('lxc.idmap:') for ln in content.splitlines())
        entry_present = ENTRY in content.splitlines()
        other_mount = any('mp=/run/mta-gpu-agent' in ln for ln in content.splitlines())
        free_mount = next((i for i in range(256) if f'mp{i}' not in conf), None)
        result.append({'ctid': int(ctid), 'privileged': privileged,
                       'configured': entry_present,
                       'action': 'none' if (entry_present or other_mount) else ('manual-review' if (not privileged and not default_uid_map) or free_mount is None else 'add-mount'),
                       'mapped_root_uid': 100000 if not privileged and default_uid_map else None,
                       'mount_id': free_mount if not other_mount and not entry_present and (privileged or default_uid_map) else None,
                       'restart_required': not entry_present and not other_mount and (privileged or default_uid_map)})
    return result


def load_local_configs(root: pathlib.Path) -> dict[str, str]:
    return {p.stem: p.read_text() for p in root.glob('*.conf') if p.stem.isdecimal()}


def sync(root: pathlib.Path, *, apply=False) -> list[dict]:
    planned = plan(load_local_configs(root))
    if apply:
        # ACLs authorize the mapped guest root to connect to the UNIX socket
        # and read the shared token. This applies only to explicitly tagged
        # containers with default Proxmox ID maps. Never chmod world-readable.
        for rec in planned:
            if rec['mapped_root_uid'] is not None and rec['action'] in ('add-mount', 'none'):
                if not shutil.which('setfacl'):
                    rec['action'] = 'manual-review-missing-acl'
                    continue
                if not pathlib.Path('/run/mta-gpu-agent/agent.sock').is_socket():
                    rec['action'] = 'manual-review-agent-not-running'
                    continue
                uid = str(rec['mapped_root_uid'])
                for target, rights in [('/run/mta-gpu-agent', 'rx'),
                                       ('/run/mta-gpu-agent/agent.sock', 'rw'),
                                       ('/run/mta-gpu-agent/token', 'r')]:
                    subprocess.run(['setfacl', '-m', f'u:{uid}:{rights}', target], check=True, timeout=10)
        for rec in planned:
            if rec['action'] != 'add-mount':
                continue
            path = root / (str(rec['ctid']) + '.conf')
            original = path.read_text()
            if not eligible(original) or ENTRY in original.splitlines():
                continue
            # Proxmox cluster configuration is API-managed. pct set is used rather
            # than writing directly to /etc/pve, and never starts/stops guests.
            subprocess.run(['pct', 'set', str(rec['ctid']), f'-mp{rec["mount_id"]}',
                            '/run/mta-gpu-agent,mp=/run/mta-gpu-agent,ro=1'],
                           check=True, timeout=15)
            rec['action'] = 'configured-pending-restart'
    return planned


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--config-dir', default='/etc/pve/lxc')
    p.add_argument('--apply', action='store_true', help='Apply safe privileged LXC changes; never restart')
    a = p.parse_args()
    print(json.dumps(sync(pathlib.Path(a.config_dir), apply=a.apply), indent=2))


if __name__ == '__main__':
    main()
