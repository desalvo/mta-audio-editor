"""Guard against reintroducing native requirement versions flagged by CI."""

import ast
from pathlib import Path
import re


def test_native_requirement_security_pins():
    project_root = Path(__file__).resolve().parents[1]
    lines = (project_root / "requirements-native.txt").read_text(encoding="utf-8").splitlines()
    pins = dict(line.split("==", 1) for line in lines if line.startswith(("certifi==", "uv==")))
    assert pins == {"certifi": "2026.10.23", "uv": "0.13.7"}


def test_container_security_pins_match_stem_recipes():
    root = Path(__file__).resolve().parents[1]
    def pins(path):
        return dict(line.split("==", 1) for line in path.read_text().splitlines()
                    if line.startswith(("msgpack==", "urllib3==")))
    expected = pins(root / "requirements-stems.txt")
    assert expected.keys() == {"msgpack", "urllib3"}
    for name in ("requirements-stems-windows.txt", "requirements-stems-macos-x64.txt"):
        assert pins(root / name) == expected
    for name in ("Dockerfile", ".github/workflows/ci-cd.yml"):
        text = (root / name).read_text()
        actual = ast.literal_eval(re.search(r"expected=(\{[^}]+\})", text).group(1))
        assert {name: actual[name] for name in expected} == expected
    dockerfile = (root / "Dockerfile").read_text()
    for name, version in expected.items():
        assert name + "==" + version in dockerfile
