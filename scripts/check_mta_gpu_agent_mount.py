#!/usr/bin/env python3
"""Read-only host/LXC socket visibility check. Never restarts or changes an LXC."""
import argparse
import json
from pathlib import Path
import stat
import subprocess


def inspect_directory(path):
    result = {'directory': None, 'socket': False}
    try:
        st = Path(path).stat()
        result['directory'] = [st.st_dev, st.st_ino]
        result['socket'] = stat.S_ISSOCK((Path(path) / 'agent.sock').stat().st_mode)
    except OSError as exc:
        result['error'] = type(exc).__name__
    return result


def classify(host, guest):
    if not host.get('socket'): return 'host-agent-socket-unavailable'
    if not guest.get('directory'): return 'guest-directory-unavailable'
    if host['directory'] != guest['directory']: return 'different-directory-or-stale-bind-mount'
    if not guest.get('socket'): return 'guest-socket-not-accessible'
    return 'same-live-directory-and-socket-visible'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ct-id', required=True, type=int)
    args = parser.parse_args()
    if args.ct_id <= 0: parser.error('positive CT ID required')
    # Reading this helper's function source creates a fixed diagnostic payload;
    # no host command is supplied by a remote client or executed through a shell.
    import inspect
    script = ('import json,stat\nfrom pathlib import Path\n' + inspect.getsource(inspect_directory)
              + "\nprint(json.dumps(inspect_directory('/opt/mta-gpu-agent-host')))\n")
    host = inspect_directory('/run/mta-gpu-agent')
    try:
        reply = subprocess.run(['pct', 'exec', str(args.ct_id), '--', 'python3', '-c', script],
                               check=True, capture_output=True, text=True, timeout=20)
        guest = json.loads(reply.stdout)
        if not isinstance(guest, dict): raise ValueError('invalid guest reply')
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        guest = {'error': type(exc).__name__}
    print(json.dumps({'ct_id': args.ct_id, 'host': host, 'guest': guest,
                      'result': classify(host, guest), 'changes_made': False}, indent=2))


if __name__ == '__main__': main()
