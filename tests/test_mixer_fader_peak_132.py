from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = (ROOT / "app/static/app.js").read_text(encoding="utf-8")
CSS = (ROOT / "app/static/app.css").read_text(encoding="utf-8")


def test_mixer_fader_has_db_scale_and_double_click_unity_reset():
    assert 'class="db-scale"' in JS
    assert "ondblclick=\"resetTrackVolumeToUnity('${t.id}',event)\"" in JS
    assert 'ondblclick="resetMasterVolumeToUnity(event)"' in JS
    assert "function resetTrackVolumeToUnity(id,event)" in JS
    assert "setTrackVolume(id,0)" in JS
    assert "function resetMasterVolumeToUnity(event)" in JS
    assert "setMasterVolume(0)" in JS


def test_realtime_peak_led_exists_for_tracks_and_master_only_with_realtime_visibility():
    assert 'id="peak-${t.id}" class="peak-led ${current.realtime_meter_enabled?\'\':\'hidden\'}"' in JS
    assert 'id="peak-master" class="peak-led ${current.realtime_meter_enabled?\'\':\'hidden\'}"' in JS
    assert "$$('.meter-realtime,.peak-led').forEach" in JS
    assert "function latchPeak(id,pct){if(pct>=99.5)" in JS
    assert "latchPeak(`#peak-${item.trackId}`" in JS
    assert "latchPeak('#peak-master'" in JS


def test_peak_is_latched_until_meter_reset():
    assert "classList.add('active')" in JS
    assert "$$('.peak-led').forEach(x=>x.classList.remove('active'))" in JS


def test_fader_meter_layout_uses_separate_columns():
    assert "grid-template-columns:34px 25px minmax(14px,auto)" in CSS
    assert ".fader-column{position:relative;width:34px;height:112px" in CSS
    assert ".db-scale{" in CSS
    assert ".meter-stack{" in CSS
    assert ".peak-led.active{" in CSS
