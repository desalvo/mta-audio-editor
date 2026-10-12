#!/usr/bin/env python3
"""Create/verify a content-addressed offline wheelhouse manifest.

The lock authenticates staged bytes, not their provenance. CI must independently
resolve pinned transitive requirements and audit dependencies/licenses.
"""
import argparse
import hashlib
import json
from pathlib import Path
import zipfile

SCHEMA = 'mta-offline-wheelhouse-v1'


def inventory(stage: Path):
    directory = stage / 'wheelhouse'
    wheels = sorted(directory.glob('*.whl'))
    if not wheels:
        raise ValueError('wheelhouse empty')
    result = []
    for wheel in wheels:
        if wheel.is_symlink() or not wheel.is_file():
            raise ValueError(f'unsafe wheel: {wheel.name}')
        with zipfile.ZipFile(wheel) as archive:
            bad = archive.testzip()
            if bad is not None:
                raise ValueError(f'corrupt wheel: {wheel.name}: {bad}')
            if not any(n.endswith('.dist-info/WHEEL') for n in archive.namelist()):
                raise ValueError(f'wheel lacks metadata: {wheel.name}')
        result.append({'file': wheel.name, 'sha256': hashlib.file_digest(wheel.open('rb'), 'sha256').hexdigest(), 'bytes': wheel.stat().st_size})
    return result


def verify(stage: Path):
    target = stage / 'wheelhouse.lock.json'
    if not target.is_file() or target.is_symlink():
        raise ValueError('missing trusted wheelhouse.lock.json')
    data = json.loads(target.read_text())
    if data.get('schema') != SCHEMA or data.get('wheels') != inventory(stage):
        raise ValueError('wheelhouse differs from lock manifest')
    if set(data) != {'schema', 'wheels'}:
        raise ValueError('unknown wheelhouse manifest properties')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=('create', 'verify'))
    parser.add_argument('stage', type=Path)
    args = parser.parse_args()
    if args.command == 'create':
        data = {'schema': SCHEMA, 'wheels': inventory(args.stage)}
        (args.stage / 'wheelhouse.lock.json').write_text(json.dumps(data, indent=2) + '\n')
    else:
        verify(args.stage)
    print(f'wheelhouse lock {args.command}: OK')


if __name__ == '__main__':
    main()
