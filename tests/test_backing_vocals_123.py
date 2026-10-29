from pathlib import Path
import pytest

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


def test_configured_ai_separator_without_checkpoint_contract_is_denied(monkeypatch, tmp_path):
    # Exercise the local desktop branch. Server calls require a global job.
    monkeypatch.setattr(main,'NATIVE_SINGLE_USER',True)
    monkeypatch.setattr('app.native_ai_routing.is_remote',lambda kind:False)
    src = tmp_path / "vocals.wav"
    src.write_bytes(b"RIFF")
    monkeypatch.setenv("MTA_LEAD_BACKING_COMMAND", "fake-separator --input {input} --lead {lead} --backing {backing}")
    monkeypatch.setenv("MTA_LEAD_BACKING_MODEL", "karaoke-ai")

    from app.model_license_policy import LicenseDenied
    monkeypatch.setattr(main.subprocess, 'Popen', lambda *a, **kw: pytest.fail('Unreviewed command spawned'))
    with pytest.raises(LicenseDenied, match='checkpoint rights contract'):
        main._split_lead_backing_vocals(src, tmp_path / 'out')
    assert not (tmp_path / 'out').exists()


def test_ffmpeg_fallback_builds_center_side_outputs(monkeypatch, tmp_path):
    monkeypatch.setattr(main,'NATIVE_SINGLE_USER',True)
    monkeypatch.setattr('app.native_ai_routing.is_remote',lambda kind:False)
    src = tmp_path / "vocals.wav"
    src.write_bytes(b"RIFF")
    monkeypatch.delenv("MTA_LEAD_BACKING_COMMAND", raising=False)
    monkeypatch.setattr(main.shutil, "which", lambda name: "/usr/bin/ffmpeg" if name == "ffmpeg" else None)

    def fake_run(command, **kwargs):
        assert "-filter_complex" in command
        assert kwargs['own_session'] is False
        Path(next(x for x in command if str(x).endswith("lead_vocals.wav"))).write_bytes(b"lead")
        Path(next(x for x in command if str(x).endswith("backing_vocals.wav"))).write_bytes(b"backing")

    monkeypatch.setattr('app.separator_process.run', fake_run)
    lead, backing, method = main._split_lead_backing_vocals(src, tmp_path / "out", model_id="ffmpeg-center-side")
    assert lead.exists() and backing.exists()
    assert method == "ffmpeg-center-side"
