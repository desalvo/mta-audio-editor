"""Preflight contract for the privileged production acceptance checks."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'scripts' / 'server_packages'


def test_systemd_vm_acceptance_is_fail_closed():
    source = (BASE / 'check_system_services.sh').read_text()
    assert 'MTA_CI_DISPOSABLE_VM:-0' in source
    assert '/proc/1/comm' in source and 'systemd' in source
    assert 'systemctl is-active --quiet mta-server.service' in source
    assert 'systemctl is-active --quiet mta-billing-scheduler.timer' in source
    assert 'systemctl start mta-billing-scheduler.service' in source
    assert '/api/health' in source


def test_installers_do_not_touch_legacy_managed_install():
    for name in ('preinst', 'postinst', 'build_rpm.sh'):
        source = (BASE / name).read_text()
        assert '/opt/mta/application/.git' in source


def test_rpm_and_deb_persist_billing_timer():
    assert 'mta-billing-scheduler.timer' in (BASE / 'build_rpm.sh').read_text()
    assert 'mta-billing-scheduler.timer' in (BASE / 'build_deb.sh').read_text()
    assert 'Persistent=true' in (BASE / 'mta-billing-scheduler.timer').read_text()


def test_ephemeral_signed_repository_rejects_metadata_tampering():
    source = (ROOT / 'scripts/repositories/test_signed_apt_repository_ci.sh').read_text()
    assert 'tampered-release' in source
    assert 'accepted tampered Release metadata' in source
    assert 'signed-by=' in source


def test_real_systemd_acceptance_is_wired_to_ephemeral_ubuntu_runner():
    workflow = (ROOT / '.github/workflows/server-native-runtime-validation.yml').read_text()
    assert 'ubuntu-systemd-vm:' in workflow
    assert 'MTA_CI_DISPOSABLE_VM=1' in workflow
    assert 'Reinstall and verify service recovery and persistent state' in workflow


def test_service_port_matches_systemd_http_acceptance():
    unit = (BASE / 'mta-server.service').read_text()
    acceptance = (BASE / 'check_system_services.sh').read_text()
    assert 'Environment=MTA_PORT=8000' in unit
    assert '127.0.0.1:8000/api/health' in acceptance
    assert 'journalctl -u mta-server.service' in acceptance

def test_ubuntu_unit_verify_occurs_only_after_install():
    workflow = (ROOT / '.github/workflows/server-native-runtime-validation.yml').read_text()
    early = workflow.split('      - name: Prepare isolated target-runtime wheels')[0]
    assert 'systemd-analyze verify scripts/server_packages/' not in early
    assert 'MTA_CI_DISPOSABLE_VM=1' in workflow
