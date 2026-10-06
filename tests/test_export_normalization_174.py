from pathlib import Path


def test_render_mix_normalization_uses_peak_analysis(tmp_path, monkeypatch):
    from app import audio_engine as engine
    from app.models import Project, Track

    source = tmp_path / "source.wav"
    source.write_bytes(b"x")
    out = tmp_path / "mix.mp3"
    project = Project(id="p", title="x", tracks=[Track(id="t", name="T", filename="source.wav", duration_ms=1000)])
    calls = []

    def fake_run(cmd):
        calls.append(list(cmd))
        target = Path(cmd[-1]) if cmd and not str(cmd[-1]).startswith("-") else None
        if target and target.suffix in {".wav", ".mp3"}:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(b"audio")
        return ""

    class Proc:
        returncode = 0
        stdout = ""
        stderr = "[Parsed_volumedetect] max_volume: -5.0 dB\n"

    monkeypatch.setattr(engine, "_run", fake_run)
    monkeypatch.setattr(engine.subprocess, "run", lambda *a, **k: Proc())
    engine.render_mix(project, lambda _pid, _name: source, out, fmt="mp3", normalize_peak_db=-1.0)
    assert any(any("volume=4.0000dB" in str(part) for part in cmd) for cmd in calls)
