from pathlib import Path


def test_android_ci_uses_supported_setup_android_action():
    root = Path(__file__).resolve().parents[1]
    workflow = (root / ".github/workflows/ci-cd.yml").read_text(encoding="utf-8")
    assert "android-actions/setup-android@v4" in workflow
    assert "android-actions/setup-android@v3" not in workflow
    assert "actions/setup-java@v6" in workflow
    assert "gradle/actions/setup-gradle@v6" in workflow


def test_ios_open_panel_is_availability_guarded_for_ios_15_target():
    root = Path(__file__).resolve().parents[1]
    swift = (root / "mobile/ios/MTAEditorMobile/MobileWebViewController.swift").read_text(encoding="utf-8")
    assert "@available(iOS 18.4, *)" in swift
    marker = swift.index("@available(iOS 18.4, *)")
    method = swift.index("runOpenPanelWith parameters: WKOpenPanelParameters", marker)
    assert marker < method
