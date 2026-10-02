from pathlib import Path


def test_stop_invalidates_meter_loop_and_forces_zero():
    root = Path(__file__).resolve().parents[1]
    js = (root / "app/static/app.js").read_text(encoding="utf-8")
    assert "meterRunToken++" in js
    assert "cancelAnimationFrame(meterRaf)" in js
    assert "resetVuMeters();" in js
    assert "requestAnimationFrame(resetVuMeters)" in js
    assert "playbackActuallyRunning()" in js
    assert "if(!current?.realtime_meter_enabled||!playbackActuallyRunning())" in js
    assert "if(!playbackActuallyRunning())resetVuMeters()" in js
