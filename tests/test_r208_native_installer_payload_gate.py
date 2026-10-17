"""Test actual native package payload gate with positive and negative DEB fixtures."""
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
CHECK = ROOT / 'scripts/server_packages/verify_native_installers.py'
INSTALLERS = ('install_ai_engines.py', 'install_ace_step.sh', 'install_rocm_userspace.sh', 'install_demucs.py', 'configure_ai_workers.py', 'gpu_verified_billing.py')


@pytest.mark.skipif(shutil.which('dpkg-deb') is None, reason='dpkg-deb not available')
@pytest.mark.parametrize('omit', [None, 'install_ai_engines.py', 'install_ace_step.sh', 'install_rocm_userspace.sh', 'install_demucs.py', 'configure_ai_workers.py', 'gpu_verified_billing.py'])
def test_deb_payload_gate(tmp_path, omit):
    root = tmp_path / 'package'
    scripts = root / 'usr/lib/mta-audio-editor-server/native-installers'
    scripts.mkdir(parents=True)
    debian = root / 'DEBIAN'
    debian.mkdir()
    (debian / 'control').write_text('Package: mta-audio-editor-server\nVersion: 0.3.0-0.208\nArchitecture: all\nMaintainer: Tests <test@example.org>\nDescription: Payload test\n')
    for item in INSTALLERS:
        if item != omit:
            file = scripts / item
            file.write_text('#!/bin/sh\nexit 0\n')
            file.chmod(0o755)
    deb = tmp_path / 'fixture.deb'
    subprocess.run(['dpkg-deb', '--build', str(root), str(deb)], check=True, capture_output=True)
    result = subprocess.run([sys.executable, str(CHECK), str(deb)], text=True, capture_output=True)
    assert (result.returncode == 0) == (omit is None), result.stdout + result.stderr
    if omit:
        assert omit in result.stderr


def test_wizard_missing_package_helper_never_fetches_unverified_code():
    wizard = (ROOT / 'scripts/install_mta_native_wizard.sh').read_text()
    assert 'dnf --refresh upgrade mta-audio-editor-server' in wizard
    assert 'apt-get install --only-upgrade mta-audio-editor-server' in wizard
    assert 'Do not run a downloaded, unverified replacement installer' in wizard
