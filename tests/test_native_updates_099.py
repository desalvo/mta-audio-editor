from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_desktop_native_update_channel_and_github_sources():
    native = (ROOT / "native/mta_audio_editor_native.py").read_text(encoding="utf-8")
    updater = (ROOT / "native/update_manager.py").read_text(encoding="utf-8")
    js = (ROOT / "app/static/app.js").read_text(encoding="utf-8")
    assert "update_channel" in native
    assert "check_for_updates" in native
    assert "install_update" in native
    assert "releases/latest" in updater
    assert "releases/tags/early-main" in updater
    assert "Stable · GitHub tags/releases only" in js
    assert "Early release · include latest main packages" in js


def test_android_updater_supports_stable_early_and_apk_install():
    main = (ROOT / "mobile/android/app/src/main/java/com/desalvo/mtaaudioeditor/mobile/MainActivity.java").read_text(encoding="utf-8")
    updater = (ROOT / "mobile/android/app/src/main/java/com/desalvo/mtaaudioeditor/mobile/GitHubUpdateManager.java").read_text(encoding="utf-8")
    manifest = (ROOT / "mobile/android/app/src/main/AndroidManifest.xml").read_text(encoding="utf-8")
    assert "PREF_UPDATE_CHANNEL" in main
    assert "Early release" in main
    assert "releases/latest" in updater
    assert "releases/tags/early-main" in updater
    assert "application/vnd.android.package-archive" in updater
    assert "REQUEST_INSTALL_PACKAGES" in manifest


def test_ios_updater_and_default_demucs_bootstrap():
    controller = (ROOT / "mobile/ios/MTAEditorMobile/MobileWebViewController.swift").read_text(encoding="utf-8")
    updater = (ROOT / "mobile/ios/MTAEditorMobile/NativeUpdateManager.swift").read_text(encoding="utf-8")
    engine = (ROOT / "mobile/ios/MTAEditorMobile/LocalStemEngine.swift").read_text(encoding="utf-8")
    project = (ROOT / "mobile/ios/MTAEditorMobile.xcodeproj/project.pbxproj").read_text(encoding="utf-8")
    assert "bootstrapDefaultCoreMLModelIfNeeded" in controller
    assert "/api/mobile/demucs-coreml/bootstrap" in controller
    assert "refreshCoreMLModelsIfNeeded" in controller
    assert "modelFingerprint" in engine
    assert "demucs-default-4" in engine
    assert "releases/latest" in updater
    assert "releases/tags/early-main" in updater
    assert "NativeUpdateManager.swift in Sources" in project
    assert "Models in Resources" in project


def test_ci_publishes_rolling_early_main_packages():
    workflow = (ROOT / ".github/workflows/ci-cd.yml").read_text(encoding="utf-8")
    assert "Publish rolling early-main packages" in workflow
    assert "early-update.json" in workflow
    assert "gh release upload early-main" in workflow
    assert ":app:assembleRelease" in workflow


def test_coreml_status_exposes_fingerprints_and_authenticated_default(tmp_path, monkeypatch):
    monkeypatch.setenv("MTA_ALLOW_INSECURE_NO_AUTH", "true")
    from fastapi.testclient import TestClient
    import app.main as main

    payload = b"coreml-default-model-v2"
    (tmp_path / "demucs-4.mlmodel").write_bytes(payload)
    monkeypatch.setattr(main, "COREML_DEMUCS_MODEL_DIR", tmp_path)
    client = TestClient(main.app)

    status = client.get("/api/mobile/demucs-coreml/status")
    assert status.status_code == 200
    data = status.json()
    assert data["default_stem_count"] == 4
    assert data["models"]["4"]["sha256"]
    assert data["models"]["4"]["size"] == len(payload)

    bootstrap = client.get("/api/mobile/demucs-coreml/bootstrap")
    assert bootstrap.status_code == 200
    assert bootstrap.content == payload
    assert bootstrap.headers["x-mta-model-sha256"] == data["models"]["4"]["sha256"]
