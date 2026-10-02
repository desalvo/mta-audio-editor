from pathlib import Path


def test_intel_macos_uses_supported_legacy_pytorch_stack():
    root = Path(__file__).resolve().parents[1]
    workflow = (root / ".github/workflows/ci-cd.yml").read_text(encoding="utf-8")
    req = (root / "requirements-stems-macos-x64.txt").read_text(encoding="utf-8")

    assert "runner: macos-15-intel" in workflow
    assert "arch: x64" in workflow
    assert "python: '3.12'" in workflow
    assert "requirements-stems-macos-x64.txt" in workflow
    assert "torch==2.2.2" in req
    assert "torchaudio==2.2.2" in req
    assert "demucs==4.1.0" in req

    assert "runner: macos-15" in workflow
    assert "arch: arm64" in workflow
    assert "python: '3.14'" in workflow
