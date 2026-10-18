#!/usr/bin/env python3
"""Target-runner offline dependency closure check; does not fetch packages.

A release proof binds the wheelhouse lock, requirements, platform and interpreter.
Run inside each target OS/architecture before distributing a native package.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys

SCHEMA = 'mta-server-offline-runtime-v1'


def sha256(path: Path) -> str:
    with path.open('rb') as handle:
        return hashlib.file_digest(handle, 'sha256').hexdigest()


def metadata(stage: Path) -> dict:
    return {
        'schema': SCHEMA,
        'wheelhouse_lock_sha256': sha256(stage / 'wheelhouse.lock.json'),
        'requirements_sha256': sha256(stage / 'application/requirements.txt'),
        'python': '.'.join(map(str, sys.version_info[:3])),
        'python_implementation': platform.python_implementation(),
        'machine': platform.machine(),
        'platform': platform.system(),
    }


def verify(stage: Path, proof: Path | None = None) -> dict:
    # Uses pip's actual resolver, not filename heuristics. --ignore-installed
    # prevents ambient site-packages from masking missing transitive wheels.
    from wheelhouse_lock import verify as verify_lock
    verify_lock(stage)
    cmd = [sys.executable, '-m', 'pip', 'install', '--dry-run', '--ignore-installed',
           '--no-index', '--only-binary=:all:', '--disable-pip-version-check',
           f'--find-links={stage / "wheelhouse"}',
           '-r', str(stage / 'application/requirements.txt')]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=180, check=False,
                            env={**os.environ, 'PIP_NO_INDEX': '1', 'PIP_DISABLE_PIP_VERSION_CHECK': '1'})
    if result.returncode:
        raise ValueError('Offline dependency resolution failed: ' + (result.stderr or result.stdout)[-1500:])
    data = metadata(stage)
    if proof is not None:
        proof.write_text(json.dumps(data, indent=2, sort_keys=True) + '\n')
    return data


def check_proof(stage: Path) -> None:
    path = stage / 'offline-runtime-proof.json'
    if not path.is_file() or path.is_symlink():
        raise ValueError('Missing offline runtime proof')
    if json.loads(path.read_text()) != metadata(stage):
        raise ValueError('Offline runtime proof is stale or targets a different runtime/architecture')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('stage', type=Path)
    parser.add_argument('--check-proof', action='store_true')
    parser.add_argument('--write-proof', action='store_true')
    args = parser.parse_args()
    stage = args.stage.resolve()
    if args.check_proof:
        check_proof(stage)
    else:
        verify(stage, stage / 'offline-runtime-proof.json' if args.write_proof else None)
    print('Offline runtime validation: OK')


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, subprocess.TimeoutExpired) as error:
        print(f'ERROR: {error}', file=sys.stderr)
        sys.exit(1)
