#!/usr/bin/env python3
"""Create an offline, hash-locked runtime staging for native server packages.

Run INSIDE a supported target OS/architecture with the same Python interpreter
used by the resulting package; do not cross-download binary wheels.
"""
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys


def run(cmd):
    subprocess.run(cmd, check=True, env={**os.environ, 'PIP_DISABLE_PIP_VERSION_CHECK': '1'})


def prepare(source: Path, stage: Path, requirements: Path):
    if sys.version_info < (3, 12):
        raise ValueError('Python 3.12+ is required by the MTA server')
    if stage.exists() and any(stage.iterdir()):
        raise ValueError('Refusing non-empty staging directory: use a fresh stage')
    if not (source / 'app/main.py').is_file() or not (source / 'app/ai_cgroup_launcher.py').is_file():
        raise ValueError('MTA application entrypoints not found')
    if not requirements.is_file():
        raise ValueError('Missing server requirements')
    app = stage / 'application'
    wheels = stage / 'wheelhouse'
    app.mkdir(parents=True, exist_ok=True)
    wheels.mkdir()
    # Only the application and locked runtime requirements belong to the server.
    shutil.copytree(source / 'app', app / 'app', ignore=shutil.ignore_patterns('__pycache__', '*.pyc', '.git'), symlinks=False)
    shutil.copy2(requirements, app / 'requirements.txt')
    # Download the full transitive closure. No sdists, no editable/VCS builds.
    run([sys.executable, '-m', 'pip', 'download', '--only-binary=:all:', '--no-cache-dir',
         '--dest', str(wheels), '-r', str(app / 'requirements.txt')])
    scripts = Path(__file__).resolve().parent
    run([sys.executable, str(scripts / 'wheelhouse_lock.py'), 'create', str(stage)])
    run([sys.executable, str(scripts / 'verify_offline_runtime.py'), str(stage), '--write-proof'])
    run([sys.executable, str(scripts / 'validate_stage.py'), str(stage)])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', type=Path, default=Path('.'))
    parser.add_argument('--stage', type=Path, required=True)
    parser.add_argument('--requirements', type=Path, default=Path('requirements.txt'))
    args = parser.parse_args()
    prepare(args.source.resolve(), args.stage.resolve(), args.requirements.resolve())
    print(f'Release-ready offline runtime: {args.stage}')


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, subprocess.CalledProcessError) as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        sys.exit(1)
