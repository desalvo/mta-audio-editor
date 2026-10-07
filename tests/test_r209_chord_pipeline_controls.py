from app.models import Chord
from app.music_text import _normalize_chord_options, _postprocess_chord_events


def c(t, label):
    return Chord(time_ms=t, chord=label)


def test_stable_preset_is_conservative():
    opts = _normalize_chord_options({"preset": "stable"})
    assert opts["sensitivity"] == 25
    assert opts["harmonic_refinement"] is False
    assert opts["detect_slash_bass"] is False
    assert opts["temporal_smoothing"] is True
    assert opts["min_chord_ms"] >= 1500
    assert opts["max_changes_per_minute"] <= 24


def test_raw_preset_preserves_density_and_skips_filters():
    opts = _normalize_chord_options({"preset": "raw"})
    assert opts["temporal_smoothing"] is False
    assert opts["min_chord_ms"] == 0
    assert opts["max_changes_per_minute"] == 0


def test_stable_pipeline_removes_short_chord_chatter_and_slash_bass():
    events = [
        c(0, "C"), c(400, "C/E"), c(800, "G7"), c(1200, "C"),
        c(4000, "Fmaj7"), c(4400, "F/A"), c(8000, "G7"),
    ]
    out = _postprocess_chord_events(events, {"preset": "stable"})
    assert all("/" not in x.chord for x in out)
    assert all("7" not in x.chord for x in out)
    assert len(out) < len(events)


def test_balanced_can_keep_sevenths_but_not_slash_bass():
    events = [c(0, "Cmaj7/E"), c(2500, "G7/B")]
    out = _postprocess_chord_events(events, {"preset": "balanced", "min_chord_ms": 0})
    assert [x.chord for x in out] == ["Cmaj7", "G7"]


def test_detailed_can_keep_slash_bass():
    events = [c(0, "C/E"), c(2500, "G7/B")]
    out = _postprocess_chord_events(events, {"preset": "detailed", "min_chord_ms": 0})
    assert [x.chord for x in out] == ["C/E", "G7/B"]


def test_beat_sync_quantizes_changes_to_project_beat_grid():
    events = [c(0, "C"), c(870, "F"), c(2110, "G")]
    out = _postprocess_chord_events(
        events,
        {"preset": "balanced", "beat_sync": True, "min_chord_ms": 0, "max_changes_per_minute": 0},
        bpm=120,
    )
    assert [x.time_ms for x in out] == [0, 1000, 2000]


def test_density_ceiling_limits_changes_per_minute():
    events = [c(i * 1000, "C" if i % 2 == 0 else "G") for i in range(61)]
    out = _postprocess_chord_events(
        events,
        {"preset": "balanced", "min_chord_ms": 0, "max_changes_per_minute": 12},
    )
    assert len(out) <= 14


def test_native_frozen_chordino_prefers_bundle_and_ignores_stale_builder_env(tmp_path, monkeypatch):
    import os
    import sys
    from app.chordino_runtime import chordino_host_path, configure_chordino_environment, clear_chordino_probe_cache

    contents = tmp_path / 'MTA Audio Editor.app' / 'Contents'
    frameworks = contents / 'Frameworks'
    host_dir = frameworks / 'bin'
    vamp_dir = frameworks / 'vamp'
    host_dir.mkdir(parents=True)
    vamp_dir.mkdir(parents=True)
    host = host_dir / 'vamp-simple-host'
    host.write_text('host')
    (vamp_dir / 'nnls-chroma.dylib').write_text('plugin')

    stale = tmp_path / 'builder' / 'vamp-simple-host'
    stale.parent.mkdir()
    stale.write_text('builder')
    monkeypatch.setattr(sys, 'frozen', True, raising=False)
    monkeypatch.setenv('MTA_CHORDINO_HOST', str(stale))
    monkeypatch.setenv('MTA_VAMP_PATH', str(tmp_path / 'builder-vamp'))
    monkeypatch.setenv('VAMP_PATH', str(tmp_path / 'builder-vamp'))

    configure_chordino_environment(bundle_root=frameworks)
    clear_chordino_probe_cache()
    assert chordino_host_path() == str(host.resolve())
    assert os.environ['MTA_CHORDINO_HOST'] == str(host.resolve())
    assert os.environ['VAMP_PATH'] == str(vamp_dir.resolve())
    assert str(tmp_path / 'builder-vamp') not in os.environ['VAMP_PATH']


def test_macos_native_smoke_drops_build_time_chordino_environment():
    from pathlib import Path
    workflow = Path('.github/workflows/ci-cd.yml').read_text(encoding='utf-8')
    assert '-u MTA_NATIVE_CHORDINO_BIN_DIR' in workflow
    assert '-u MTA_NATIVE_CHORDINO_VAMP_DIR' in workflow
    assert '-u MTA_CHORDINO_HOST' in workflow
    assert '-u MTA_VAMP_PATH' in workflow
    assert '-u VAMP_PATH' in workflow
