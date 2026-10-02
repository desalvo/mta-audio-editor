from pathlib import Path

from app.models import InsertPlugin, Track
from app.main import _track_waveform_revision


def test_waveform_revision_changes_when_insert_is_enabled_or_disabled(tmp_path):
    source = tmp_path / "audio.wav"
    source.write_bytes(b"abc")
    track = Track(id="t1", name="Track", filename="audio.wav", channels=1)

    base = _track_waveform_revision(track, source)
    track.inserts = [
        InsertPlugin(id="fx1", plugin="amplify", preset="default", enabled=True)
    ]
    enabled = _track_waveform_revision(track, source)
    track.inserts[0].enabled = False
    disabled = _track_waveform_revision(track, source)

    assert enabled != base
    assert disabled != enabled
    assert disabled != base  # state is persisted in the revision as requested


def test_frontend_recalculates_waveform_for_all_track_insert_mutations():
    root = Path(__file__).resolve().parents[1]
    js = (root / "app/static/app.js").read_text(encoding="utf-8")

    assert "function queueInsertWaveformRefresh(trackId)" in js
    assert "waveform-jobs?force=true" in js
    assert "Ricalcolo waveform dopo modifica insert" in js

    # Add, remove, enable/disable, preset and custom config all trigger recalculation.
    assert js.count("queueInsertWaveformRefresh(trackId||selectedTrack()?.id||'')") >= 5


def test_backend_waveform_worker_renders_enabled_inserts():
    root = Path(__file__).resolve().parents[1]
    main = (root / "app/main.py").read_text(encoding="utf-8")
    assert "enabled_inserts = any(item.enabled for item in track.inserts)" in main
    assert "render_track(track, source, rendered, apply_inserts=True)" in main
    assert "_track_waveform_revision(latest_track, source)" in main
