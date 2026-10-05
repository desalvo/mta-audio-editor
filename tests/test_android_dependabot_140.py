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
    assert 'versionCode = 20140' in gradle
    assert 'versionName = "0.2.0-140"' in gradle
