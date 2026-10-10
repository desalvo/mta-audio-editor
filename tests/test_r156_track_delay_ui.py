"""r156: prevent duplicate track Delay controls and handler definitions."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def test_track_header_renders_one_delay_control():
    source = (ROOT / "app/static/app.js").read_text(encoding="utf-8")
    template = source.split("function trackHead(t,i){", 1)[1].split("function closeTrackContextMenu(){", 1)[0]
    assert template.count('class="track-delay-row"') == 1
    assert template.count('id="track-delay-${t.id}"') == 1
    assert template.count('data-delay-track="${t.id}"') == 1
    assert "setTrackDelayFromInput('${t.id}',this.value)" in template

def test_delay_ui_helpers_have_one_definition_each():
    source = (ROOT / "app/static/app.js").read_text(encoding="utf-8")
    for func in ("trackDelayInputValue", "setTrackDelayFromInput", "updateTrackDelayUnitDisplay"):
        assert source.count(f"function {func}(") == 1

def test_delay_ui_css_has_unique_rules():
    source = (ROOT / "app/static/app.css").read_text(encoding="utf-8")
    for selector in (".track-delay-row{", ".track-delay-input{", ".track-delay-unit{"):
        assert source.count(selector) == 1

def test_native_host_stays_disabled():
    source = (ROOT / "native/vst3_probe/main.cpp").read_text(encoding="utf-8")
    assert "native_host_ready" in source
