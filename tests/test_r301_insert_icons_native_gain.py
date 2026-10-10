from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def test_plugin_categories_have_specific_icons():
    js = (ROOT / "app/static/app.js").read_text()
    for theme in ("eq", "dynamics", "space", "delay", "saturation", "modulation", "studio", "vst3"):
        assert f"{theme}:`" in js
    assert "insertSetupIcon(theme)" in js
    assert "insertSetupIcon('vst3')" in js

def test_native_gain_is_opt_in_and_validated():
    cpp = (ROOT / "native/audio_core/audio_core.cpp").read_text()
    assert "mta_pcm_gain" in cpp
    assert "!std::isfinite(pcm[i])" in cpp
    assert "!std::isfinite(gain)" in cpp


def test_gain_portable_semantics():
    from app import native_dsp
    assert native_dsp.pcm_gain([0.5, -0.5, 0.0, 1.0], 2.0, channels=2) == [1.0, -1.0, 0.0, 2.0]
    import pytest
    with pytest.raises(ValueError):
        native_dsp.pcm_gain([0.2], float('nan'))
    with pytest.raises(ValueError):
        native_dsp.pcm_gain([0.2], 2, channels=2)
