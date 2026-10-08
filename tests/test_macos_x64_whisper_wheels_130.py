from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_macos_x64_whisper_uses_prebuilt_numba_llvmlite_line():
    req = (ROOT / "requirements-lyrics.txt").read_text(encoding="utf-8")
    assert "numba==0.61.2; sys_platform == 'darwin' and platform_machine == 'x86_64'" in req
    assert "llvmlite==0.44.0; sys_platform == 'darwin' and platform_machine == 'x86_64'" in req
    workflow = (ROOT / ".github/workflows/ci-cd.yml").read_text(encoding="utf-8")
    assert "pip install -r requirements-lyrics.txt" in workflow


def test_macos_x64_chords_preserve_whisper_numpy_compatibility():
    req = (ROOT / "requirements-chords.txt").read_text(encoding="utf-8")
    assert "numpy==1.26.4; sys_platform == 'darwin' and platform_machine == 'x86_64'" in req
    workflow = (ROOT / ".github/workflows/ci-cd.yml").read_text(encoding="utf-8")
    assert "pip install -r requirements-chords.txt" in workflow
    lyrics = (ROOT / "requirements-lyrics.txt").read_text(encoding="utf-8")
    assert "numba==0.61.2; sys_platform == 'darwin' and platform_machine == 'x86_64'" in lyrics


def test_librosa_uses_compatible_versions_on_macos_intel():
    req = (ROOT / "requirements-chords.txt").read_text(encoding="utf-8")
    assert "librosa>=0.11.0,<0.12; sys_platform == 'darwin' and platform_machine == 'x86_64'" in req
    assert "librosa>=1.0.0,<1.1; sys_platform != 'darwin' or platform_machine != 'x86_64'" in req
    assert "librosa>=1.0.0,<1.1\n" not in req
