from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_macos_x64_whisper_uses_prebuilt_numba_llvmlite_line():
    req = (ROOT / "requirements-lyrics.txt").read_text(encoding="utf-8")
    assert "numba==0.68.0; sys_platform == 'darwin' and platform_machine == 'x86_64'" in req
    assert "llvmlite==0.50.0; sys_platform == 'darwin' and platform_machine == 'x86_64'" in req
    workflow = (ROOT / ".github/workflows/ci-cd.yml").read_text(encoding="utf-8")
    assert "pip install -r requirements-lyrics.txt" in workflow


def test_macos_x64_chords_preserve_whisper_numpy_compatibility():
    req = (ROOT / "requirements-chords.txt").read_text(encoding="utf-8")
    assert "numpy==2.5.3; sys_platform == 'darwin' and platform_machine == 'x86_64'" in req
    workflow = (ROOT / ".github/workflows/ci-cd.yml").read_text(encoding="utf-8")
    assert "pip install -r requirements-chords.txt" in workflow
    lyrics = (ROOT / "requirements-lyrics.txt").read_text(encoding="utf-8")
    assert "numba==0.68.0; sys_platform == 'darwin' and platform_machine == 'x86_64'" in lyrics
