from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "install_mta.sh"
REQUIREMENTS = ROOT / "requirements.txt"


def test_rocky_installer_uses_supported_python():
    text = SCRIPT.read_text()
    assert "python3.14 python3.14-pip" in text
    assert "for candidate in python3.14 python3.13 python3.12 python3; do" in text
    assert "sys.version_info >= (3,12)" in text
    assert "if command -v python3.11" not in text
    assert '"$PY" -m venv "$TEMP/venv-mta"' in text
    assert "numpy==2.5.3" in REQUIREMENTS.read_text()
