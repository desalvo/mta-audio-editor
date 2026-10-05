from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = (ROOT / "app/static/app.js").read_text(encoding="utf-8")

def test_transport_uses_audio_context_as_authoritative_clock():
    assert "transportClockStartCtx" in JS
    assert "function transportMediaSeconds()" in JS
    align = JS[JS.index("function alignDynamicTracks"):JS.index("function startDynamicSyncMonitor")]
    assert "const ref=transportMediaSeconds()" in align
    assert "const ref=clock.currentTime" not in align

def test_project_open_prewarms_playback_sources():
    block = JS[JS.index("async function openP"):JS.index("function downloadProjectArchive")]
    assert "schedulePlaybackPrewarm(40)" in block
    assert "function prewarmPlaybackSources()" in JS
    assert "audio.preload='auto'" in JS

def test_startup_is_silent_until_first_hard_sync():
    start = JS[JS.index("async function startDynamicTrackPreview"):JS.index("function stopPlayback")]
    assert "startupMuted" in JS
    assert "startTransportClock(playCursorMs)" in start
    assert "alignDynamicTracks(true);releaseStartupMute(items)" in start
    assert "linearRampToValueAtTime(target,now+.008)" in JS

def test_non_render_play_does_not_wait_for_track_fx_render():
    preview = JS[JS.index("async function previewMaster"):JS.index("function movePlayhead")]
    assert "startDynamicTrackPreview(false,false,token)" in preview
    assert "queueInitialTrackFxUpgrades()" in JS
    assert "if((track.inserts||[]).some(x=>x.enabled))" in JS

def test_master_volume_does_not_force_rendered_preview():
    preview = JS[JS.index("async function previewMaster"):JS.index("function movePlayhead")]
    assert "const needsRenderedMaster=!!current.render_preview_enabled;" in preview
    assert "Math.abs(Number(current.master_volume_db" not in preview

def test_live_fx_replacement_is_clock_locked_and_crossfaded():
    block = JS[JS.index("async function refreshDynamicTrackPlayback"):JS.index("function queueLiveFxRefresh")]
    assert "transportMediaSeconds()" in block
    assert "makeTrackPlayback(track,true,false,true,true)" in block
    assert "linearRampToValueAtTime(target,now+.018)" in block
    assert "linearRampToValueAtTime(0,oldNow+.018)" in block
