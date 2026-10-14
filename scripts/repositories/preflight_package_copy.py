#!/usr/bin/env python3
"""Fail closed before copying packages into a signed repository staging tree.

Only operate on known package pool directories. The caller MUST regenerate signed
APT/RPM metadata after the package pool has been cleaned.
"""
import argparse
from pathlib import Path

POOLS = (('apt', 'pool', '.deb'), ('rpm/el9', 'packages', '.rpm'), ('rpm/el10', 'packages', '.rpm'))


def prepare(input_root: Path, output_root: Path, channel: str, *, limit: int = 2):
    if channel not in ('early', 'stable') or limit != 2:
        raise ValueError('Invalid channel or retention limit')
    planned = []
    for part, pool, ext in POOLS:
        source = input_root if part == 'apt' else input_root / part
        target = output_root / part / channel / pool if part == 'apt' else output_root / 'rpm' / channel / part.split('/')[1] / pool
        packages = sorted(source.glob('*' + ext))
        if not 1 <= len(packages) <= limit:
            raise ValueError(f'Expected one or two retained {part} packages before copying, got {len(packages)}')
        planned.append((target, ext))
    # Validate all inputs before mutating any destination.
    for target, ext in planned:
        target.mkdir(parents=True, exist_ok=True)
        for old in target.glob('*' + ext):
            if old.is_symlink() or not old.is_file():
                raise ValueError(f'Unsafe existing package: {old}')
            old.unlink()
        if len(list(target.glob('*' + ext))) > limit:
            raise ValueError(f'Package retention failed in {target}')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--channel', choices=('early', 'stable'), required=True)
    args = parser.parse_args()
    prepare(args.input.resolve(), args.output.resolve(), args.channel)


if __name__ == '__main__':
    main()
