from pathlib import Path
import plistlib
from defusedxml import ElementTree as ET


def test_android_native_client_files_and_storage_bridge_exist():
    root = Path(__file__).resolve().parents[1]
    android = root / "mobile" / "android"
    assert (android / "settings.gradle.kts").is_file()
    assert (android / "app" / "build.gradle.kts").is_file()
    manifest = android / "app" / "src" / "main" / "AndroidManifest.xml"
    ET.parse(manifest)
    java = (android / "app" / "src" / "main" / "java" / "com" / "desalvo" / "mtaaudioeditor" / "mobile" / "MainActivity.java").read_text(encoding="utf-8")
    for marker in (
        "addJavascriptInterface(new MobileBridge(), \"MtaMobile\")",
        "ACTION_OPEN_DOCUMENT",
        "ACTION_CREATE_DOCUMENT",
        "saveRemoteFile",
        "shareRemoteFile",
        "FLAG_KEEP_SCREEN_ON",
        "CookieManager.getInstance().getCookie",
    ):
        assert marker in java


def test_ios_native_client_files_and_document_bridge_exist():
    root = Path(__file__).resolve().parents[1]
    ios = root / "mobile" / "ios"
    assert (ios / "MTAEditorMobile.xcodeproj" / "project.pbxproj").is_file()
    assert (ios / "MTAEditorMobile.xcodeproj" / "xcshareddata" / "xcschemes" / "MTAEditorMobile.xcscheme").is_file()
    with (ios / "MTAEditorMobile" / "Info.plist").open("rb") as handle:
        info = plistlib.load(handle)
    assert info["CFBundleDisplayName"] == "MTA Audio Editor"
    swift = (ios / "MTAEditorMobile" / "MobileWebViewController.swift").read_text(encoding="utf-8")
    for marker in (
        "WKScriptMessageHandler",
        "UIDocumentPickerViewController",
        "saveRemoteFile",
        "shareRemoteFile",
        "getAllCookies",
        "isIdleTimerDisabled",
    ):
        assert marker in swift


def test_mobile_frontend_bridge_and_server_side_export_jobs_are_integrated():
    root = Path(__file__).resolve().parents[1]
    js = (root / "app" / "static" / "app.js").read_text(encoding="utf-8")
    main = (root / "app" / "main.py").read_text(encoding="utf-8")
    assert "function mobilePlatform()" in js
    assert "function mobileSaveRemoteFile(" in js
    assert "configured-export-jobs" in js
    assert "Condividi…" in js
    assert "@app.post(\"/api/projects/{pid}/configured-export-jobs\")" in main
    assert '"kind": "project-export"' in main
    assert '{"track-export", "project-export"}' in main


def test_ci_builds_android_and_ios_and_publishes_mobile_artifacts():
    root = Path(__file__).resolve().parents[1]
    workflow = (root / ".github" / "workflows" / "ci-cd.yml").read_text(encoding="utf-8")
    for marker in (
        "mobile-android:",
        "mobile-ios:",
        ":app:assembleDebug :app:bundleRelease",
        "MTAEditorMobile.xcarchive",
        "APPSTORE_CONNECT_KEY_ID",
        "pattern: mobile-*",
    ):
        assert marker in workflow
