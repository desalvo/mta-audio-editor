from pathlib import Path


def test_windows_registers_portable_as_primary_and_keeps_legacy():
    installer = Path("native/windows-installer.iss").read_text(encoding="utf-8")
    assert 'Software\\Classes\\.maeprojz' in installer
    assert 'MTA.AudioEditor.PortableProject' in installer
    assert 'Portable MTA Audio Editor Project' in installer
    assert 'application/vnd.mta-audio-editor.portable-project' in installer
    assert 'Software\\Classes\\.maeproj' in installer


def test_macos_registers_portable_uti_and_legacy_project():
    spec = Path("native/mta_audio_editor_native.spec").read_text(encoding="utf-8")
    assert 'com.desalvo.mtaaudioeditor.portable-project' in spec
    assert '"CFBundleTypeExtensions": ["maeprojz"]' in spec
    assert 'application/vnd.mta-audio-editor.portable-project' in spec
    assert '"CFBundleTypeExtensions": ["maeproj"]' in spec


def test_mobile_registers_portable_extension_and_mime():
    plist = Path("mobile/ios/MTAEditorMobile/Info.plist").read_text(encoding="utf-8")
    android = Path("mobile/android/app/src/main/AndroidManifest.xml").read_text(encoding="utf-8")
    assert 'com.desalvo.mtaaudioeditor.portable-project' in plist
    assert '<string>maeprojz</string>' in plist
    assert 'application/vnd.mta-audio-editor.portable-project' in plist
    assert '.*\\.maeprojz' in android
    assert 'application/vnd.mta-audio-editor.portable-project' in android
