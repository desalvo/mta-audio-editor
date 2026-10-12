"""Pre-release systemd and RPM service lifecycle invariants."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UNITS = ROOT / "scripts/server_packages"


def test_web_service_delegates_required_cgroup_controllers():
    text = (UNITS / "mta-server.service").read_text()
    assert "Delegate=cpu io" in text
    assert "ExecStart=/opt/mta/server-venv/bin/python -m app.ai_cgroup_launcher" in text
    assert "NoNewPrivileges=true" in text


def test_billing_service_targets_offline_runtime():
    text = (UNITS / "mta-billing-scheduler.service").read_text()
    assert "ExecStart=/opt/mta/server-venv/bin/python -m app.ai_billing_scheduler" in text
    assert "EnvironmentFile=/etc/mta/mta.env" in text


def test_rpm_restarts_both_services_after_upgrade():
    text = (UNITS / "build_rpm.sh").read_text()
    assert "systemctl try-restart mta-server.service || :" in text
    assert "systemctl start mta-billing-scheduler.timer || :" in text
    assert "mta-billing-scheduler.timer" in text


def test_billing_is_periodic_and_packaged():
    timer = (UNITS / "mta-billing-scheduler.timer").read_text()
    service = (UNITS / "mta-billing-scheduler.service").read_text()
    deb = (UNITS / "build_deb.sh").read_text()
    rpm = (UNITS / "build_rpm.sh").read_text()
    assert "OnCalendar=hourly" in timer
    assert "Persistent=true" in timer
    assert "Type=oneshot" in service
    assert "mta-billing-scheduler.timer" in deb
    assert "mta-billing-scheduler.timer" in rpm


def test_http_acceptance_is_executed_after_install_and_reinstall():
    for name in ("test_deb_upgrade.sh", "test_rpm_upgrade.sh"):
        script = (UNITS / name).read_text()
        assert script.count("scripts/server_packages/http_smoke.py") == 2
    smoke = (UNITS / "http_smoke.py").read_text()
    assert "/api/health" in smoke
    assert "MTA_CI_DISPOSABLE_CONTAINER" in smoke
