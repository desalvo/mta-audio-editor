from pathlib import Path


def test_mixer_uses_one_vu_for_mono_and_independent_lr_for_stereo_and_master():
    root = Path(__file__).resolve().parents[1]
    js = (root / "app/static/app.js").read_text(encoding="utf-8")
    css = (root / "app/static/app.css").read_text(encoding="utf-8")

    assert "effectiveTrackChannels(track)" in js or "Number(track.channels)===1?1:2" in js
    assert "createChannelSplitter(2)" in js
    assert "splitter.connect(left,0)" in js
    assert "splitter.connect(right,1)" in js

    assert 'id="vu-${t.id}-M"' in js
    assert 'id="vu-${t.id}-L"' in js
    assert 'id="vu-${t.id}-R"' in js
    assert 'id="vu-master-L"' in js
    assert 'id="vu-master-R"' in js

    assert "createChannelSplitter(2)" in js
    assert "masterMeterAnalysers" in js
    assert "masterLeftEnergy" in js and "masterRightEnergy" in js
    assert ".master-meter-pair" in css


def test_follow_updates_timeline_scroll_from_playhead():
    root = Path(__file__).resolve().parents[1]
    js = (root / "app/static/app.js").read_text(encoding="utf-8")

    start = js.index("function movePlayhead")
    end = js.index("function selectExport", start)
    block = js[start:end]
    assert "const playheadX=" in block
    assert "followPlayhead(playheadX)" in block
