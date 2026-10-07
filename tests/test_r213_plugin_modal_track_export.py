from pathlib import Path


def test_plugin_setup_modal_stacks_above_inspector_overlay():
    css = Path("app/static/app.css").read_text()
    assert ".utility-backdrop{position:fixed;inset:0;z-index:5000" in css
    assert ".inspector{position:absolute!important" in css
    assert "z-index:180!important" in css
    assert ".utility-modal{position:relative;z-index:1" in css


def test_native_track_export_asks_destination_before_render_job():
    js = Path("app/static/app.js").read_text()
    body = js.split("async function exportTrack(id,format){", 1)[1].split("async function doExport", 1)[0]
    choose = body.index("choose_export_save_path")
    start_job = body.index("track-export-jobs")
    assert choose < start_job
    assert "if(!chosen?.ok)return" in body
    assert "nativeOutputPath=chosen.path||''" in body
    assert "downloadWithProgress(result.download_url" in body
    assert "nativeOutputPath" in body


def test_native_bridge_can_write_preselected_generated_audio_path():
    native = Path("native/mta_audio_editor_native.py").read_text()
    js = Path("app/static/app.js").read_text()
    assert "def save_generated_file_to_path(self, path: str, data_base64: str) -> dict:" in native
    assert '{"wav", "mp3", "flac", "pdf", "txt", "cho", "mta8", "mta16"}' in native
    assert "async function saveGeneratedBlobToNativePath(blob,path)" in js
    assert "save_generated_file_to_path(path,dataUrl)" in js


def test_browser_generated_audio_uses_save_picker_when_available():
    js = Path("app/static/app.js").read_text()
    assert "const saveableExts=['pdf','txt','cho','wav','mp3','flac'];" in js
    assert "wav:'WAV Audio',mp3:'MP3 Audio',flac:'FLAC Audio'" in js


def test_r213_mobile_build_numbers_match_revision():
    rev = int(Path("REVISION").read_text().strip())
    assert f"versionCode = {20000 + rev}" in Path("mobile/android/app/build.gradle.kts").read_text()
    info = Path("mobile/ios/MTAEditorMobile/Info.plist").read_text()
    assert f"<key>CFBundleVersion</key><string>{20000 + rev}</string>" in info
    assert f"<key>MTAEditorRevision</key><string>{rev}</string>" in info
