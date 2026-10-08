from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_desktop_downloader_reports_progress():
    source = (ROOT / 'native/update_manager.py').read_text()
    assert 'progress(received, total)' in source
    assert 'os.replace(staging, target)' in source
    assert 'Incomplete update download' in source


def test_desktop_bridge_polling_is_async():
    source = (ROOT / 'native/mta_audio_editor_native.py').read_text()
    assert 'def update_download_status(self)' in source
    assert 'mta-update-download' in source
    ui = (ROOT / 'app/static/app.js').read_text()
    assert 'nativeUpdateProgressBar' in ui
    assert 'bridge.update_download_status()' in ui


def test_android_download_progress():
    manager = (ROOT / 'mobile/android/app/src/main/java/com/desalvo/mtaaudioeditor/mobile/GitHubUpdateManager.java').read_text()
    activity = (ROOT / 'mobile/android/app/src/main/java/com/desalvo/mtaaudioeditor/mobile/MainActivity.java').read_text()
    assert 'interface ProgressCallback' in manager
    assert 'progress.onProgress(received, total)' in manager
    assert 'downloadDialog.setProgress' in activity
