"""Regression tests for cross-platform release identity."""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]

def test_release_metadata_consistent():
    revision = (ROOT / "REVISION").read_text().strip()
    assert revision.isdecimal()
    assert (ROOT / "RELEASE").read_text().strip() == f"0.3.0-r{revision}"
    assert re.fullmatch(r"[0-9]{14}", (ROOT / "BUILD_INFO").read_text().strip())
    windows = (ROOT / "native/windows-version-info.txt").read_text()
    assert f"filevers=(0, 3, 0, {revision})" in windows
    assert f"prodvers=(0, 3, 0, {revision})" in windows
    assert f"Revision {revision}" in windows
    android = (ROOT / "mobile/android/app/build.gradle.kts").read_text()
    assert f"versionCode = {30000 + int(revision)}" in android
    assert f'MTA_REVISION", "\\"{revision}\\""' in android
    ios = (ROOT / "mobile/ios/MTAEditorMobile/Info.plist").read_text()
    assert f"<string>{30000 + int(revision)}</string>" in ios
    assert f"<string>{revision}</string>" in ios
