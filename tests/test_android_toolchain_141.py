from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_android_api37_toolchain_matches_androidx_core_1191():
    app = (ROOT / "mobile/android/app/build.gradle.kts").read_text(encoding="utf-8")
    root = (ROOT / "mobile/android/build.gradle.kts").read_text(encoding="utf-8")
    workflow = (ROOT / ".github/workflows/ci-cd.yml").read_text(encoding="utf-8")
    assert "compileSdk = 37" in app
    assert 'androidx.core:core:1.19.1' in app
    assert 'onnxruntime-android:1.30.0' in app
    assert 'version "9.1.1"' in root
    assert "gradle-version: '9.3.1'" in workflow
    assert 'sdkmanager "platforms;android-37.0" "build-tools;37.0.0"' in workflow
