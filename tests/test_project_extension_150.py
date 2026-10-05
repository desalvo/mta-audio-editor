from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_project_download_uses_maeproj_extension():
    main = (ROOT / "app/main.py").read_text(encoding="utf-8")
    assert 'return f"{clean}-{project.id}.maeproj"' in main
    assert 'application/vnd.mta-audio-editor.project' in main


def test_native_save_open_and_startup_support_maeproj_and_legacy():
    native = (ROOT / "native/mta_audio_editor_native.py").read_text(encoding="utf-8")
    assert 'PROJECT_EXTENSION = ".maeproj"' in native
    assert 'MTA Audio Editor Project (*.maeproj)' in native
    assert 'Legacy MTA Audio Editor Project (*.zip)' in native
    assert 'def consume_startup_project' in native
    assert 'def _startup_project_path' in native


def test_windows_installer_registers_maeproj_file_association():
    iss = (ROOT / "native/windows-installer.iss").read_text(encoding="utf-8")
    assert 'Software\\Classes\\.maeproj' in iss
    assert 'MTA.AudioEditor.Project' in iss
    assert '%1' in iss


def test_macos_bundle_declares_maeproj_document_type():
    spec = (ROOT / "native/mta_audio_editor_native.spec").read_text(encoding="utf-8")
    assert 'CFBundleDocumentTypes' in spec
    assert 'com.desalvo.mtaaudioeditor.project' in spec
    assert 'maeproj' in spec


def test_mobile_platforms_register_maeproj_type():
    android = (ROOT / "mobile/android/app/src/main/AndroidManifest.xml").read_text(encoding="utf-8")
    ios = (ROOT / "mobile/ios/MTAEditorMobile/Info.plist").read_text(encoding="utf-8")
    assert 'application/vnd.mta-audio-editor.project' in android
    assert 'maeproj' in android
    assert 'CFBundleDocumentTypes' in ios
    assert 'com.desalvo.mtaaudioeditor.project' in ios
