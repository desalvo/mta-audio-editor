from pathlib import Path

import app.main as main


def test_ui_exposes_second_pass_backing_vocals():
    js = Path("app/static/app.js").read_text(encoding="utf-8")
    assert 'id="stemSplitBackingVocals"' in js
    assert 'split_backing_vocals=${splitBackingVocals}' in js
    assert "execution='server'" in js


def test_backend_accepts_and_tracks_backing_vocals_option():
    source = Path("app/main.py").read_text(encoding="utf-8")
    assert "split_backing_vocals: bool = False" in source
    assert 'job.get("split_backing_vocals")' in source
    assert '"vocal_split_method": job.get("vocal_split_method")' in source
    assert '"Lead Vocals"' in source
    assert '"Backing Vocals"' in source


def test_configured_ai_separator_uses_no_shell(monkeypatch, tmp_path):
    src = tmp_path / "vocals.wav"
    src.write_bytes(b"RIFF")
    monkeypatch.setenv("MTA_LEAD_BACKING_COMMAND", "fake-separator --input {input} --lead {lead} --backing {backing}")
    monkeypatch.setenv("MTA_LEAD_BACKING_MODEL", "karaoke-ai")

    class Proc:
        returncode = 0
        stdout = None
        def poll(self):
            return 0

    def fake_popen(command, **kwargs):
        assert isinstance(command, list)
        assert kwargs.get("stdout") is not None
        lead = Path(command[command.index("--lead") + 1])
        backing = Path(command[command.index("--backing") + 1])
        lead.write_bytes(b"lead")
        backing.write_bytes(b"backing")
        return Proc()

    monkeypatch.setattr(main.subprocess, "Popen", fake_popen)
    lead, backing, method = main._split_lead_backing_vocals(src, tmp_path / "out")
    assert lead.exists() and backing.exists()
    assert method == "karaoke-ai"


def test_ffmpeg_fallback_builds_center_side_outputs(monkeypatch, tmp_path):
    src = tmp_path / "vocals.wav"
    src.write_bytes(b"RIFF")
    monkeypatch.delenv("MTA_LEAD_BACKING_COMMAND", raising=False)
    monkeypatch.setattr(main.shutil, "which", lambda name: "/usr/bin/ffmpeg" if name == "ffmpeg" else None)

    class Result:
        returncode = 0
        stderr = ""

    def fake_run(command, **kwargs):
        assert "-filter_complex" in command
        Path(next(x for x in command if str(x).endswith("lead_vocals.wav"))).write_bytes(b"lead")
        Path(next(x for x in command if str(x).endswith("backing_vocals.wav"))).write_bytes(b"backing")
        return Result()

    monkeypatch.setattr(main.subprocess, "run", fake_run)
    lead, backing, method = main._split_lead_backing_vocals(src, tmp_path / "out", model_id="ffmpeg-center-side")
    assert lead.exists() and backing.exists()
    assert method == "ffmpeg-center-side"
