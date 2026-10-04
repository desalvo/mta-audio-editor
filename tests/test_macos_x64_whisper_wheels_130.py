from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_macos_x64_whisper_uses_prebuilt_numba_llvmlite_line():
    req = (ROOT / "requirements-lyrics.txt").read_text(encoding="utf-8")
    assert "numba==0.61.2; sys_platform == 'darwin' and platform_machine == 'x86_64'" in req
    assert "llvmlite==0.44.0; sys_platform == 'darwin' and platform_machine == 'x86_64'" in req
    workflow = (ROOT / ".github/workflows/ci-cd.yml").read_text(encoding="utf-8")
    assert "pip install -r requirements-lyrics.txt" in workflow
