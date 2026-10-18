#!/usr/bin/env python3
"""Inspect actual RPM/DEB file lists, not merely build recipes."""
import argparse
import subprocess
from pathlib import Path

REQUIRED = (
    '/usr/lib/mta-audio-editor-server/native-installers/install_ai_engines.py',
    '/usr/lib/mta-audio-editor-server/native-installers/install_ace_step.sh',
    '/usr/lib/mta-audio-editor-server/native-installers/install_rocm_userspace.sh',
    '/usr/lib/mta-audio-editor-server/native-installers/install_demucs.py',
    '/usr/lib/mta-audio-editor-server/native-installers/configure_ai_workers.py',
    '/usr/lib/mta-audio-editor-server/native-installers/gpu_verified_billing.py',
)


def check(package: Path) -> None:
    if package.suffix == '.rpm':
        cmd = ['rpm', '-qpl', str(package)]
    elif package.suffix == '.deb':
        cmd = ['dpkg-deb', '--fsys-tarfile', str(package)]
    else:
        raise ValueError(f'Unsupported package type: {package}')
    if package.suffix == '.deb':
        import tarfile
        with subprocess.Popen(cmd, stdout=subprocess.PIPE) as proc:
            assert proc.stdout is not None
            with tarfile.open(fileobj=proc.stdout, mode='r|') as archive:
                members = {('/' + member.name.lstrip('./')): member for member in archive}
            if proc.wait():
                raise RuntimeError('Failed to inspect DEB content')
        missing = [p for p in REQUIRED if p not in members or not members[p].isfile() or not members[p].mode & 0o111]
    else:
        paths = set(subprocess.check_output(cmd, text=True).splitlines())
        missing = [p for p in REQUIRED if p not in paths]
        # rpm -qpl reports presence; executable mode is additionally checked via --dump.
        dump = subprocess.check_output(['rpm', '-qp', '--dump', str(package)], text=True)
        for p in REQUIRED:
            rows = [row.split() for row in dump.splitlines() if row.startswith(p + ' ')]
            if rows and not (int(rows[0][4], 8) & 0o111):
                missing.append(p + ' (not executable)')
    if missing:
        raise RuntimeError(f'{package.name}: missing/non-executable native installer: {missing}')
    print(f'PASS {package.name}: ACE-Step and ROCm installers included')


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('packages', nargs='+', type=Path)
    args = parser.parse_args()
    for package in args.packages:
        check(package)


if __name__ == '__main__':
    main()
