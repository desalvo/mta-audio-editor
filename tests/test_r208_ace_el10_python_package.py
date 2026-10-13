from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "install_ace_step.sh"


def test_el10_uses_distribution_python():
    content = SCRIPT.read_text()
    assert "OS_MAJOR -ge 10 && -z ${MTA_PYTHON:-}" in content
    assert "PYTHON=python3" in content
    assert "dnf install -y git ca-certificates python3 python3-pip" in content


def test_python_version_checked_and_venv_required():
    content = SCRIPT.read_text()
    assert "PY_VERSION=" in content
    assert "3.11 || $PY_VERSION == 3.12" in content
    assert '"$PYTHON" -m venv --help' in content


def test_custom_interpreter_is_respected():
    content = SCRIPT.read_text()
    assert "-z ${MTA_PYTHON:-}" in content
    assert '"$PYTHON" "${PYTHON}-pip"' in content
