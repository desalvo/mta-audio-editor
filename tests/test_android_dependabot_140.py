from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_android_dependabot_updates_are_integrated():
    gradle = (ROOT / "mobile/android/app/build.gradle.kts").read_text(encoding="utf-8")
    assert 'implementation("androidx.core:core:1.19.1")' in gradle
    assert 'implementation("com.microsoft.onnxruntime:onnxruntime-android:1.30.0")' in gradle
    assert 'androidx.core:core:1.15.0' not in gradle
    assert 'onnxruntime-android:1.22.0' not in gradle


def test_android_package_version_matches_release():
    gradle = (ROOT / "mobile/android/app/build.gradle.kts").read_text(encoding="utf-8")
    version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    revision = int((ROOT / "REVISION").read_text(encoding="utf-8").strip())
    major, minor, patch = (int(part) for part in version.split("."))
    version_code = major * 10_000_000 + minor * 10_000 + patch * 1_000 + revision
    assert f'versionCode = {version_code}' in gradle
    assert f'versionName = "{version}"' in gradle
