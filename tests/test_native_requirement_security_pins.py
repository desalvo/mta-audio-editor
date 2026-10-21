"""Guard against reintroducing native requirement versions flagged by CI."""

from pathlib import Path


def test_native_requirement_security_pins():
    project_root = Path(__file__).resolve().parents[1]
    lines = (project_root / "requirements-native.txt").read_text(encoding="utf-8").splitlines()
    pins = dict(line.split("==", 1) for line in lines if line.startswith(("certifi==", "uv==")))
    assert pins == {"certifi": "2026.10.19", "uv": "0.13.4"}
