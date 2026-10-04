from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def test_server_periodic_model_updater_and_platform_endpoints():
    main=(ROOT/'app/main.py').read_text(); up=(ROOT/'app/model_updater.py').read_text()
    assert 'start_background_updater()' in main
    assert '/api/mobile/demucs-onnx/status' in main and '/api/mobile/demucs-coreml/status' in main
    assert 'MTA_DEMUCS_MODEL_UPDATE_INTERVAL_SECONDS' in up and 'SHA-256 mismatch' in up
def test_ios_wifi_only_default_and_periodic_refresh():
    s=(ROOT/'mobile/ios/MTAEditorMobile/MobileWebViewController.swift').read_text()
    assert 'modelUpdatesWifiOnly' in s and 'usesInterfaceType(.wifi)' in s and '21600' in s
    assert 'Update on Wi-Fi only' in s and 'UISwitch' in s
def test_android_wifi_only_and_model_sync():
    s=(ROOT/'mobile/android/app/src/main/java/com/desalvo/mtaaudioeditor/mobile/DemucsModelManager.java').read_text()
    assert 'TRANSPORT_WIFI' in s and 'PERIOD_MS' in s and 'demucs-4.onnx' in s
def test_project_file_contains_new_project_action():
    s=(ROOT/'app/templates/index.html').read_text()
    segment=s[s.index('id="projectToolsBody"'):s.index('</section>',s.index('id="projectToolsBody"'))]
    assert 'onclick="newProject()"' in segment and 'New project' in segment

def test_mobile_release_builds_bundle_default_models():
    ci=(ROOT/'.github/workflows/ci-cd.yml').read_text()
    assert '/api/mobile/demucs-coreml/bootstrap' in ci
    assert 'demucs-default-4.mlmodel' in ci
    assert '/api/mobile/demucs-onnx/bootstrap' in ci
    assert 'demucs-default-4.onnx' in ci
    android=(ROOT/'mobile/android/app/src/main/java/com/desalvo/mtaaudioeditor/mobile/DemucsModelManager.java').read_text()
    assert 'installBundledDefault' in android
