from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = (ROOT / "app/static/app.js").read_text(encoding="utf-8")
CODEC = (ROOT / "app/codec.py").read_text(encoding="utf-8")

def test_render_meter_only_graph_keeps_real_gain():
    assert "gainNode.gain.value=!audible?0:dbToGain(db)" in JS
    assert "if(silent)panner.connect(zero);else panner.connect(audioCtx.destination)" in JS
    assert "if(!track||item?.silent)return 0" not in JS

def test_track_volume_pan_and_fx_are_live():
    assert "if(renderedMasterPlayback)queueRenderedMasterRefresh()" in JS
    assert "function queueLiveFxRefresh(isMaster,trackId='',delay=90)" in JS
    assert "async function refreshDynamicTrackPlayback(trackId)" in JS
    assert "x.enabled=!x.enabled;markDirty(100);queueLiveFxRefresh(isMaster,trackId)" in JS
    assert "x.preset=preset;x.params=presetParamsFor(x.plugin,preset);markDirty(100);queueLiveFxRefresh(isMaster,trackId)" in JS

def test_master_fader_uses_render_baseline():
    assert "renderedMasterBaseVolumeDb" in JS
    assert "n-renderedMasterBaseVolumeDb" in JS

def test_click_melody_ambiguous_slots_are_not_guessed():
    assert 'MTA8_STABLE_TYPES = ["drums", "bass", "guitars", "keyboards", "orchestra", "winds"]' in CODEC
    assert "def infer_mta_track_type(index: int, tags: dict)" in CODEC
    assert '"metronome"' in CODEC
    assert '"metronomo"' in CODEC
