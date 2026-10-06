from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_native_project_dialog_uses_maeproj_filter_and_legacy_open_filter():
    text = (ROOT / "native/mta_audio_editor_native.py").read_text(encoding="utf-8")
    assert 'PROJECT_EXTENSION = ".maeproj"' in text
    assert 'MTA Audio Editor Project (*.maeproj)' in text
    assert 'Legacy MTA Audio Editor Project (*.zip)' in text
    assert 'safe_name += PROJECT_EXTENSION' in text


def test_utility_backdrop_does_not_close_on_incidental_clicks():
    text = (ROOT / "app/templates/index.html").read_text(encoding="utf-8")
    assert 'id="utilityBackdrop" class="utility-backdrop hidden"' in text
    assert 'event.target===this)closeUtilityModal()' not in text


def test_dynamic_playback_uses_adaptive_buffer_and_smooth_drift_correction():
    text = (ROOT / "app/static/app.js").read_text(encoding="utf-8")
    buffer_block = text[text.index("function waitForMediaBuffer"):text.index("function stopDynamicSyncMonitor")]
    assert "audio.buffered.end(i)-pos>=Math.min(.40" in buffer_block
    assert "audio.readyState<2" in buffer_block
    assert "audio.addEventListener('canplay',check)" in buffer_block
    assert "audio.addEventListener('progress',check)" in buffer_block
    assert "if(audio.readyState<2||audio.seeking)continue" in text
    assert "addEventListener('waiting',mark)" in text
    assert "audio.playbackRate=1" in text
    assert "Math.abs(drift)>.060" in text
    assert "dynamicSyncTimer=setInterval" not in text
    assert "transportMediaSeconds()" in text


def test_live_mixer_controls_are_not_buffer_gated():
    text = (ROOT / "app/static/app.js").read_text(encoding="utf-8")
    gains = text[text.index("function updatePlaybackGains"):text.index("function refreshRenderedMasterForMixState")]
    assert "cancelScheduledValues(now)" in gains
    assert "setValueAtTime(playbackGainForTrack(track,item),now)" in gains
    pan = text[text.index("function setTrackPan"):text.index("function bindTrackTimelineScroll")]
    assert "panner.pan.cancelScheduledValues(now)" in pan
