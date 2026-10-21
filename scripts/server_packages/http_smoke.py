#!/usr/bin/env python3
"""Disposable CI HTTP acceptance: start packaged MTA and check real health response."""
from __future__ import annotations

import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
from urllib.request import urlopen


def main() -> int:
    if os.environ.get('MTA_CI_DISPOSABLE_CONTAINER') != '1':
        raise SystemExit('Refusing to launch acceptance server outside disposable CI')
    app = Path('/usr/lib/mta-audio-editor-server')
    interpreter = Path('/opt/mta/server-venv/bin/python')
    if not interpreter.is_file() or not (app / 'app/main.py').is_file():
        raise SystemExit('Packaged server runtime missing')
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
    with tempfile.TemporaryDirectory(prefix='mta-http-ci-') as tmp:
        env = dict(os.environ, MTA_HOST='127.0.0.1', MTA_PORT=str(port), MTA_DATA_DIR=tmp)
        env.pop('MTA_AI_CGROUP_PARENT', None)
        with subprocess.Popen([str(interpreter), '-m', 'app.main'], cwd=app, env=env,
                              stdout=subprocess.DEVNULL, stderr=subprocess.PIPE) as proc:
            try:
                for _ in range(80):
                    if proc.poll() is not None:
                        err = proc.stderr.read().decode(errors='replace')[-1800:]
                        raise RuntimeError(f'Packaged server exited: {err}')
                    try:
                        with urlopen(f'http://127.0.0.1:{port}/api/health', timeout=1) as response:
                            payload = json.load(response)
                            if response.status == 200 and payload.get('status') == 'ok':
                                print('Packaged HTTP /api/health: OK')
                                return 0
                    except (OSError, ValueError):
                        time.sleep(0.25)
                raise RuntimeError('Packaged server HTTP readiness timeout')
            finally:
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait(timeout=5)
    return 1


if __name__ == '__main__':
    sys.exit(main())
