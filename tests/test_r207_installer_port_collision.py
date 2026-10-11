"""Installer must never mistake an unrelated local listener for MTA."""
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "install_mta.sh"


def test_port_preflight_precedes_dependency_install_and_source_replacement():
    s = SCRIPT.read_text()
    assert "check_mta_port_owner || exit 3" in s
    assert s.index("check_mta_port_owner || exit 3") < s.index("dnf install -y git")
    assert s.index("check_mta_port_owner || exit 3") < s.index("git clone --quiet")
    assert 'ss -H -ltnp "sport = :$PORT"' in s
    assert "systemctl is-active --quiet mta-audio-editor.service" in s
    assert 'pid=$mainpid,' in s


def test_health_check_requires_mta_unit_owner_and_json_identity():
    s = SCRIPT.read_text()
    assert "if verify_mta_listener && curl" in s
    assert 'd.get("status")=="ok"' in s
    assert 'str(d.get("revision", "")).isdigit()' in s
    assert 'd.get("version")' in s
    assert "if (( ! ok )); then" in s
