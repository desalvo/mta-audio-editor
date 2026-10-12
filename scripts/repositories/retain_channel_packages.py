#!/usr/bin/env python3
"""Retain the newest two native package versions per format/architecture.

Uses distro-native Debian and RPM version comparison, never lexical ordering.
"""
import argparse
from functools import cmp_to_key
from pathlib import Path
import subprocess


def run(*args):
    return subprocess.check_output(args, text=True).strip()


def deb_info(path):
    return (run('dpkg-deb', '-f', str(path), 'Package'),
            run('dpkg-deb', '-f', str(path), 'Architecture'),
            run('dpkg-deb', '-f', str(path), 'Version'))


def rpm_info(path):
    values = run('rpm', '-qp', '--qf', '%{NAME}\n%{ARCH}\n%{EPOCHNUM}\n%{VERSION}\n%{RELEASE}\n', str(path)).splitlines()
    if len(values) != 5:
        raise ValueError(f'Invalid RPM identity: {path}')
    return values[0], values[1], (values[2], values[3], values[4])


def compare_deb(a, b):
    if subprocess.run(['dpkg', '--compare-versions', a, 'gt', b], check=False).returncode == 0:
        return 1
    if subprocess.run(['dpkg', '--compare-versions', a, 'lt', b], check=False).returncode == 0:
        return -1
    return 0


def compare_rpm(a, b):
    import rpm  # Requires python3-rpm on the publisher, checked in CI.
    return rpm.labelCompare(a, b)


def retain(directory, extension, inspect, compare, limit=2, dry_run=False):
    groups = {}
    for file in directory.glob(f'*{extension}'):
        name, arch, version = inspect(file)
        if name != 'mta-audio-editor-server':
            raise ValueError(f'Refusing unexpected package: {file}')
        groups.setdefault((name, arch), []).append((version, file))
    for identity, packages in groups.items():
        versions = sorted({version for version, _ in packages}, key=cmp_to_key(compare), reverse=True)
        keep = versions[:limit]
        for version, file in packages:
            if version not in keep:
                print(f'{"WOULD REMOVE" if dry_run else "REMOVE"}: {file} ({identity}, {version})')
                if not dry_run:
                    file.unlink()
    return groups


def main():
    p = argparse.ArgumentParser()
    p.add_argument('directory', type=Path)
    p.add_argument('--limit', type=int, default=2)
    p.add_argument('--dry-run', action='store_true')
    args = p.parse_args()
    if args.limit != 2:
        p.error('This release policy requires exactly two versions')
    retain(args.directory, '.deb', deb_info, compare_deb, args.limit, args.dry_run)
    retain(args.directory, '.rpm', rpm_info, compare_rpm, args.limit, args.dry_run)


if __name__ == '__main__':
    main()
