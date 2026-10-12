"""Guard against accidentally omitting the real native server certification stages."""
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def test_native_matrix_has_rpm_install_and_ubuntu_installer():
    flow = yaml.safe_load((ROOT / '.github/workflows/server-native-runtime-validation.yml').read_text())
    matrix = flow['jobs']['offline-wheelhouse']['strategy']['matrix']['include']
    assert any(row['name'] == 'ubuntu2404-python312' for row in matrix)
    rpm_steps = flow['jobs']['rpm-payload']['steps']
    assert any('MTA_CI_DISPOSABLE_CONTAINER=1' in step.get('run', '') and 'test_rpm_upgrade.sh' in step.get('run', '') for step in rpm_steps)
    assert any('test_deb_upgrade.sh' in step.get('run', '') for step in flow['jobs']['offline-wheelhouse']['steps'])


def test_rpm_dependency_is_ffmpeg_executable_not_unavailable_meta_package():
    builder = (ROOT / 'scripts/server_packages/build_rpm.sh').read_text()
    assert '/usr/bin/ffmpeg' in builder
    assert 'Requires: python3.12, python3.12-pip, ffmpeg,' not in builder


def test_ephemeral_signed_repository_requires_disposable_container():
    script = (ROOT / 'scripts/repositories/test_signed_apt_repository_ci.sh').read_text()
    assert 'MTA_CI_DISPOSABLE_CONTAINER' in script
    assert 'gnupg' in script
    assert 'signed-by=' in script
    assert 'apt-get update' in script
    assert 'quick-generate-key' in script
    flow = yaml.safe_load((ROOT / '.github/workflows/server-package-repository-validation.yml').read_text())
    assert 'signed-apt-repository' in flow['jobs']
