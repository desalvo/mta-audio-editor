"""CLI smoke and boundary checks for isolated VST3 WAV export."""
import json
import struct
import wave
from unittest.mock import patch

import pytest

from native.vst3_probe import render_wav_cli
from native.vst3_probe.native_chain import render_native_chain, render_native_wav


def _make_wav(path):
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(48000)
        wav.writeframes(struct.pack("<hhh", 123, -100, 0))


def test_cli_export(tmp_path, capsys):
    source = tmp_path / "in.wav"
    destination = tmp_path / "out.wav"
    _make_wav(source)
    with patch("native.vst3_probe.native_chain.render_native_chain", side_effect=lambda audio, *a, **kw: audio):
        result = render_wav_cli.main([str(source), str(destination), "--probe", "probe",
                                       "--insert", "plugin.vst3", "f" * 32])
    assert result == 0
    report = json.loads(capsys.readouterr().out)
    assert report["frames"] == 3 and report["bit_depth"] == 16
    assert destination.is_file()


def test_cli_failure_preserves_output(tmp_path, capsys):
    source = tmp_path / "in.wav"
    destination = tmp_path / "out.wav"
    _make_wav(source)
    destination.write_bytes(b"old")
    result = render_wav_cli.main([str(source), str(destination), "--probe", "probe",
                                   "--insert", "plugin.vst3", "bad"] )
    assert result == 1
    assert destination.read_bytes() == b"old"
    assert "failed" in capsys.readouterr().err


@pytest.mark.parametrize("timeout", [0, -1, float("inf"), float("nan"), True])
def test_invalid_timeout_rejected(timeout, tmp_path):
    source = tmp_path / "in.wav"
    _make_wav(source)
    with pytest.raises(ValueError, match="Timeout"):
        render_native_wav(source, tmp_path / "out.wav", [("x", "f" * 32)], "probe", timeout=timeout)
    with pytest.raises(ValueError, match="Timeout"):
        render_native_chain([0.1], [("x", "f" * 32)], "probe", timeout=timeout)


def test_no_inserts_preflight(tmp_path):
    source = tmp_path / "in.wav"
    _make_wav(source)
    with pytest.raises(ValueError, match="1..8"):
        render_native_wav(source, tmp_path / "out.wav", [], "probe")
