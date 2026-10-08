from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = (ROOT / 'app/static/app.js').read_text(encoding='utf-8')
NATIVE = (ROOT / 'native/mta_audio_editor_native.py').read_text(encoding='utf-8')
SPEC = (ROOT / 'native/mta_audio_editor_native.spec').read_text(encoding='utf-8')


def test_chords_refresh_preserves_editorial_anchor_state():
    assert 'const editorialState={' in JS
    assert 'result.project.chords=editorialState.chords' in JS
    assert 'result.project.lyrics=editorialState.lyrics' in JS
    assert 'result.project.markers=editorialState.markers' in JS


def test_all_configured_exports_use_progress_jobs():
    start = JS.index('async function executeConfiguredExport(config,slots=[])')
    end = JS.index('function openExportMapping', start)
    body = JS[start:end]
    assert '/configured-export-jobs' in body
    assert "showMediaProgress('Export progetto'" in body
    assert "pollMediaJob(job.id,'Export progetto'" in body
    assert '/configured-export`' not in body


def test_karaoke_export_shows_progress_and_supports_native_mp4_save():
    start = JS.index('async function startKaraokeExport()')
    end = JS.index('async function recalculateBpmFromTrack', start)
    body = JS[start:end]
    assert "showMediaProgress('Export MP4 Karaoke',2" in body
    assert "choose_export_save_path" in body
    assert "'mp4'" in body
    assert '/karaoke-export-jobs' in body
    assert 'downloadWithProgress' in body


def test_native_export_bridge_accepts_mp4_and_zip():
    assert '"zip", "mp4"' in NATIVE
    assert '"zip": "ZIP Archive (*.zip)"' in NATIVE
    assert '"mp4": "MP4 Video (*.mp4)"' in NATIVE


def test_macos_bundle_uses_argv_emulation_for_finder_open_file_events():
    assert 'argv_emulation=(sys.platform == "darwin")' in SPEC
    assert 'CFBundleDocumentTypes' in SPEC
    assert 'maeprojz' in SPEC
