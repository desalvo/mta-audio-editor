from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_native_project_dialog_uses_pywebview_valid_zip_filter():
    text = (ROOT / "native/mta_audio_editor_native.py").read_text(encoding="utf-8")
    assert 'MTA Audio Editor Project (*.zip)' in text
    assert 'MTA Audio Editor Project (*.mta-project.zip)' not in text
    assert 'MTA Audio Editor Project (*.mta-project.zip;*.zip)' not in text
    assert 'safe_name += ".mta-project.zip"' in text


def test_utility_backdrop_does_not_close_on_incidental_clicks():
    text = (ROOT / "app/templates/index.html").read_text(encoding="utf-8")
    assert 'id="utilityBackdrop" class="utility-backdrop hidden"' in text
    assert 'event.target===this)closeUtilityModal()' not in text


def test_dynamic_playback_uses_adaptive_buffer_and_smooth_drift_correction():
    text = (ROOT / "app/static/app.js").read_text(encoding="utf-8")
    assert "if(audio.readyState>=3)return Promise.resolve()" in text
    assert "audio.addEventListener('canplay',finish" in text
    assert "audio.addEventListener('canplaythrough'" not in text[text.index("function waitForMediaBuffer"):text.index("function stopDynamicSyncMonitor")]
    assert "audio.playbackRate=Math.max(.985,Math.min(1.015,1-drift*.20))" in text
    assert "Math.abs(drift)>0.120" in text
    assert "setInterval(()=>alignDynamicTracks(false),50)" in text


def test_live_mixer_controls_are_not_buffer_gated():
    text = (ROOT / "app/static/app.js").read_text(encoding="utf-8")
    gains = text[text.index("function updatePlaybackGains"):text.index("function refreshRenderedMasterForMixState")]
    assert "cancelScheduledValues(now)" in gains
    assert "setValueAtTime(playbackGainForTrack(track,item),now)" in gains
    pan = text[text.index("function setTrackPan"):text.index("function bindTrackTimelineScroll")]
    assert "panner.pan.cancelScheduledValues(now)" in pan
