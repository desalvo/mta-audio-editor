from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = (ROOT / "app/static/app.js").read_text()
HTML = (ROOT / "app/templates/index.html").read_text()
MAIN = (ROOT / "app/main.py").read_text()


def test_transport_record_removed_and_play_does_not_wait_for_waveform():
    assert 'aria-label="Record"' not in HTML
    preview = JS[JS.index("async function previewMaster()") : JS.index("function movePlayhead()")]
    assert "ensureWaveforms" not in preview
    assert "waveformJobs" not in preview
    assert "waveform_peaks" not in preview


def test_open_validates_persisted_waveform_revision_and_keeps_cached_draw_fast():
    ensure = JS[JS.index("async function ensureWaveforms()") : JS.index("async function pollWaveformJob")]
    assert "if(t.waveform_peaks?.length)drawWave(t)" in ensure
    assert "/waveform-jobs" in ensure
    assert "if(t.waveform_peaks?.length){drawWave(t);continue}" not in ensure
    assert "track.waveform_revision = _track_waveform_revision(track, dst) if peaks else \"\"" in MAIN


def test_bulk_mute_solo_and_fx_controls_exist():
    for fn in ("toggleMuteAll", "toggleSoloAll", "toggleAllPlugins"):
        assert f"function {fn}()" in JS
    assert "Mute all" in JS and "Unmute all" in JS
    assert "Solo all" in JS and "Unsolo all" in JS
    assert "Bypass all FX" in JS and "Enable all FX" in JS
    assert "queueInsertWaveformRefresh(t.id)" in JS
