"""Prevent ARM64 sphn/audiopus_sys from falling back to bundled Opus CMake."""
from pathlib import Path


def test_linux_native_ci_uses_system_opus_before_stem_dependencies():
    root = Path(__file__).resolve().parents[1]
    workflow = (root / ".github/workflows/ci-cd.yml").read_text(encoding="utf-8")
    native = workflow.split("name: Linux native (${{ matrix.arch }}) DEB/RPM", 1)[1]
    native = native.split("- name: Compile portable native audio meter", 1)[0]
    assert "libopus-dev" in native
    assert "pkg-config --modversion opus" in native
    assert native.index("pkg-config --modversion opus") < native.index("pip install -r requirements-stems.txt")

def test_revision_19_android_and_ios_metadata():
    root = Path(__file__).resolve().parents[1]
    rev = int((root / "REVISION").read_text().strip())
    android = (root / "mobile/android/app/build.gradle.kts").read_text()
    ios = (root / "mobile/ios/MTAEditorMobile/Info.plist").read_text()
    assert f"versionCode = {30000 + rev}" in android
    assert f'<key>MTAEditorRevision</key><string>{rev}</string>' in ios
