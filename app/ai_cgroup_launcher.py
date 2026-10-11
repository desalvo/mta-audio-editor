"""Systemd delegated cgroup v2 launcher for the MTA web server.

Moves the server process itself into a leaf before enabling domain controllers
at the delegated service parent, then execs the web server with a dedicated
CPU/I/O accounting subtree. Do not move processes managed by other units.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path


def configure(root: Path = Path('/sys/fs/cgroup')) -> str:
    membership = Path('/proc/self/cgroup').read_text().splitlines()
    paths = [line.split(':', 2)[2] for line in membership if line.startswith('0::')]
    if len(paths) != 1:
        raise RuntimeError('Unified cgroup membership missing')
    relative = paths[0].lstrip('/')
    parent = root / relative
    if not relative or not parent.is_dir():
        raise RuntimeError('Not in a systemd service cgroup')
    available = set((parent / 'cgroup.controllers').read_text().split())
    if not {'cpu', 'io'} <= available:
        raise RuntimeError('Delegated CPU/IO controllers unavailable')
    # The leaf contains the web process, avoiding internal processes in parent.
    server = parent / 'mta-web-process'
    server.mkdir(exist_ok=True)
    (server / 'cgroup.procs').write_text(str(os.getpid()))
    (parent / 'cgroup.subtree_control').write_text('+cpu +io')
    accounting = parent / 'mta-ai-accounting'
    accounting.mkdir(exist_ok=True)
    (accounting / 'cgroup.subtree_control').write_text('+cpu +io')
    enabled = set((accounting / 'cgroup.subtree_control').read_text().split())
    if not {'cpu', 'io'} <= enabled:
        raise RuntimeError('AI accounting controllers are not enabled')
    return str(accounting)


def main() -> None:
    try:
        os.environ['MTA_AI_CGROUP_PARENT'] = configure()
    except (OSError, RuntimeError) as exc:
        # The web interface can run without paid metering; never claim a
        # usable delegated accounting subtree when preflight fails.
        os.environ.pop('MTA_AI_CGROUP_PARENT', None)
        print(f'MTA cgroup delegation unavailable: {exc}', file=sys.stderr, flush=True)
    os.execve(sys.executable, [sys.executable, '-m', 'app.main'], os.environ.copy())  # noqa: S606


if __name__ == '__main__':
    main()
