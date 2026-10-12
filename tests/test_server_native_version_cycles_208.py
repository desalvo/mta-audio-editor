"""Regression guards for native package-manager cycles and signed RPM CI."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_deb_version_cycle_requires_disposable_systemd_vm():
    src = (ROOT / 'scripts/server_packages/test_deb_version_cycle.sh').read_text()
    assert 'MTA_CI_DISPOSABLE_VM' in src
    assert '/proc/1/comm' in src
    assert '--allow-downgrades' in src
    assert 'check_system_services.sh' in src
    assert 'cmp /etc/mta/mta.env' in src


def test_rpm_version_cycle_requires_disposable_container():
    src = (ROOT / 'scripts/server_packages/test_rpm_version_cycle.sh').read_text()
    assert 'MTA_CI_DISPOSABLE_CONTAINER' in src
    assert 'dnf -y downgrade' in src
    assert 'dnf -y upgrade' in src
    assert 'cmp /etc/mta/mta.env' in src


def test_signed_rpm_repo_checks_both_signatures_and_tampering():
    src = (ROOT / 'scripts/repositories/test_signed_rpm_repository_ci.sh').read_text()
    assert 'MTA_CI_DISPOSABLE_CONTAINER' in src
    assert 'rpmsign --addsign' in src
    assert 'rpm --checksig' in src
    assert 'repo_gpgcheck=1' in src
    assert 'gpgcheck=1' in src
    assert 'tampered.xml' in src
    assert '--enablerepo=mta-signed-ci' in src


def test_workflow_runs_version_cycles_and_signed_rpm():
    src = (ROOT / '.github/workflows/server-native-runtime-validation.yml').read_text()
    assert 'scripts/server_packages/test_deb_version_cycle.sh' in src
    assert 'scripts/server_packages/test_rpm_version_cycle.sh' in src
    assert 'scripts/repositories/test_signed_rpm_repository_ci.sh' in src
    assert 'MTA_RPM_RELEASE=0.207.early' in src
    assert "MTA_SERVER_VERSION='0.3.0~early.207'" in src
