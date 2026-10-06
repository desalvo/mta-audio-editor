from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = (ROOT / "app/static/app.js").read_text(encoding="utf-8")
CSS = (ROOT / "app/static/app.css").read_text(encoding="utf-8")


def test_render_preview_uses_processed_stems_with_realtime_meters():
    render_block = JS[JS.index("async function previewMaster()") : JS.index("function movePlayhead()") ]
    assert "renderedStemPlayback=true" in render_block
    assert "startDynamicTrackPreview(true,false,token)" in render_block
    assert "startDynamicTrackPreview" in JS and "startVuMeterLoop()" in JS


def test_mixer_channels_scroll_inside_viewport_instead_of_escaping():
    assert ".mixer-dock .mixer-pane{min-width:0;max-width:100%;overflow-x:auto!important" in CSS
    assert ".mixer-dock .channels{display:flex;flex-wrap:nowrap" in CSS
    assert "width:max-content;min-width:100%" in CSS
    assert ".mixer-dock .channel{flex:0 0 78px" in CSS
    assert ".mixer-dock .channel.master{flex:0 0 88px" in CSS
