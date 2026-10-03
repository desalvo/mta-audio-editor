from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = (ROOT / "app/static/app.js").read_text(encoding="utf-8")
HTML = (ROOT / "app/templates/index.html").read_text(encoding="utf-8")
MODELS = (ROOT / "app/models.py").read_text(encoding="utf-8")
CODEC = (ROOT / "app/codec.py").read_text(encoding="utf-8")
MAIN = (ROOT / "app/main.py").read_text(encoding="utf-8")

def test_transport_has_go_to_start():
    assert 'onclick="goTransportStart()"' in HTML
    assert "function goTransportStart()" in JS

def test_dynamic_playback_buffers_and_realigns():
    assert "function waitForMediaBuffer(" in JS
    assert "Buffering audio… attendere" in JS
    assert "startDynamicSyncMonitor()" in JS
    assert "Math.abs(drift)>0.018" in JS

def test_render_follow_has_dedicated_clock():
    assert "renderedMasterAudio" in JS
    assert "function dynamicClockAudio()" in JS
    assert "if(current?.follow_playback_enabled)followPlayhead" in JS

def test_device_profiles_are_persistent_and_exported():
    assert "mta_device_profile:" in MODELS
    assert "MTA8_DEVICE_LAYOUTS" in CODEC
    assert '"merish5_xynthia2"' in CODEC
    assert '"bbeat_divo"' in CODEC
    assert "resolve_mta_device_profile" in MAIN

def test_profiled_mta8_physically_pads_slots():
    assert "force_full_mta8" in CODEC
    assert "anullsrc=r=44100:cl=stereo" in CODEC
    assert "max_slot = 8 if force_full_mta8" in CODEC

def test_mta16_profile_mapping_ui_present():
    assert "requires_explicit_click_mapping" in MAIN
    assert "Default MTA16:" in JS
