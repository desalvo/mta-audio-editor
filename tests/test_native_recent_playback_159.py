from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = (ROOT / "app/static/app.js").read_text(encoding="utf-8")
NATIVE = (ROOT / "native/mta_audio_editor_native.py").read_text(encoding="utf-8")


def test_native_recent_projects_open_from_bound_archive():
    assert "def list_recent_projects(self)" in NATIVE
    assert "def open_recent_project(self, project_id" in NATIVE
    assert "bridge.list_recent_projects()" in JS
    assert "bridge.open_recent_project(id)" in JS


def test_new_native_project_is_loaded_into_editor_after_creation():
    start = JS.index("async function createProjectFromDialog()")
    end = JS.index("async function openP", start)
    block = JS[start:end]
    assert "current=await api('/api/projects/'+createdId)" in block
    assert "render();" in block
    assert "focusProjectWorkspace();" in block


def test_render_mode_uses_processed_stems_not_parallel_master_and_tracks():
    start = JS.index("async function previewMaster()")
    end = JS.index("function movePlayhead()", start)
    block = JS[start:end]
    assert "renderedStemPlayback=true" in block
    assert "startDynamicTrackPreview(true,false,token)" in block
    assert "/preview-mix?t=" not in block
    assert "startDynamicTrackPreview(true,true" not in block


def test_dynamic_sync_keeps_normal_playback_rate_to_avoid_crackle():
    start = JS.index("function alignDynamicTracks(force=false)")
    end = JS.index("function startDynamicSyncMonitor()", start)
    block = JS[start:end]
    assert "audio.playbackRate=1;" in block
    assert "playbackRate=Math.max" not in block
    assert "if(!force&&!item.needsRelock)continue" in block
    assert "Math.abs(drift)>.060" in block
