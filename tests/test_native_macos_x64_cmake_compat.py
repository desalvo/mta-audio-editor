from pathlib import Path


def test_intel_macos_enables_cmake_legacy_policy_for_sphn():
    root = Path(__file__).resolve().parents[1]
    workflow = (root / ".github/workflows/ci-cd.yml").read_text(encoding="utf-8")
    assert "runner: macos-15-intel" in workflow
    assert "python: '3.12'" in workflow
    assert "export CMAKE_POLICY_VERSION_MINIMUM=3.5" in workflow
    assert "export MACOSX_DEPLOYMENT_TARGET=10.13" in workflow
    assert "requirements-stems-macos-x64.txt" in workflow
