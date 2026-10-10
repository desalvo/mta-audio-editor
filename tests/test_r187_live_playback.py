from pathlib import Path

JS = Path('app/static/app.js').read_text(encoding='utf-8')
MAIN = Path('app/main.py').read_text(encoding='utf-8')


def test_dynamic_playback_has_no_periodic_hard_seek_loop():
    assert 'dynamicSyncTimer=setInterval' not in JS
    move = JS[JS.index('function movePlayhead()'):JS.index('function selectExport', JS.index('function movePlayhead()'))]
    assert 'alignDynamicTracks(false)' not in move
    assert "addEventListener('waiting',mark)" in JS
    assert "addEventListener('stalled',mark)" in JS


def test_render_mode_uses_processed_stems_for_live_mix_controls():
    preview = JS[JS.index('async function previewMaster()'):JS.index('function movePlayhead()', JS.index('async function previewMaster()'))]
    assert 'renderedStemPlayback=true' in preview
    assert 'startDynamicTrackPreview(true,false,token)' in preview
    assert '/preview-mix?' not in preview


def test_preview_stems_keep_mixer_controls_neutral_server_side():
    block = MAIN[MAIN.index('def preview_track('):MAIN.index('@app.get("/api/projects/{pid}/preview-mix")')]
    assert 'preview_track_model.volume_db = 0.0' in block
    assert 'preview_track_model.pan = 0.0' in block
    assert 'preview_track_model.mute = False' in block
    assert 'render_track_export(\n            preview_track_model,' in block


def test_plugin_parameter_controls_schedule_live_updates():
    assert 'function livePluginControlChanged' in JS
    assert 'scheduleLivePluginParamCommit' in JS
    assert 'refreshDynamicTrackPlayback(id)' in JS


def test_revision_metadata_is_consistent():
    rev = int(Path('REVISION').read_text().strip())
    assert rev >= 1
    assert f'versionCode = {30000 + rev}' in Path('mobile/android/app/build.gradle.kts').read_text()
    assert f'<string>{30000 + rev}</string>' in Path('mobile/ios/MTAEditorMobile/Info.plist').read_text()
