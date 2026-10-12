#!/usr/bin/env python3
"""Test the *actual* native-package payload in an isolated venv, without network.

The caller extracts the DEB/RPM to --root first. This is a payload runtime
smoke test, not an OS package lifecycle or migration test.
"""
import argparse
import os
from pathlib import Path
import subprocess
import sys
import tempfile


def smoke(root: Path) -> None:
    app = root / 'usr/lib/mta-audio-editor-server'
    wheels = root / 'usr/share/mta-audio-editor-server/wheelhouse'
    if not (app / 'app/main.py').is_file() or not (app / 'requirements.txt').is_file():
        raise ValueError('Package lacks application entrypoints or requirements')
    if not wheels.is_dir() or not list(wheels.glob('*.whl')):
        raise ValueError('Package lacks offline wheels')
    with tempfile.TemporaryDirectory(prefix='mta-offline-payload-') as tmp:
        venv = Path(tmp) / 'venv'
        subprocess.run([sys.executable, '-m', 'venv', str(venv)], check=True)
        python = venv / 'bin/python'
        env = {**os.environ, 'PIP_NO_INDEX': '1', 'PIP_DISABLE_PIP_VERSION_CHECK': '1'}
        subprocess.run([str(python), '-m', 'pip', 'install', '--no-index',
                        '--find-links', str(wheels), '-r', str(app / 'requirements.txt')],
                       env=env, check=True)
        subprocess.run([str(python), '-m', 'pip', 'check'], env=env, check=True)
        subprocess.run([str(python), '-c',
                        'import app.main; import app.ai_cgroup_launcher; print("OFFLINE_PAYLOAD_OK")'],
                       cwd=app, env=env, check=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, required=True)
    args = parser.parse_args()
    try:
        smoke(args.root.resolve())
    except (ValueError, subprocess.CalledProcessError, OSError) as exc:
        print(f'OFFLINE_PAYLOAD_FAILED: {exc}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
