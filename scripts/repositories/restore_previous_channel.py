#!/usr/bin/env python3
"""Safely import the previous signed snapshot's package binaries, not metadata."""
import argparse
import hashlib
import json
from pathlib import Path
import tarfile


def restore(manifest, archive, incoming, channel):
    info = json.loads(manifest.read_text())
    if info.get('channel') != channel or info.get('repository') != 'desalvo/mta-audio-editor':
        raise ValueError('Previous manifest identity mismatch')
    if hashlib.file_digest(archive.open('rb'), 'sha256').hexdigest() != info.get('sha256'):
        raise ValueError('Previous artifact checksum mismatch')
    with tarfile.open(archive, 'r:gz') as tar:
        for member in tar:
            name = member.name.removeprefix('./')
            if name.endswith('.deb'):
                prefix = f'apt/{channel}/pool/'
                destination_dir = incoming
            elif name.endswith('.rpm'):
                if name.startswith(f'rpm/{channel}/el10/packages/'):
                    prefix = f'rpm/{channel}/el10/packages/'
                    destination_dir = incoming / 'rpm' / 'el10'
                elif name.startswith(f'rpm/{channel}/el9/packages/'):
                    prefix = f'rpm/{channel}/el9/packages/'
                    destination_dir = incoming / 'rpm' / 'el9'
                else:
                    # Legacy snapshot before EL9/EL10 split.
                    prefix = f'rpm/{channel}/packages/'
                    destination_dir = incoming / 'rpm' / 'el9'
            else:
                continue
            if not name.startswith(prefix) or '/' in name[len(prefix):]:
                continue
            if not member.isfile():
                raise ValueError('Unsafe previous package entry')
            filename = Path(name).name
            if not filename or filename.startswith('.'):
                raise ValueError('Unsafe package name')
            destination_dir.mkdir(parents=True, exist_ok=True)
            destination = destination_dir / filename
            if destination.exists():
                continue  # Current candidate takes precedence; signature is regenerated.
            source = tar.extractfile(member)
            if source is None:
                raise ValueError('Cannot read previous package entry')
            with destination.open('xb') as out:
                while data := source.read(1024 * 1024):
                    out.write(data)


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--manifest', type=Path, required=True)
    p.add_argument('--archive', type=Path, required=True)
    p.add_argument('--incoming', type=Path, required=True)
    p.add_argument('--channel', choices=('early', 'stable'), required=True)
    args = p.parse_args()
    args.incoming.mkdir(parents=True, exist_ok=True)
    restore(args.manifest, args.archive, args.incoming, args.channel)


if __name__ == '__main__':
    main()
