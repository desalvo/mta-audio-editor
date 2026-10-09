"""Exercise real audio worker framing/decoding and defensive branches in CI."""
from __future__ import annotations
import sys
import types
from pathlib import Path
import numpy as np
import pytest
import soundfile as sf
from app import drumsep_onnx_worker as dw
from app import main


def _small_window(monkeypatch):
    for name, value in {"SAMPLE_RATE": 8000, "WINDOW": 64, "HOP": 32,
                        "NFFT": 16, "FFT_HOP": 4, "FRAMES": 17}.items():
        monkeypatch.setattr(dw, name, value)


def test_drumsep_small_real_stft_and_inverse(monkeypatch):
    _small_window(monkeypatch)
    clip = np.zeros((2, 64), dtype="float32")
    clip[0, 11] = 0.5
    mag = dw.stft_features(clip)
    assert mag.shape == (1, 4, 8, 17)
    result = dw.reconstruct_frequency(np.zeros((1, 4, 4, 8, 17), dtype="float32"))
    assert result.shape == (4, 2, 64)
    assert np.allclose(result, 0)
    with pytest.raises(RuntimeError, match="freq_out shape"):
        dw.reconstruct_frequency(np.zeros((1, 4, 4, 8, 16)))
    with pytest.raises(RuntimeError, match="STFT dimensions"):
        dw.stft_features(np.zeros((2, 32), dtype="float32"))


def test_drumsep_worker_end_to_end_small_onnx(monkeypatch, tmp_path):
    _small_window(monkeypatch)
    calls = []
    class Named:
        def __init__(self, name): self.name = name
    class Session:
        def __init__(self, path, providers):
            assert providers == ["CPUExecutionProvider"]
            calls.append(path)
        def get_inputs(self): return [Named("mix"), Named("mag")]
        def get_outputs(self): return [Named("time_out"), Named("freq_out")]
        def run(self, unused, feeds):
            assert feeds["mix"].shape == (1, 2, 64)
            assert feeds["mag"].shape == (1, 4, 8, 17)
            return [np.ones((1, 4, 2, 64), dtype="float32") * 0.1,
                    np.zeros((1, 4, 4, 8, 17), dtype="float32")]
    monkeypatch.setitem(sys.modules, "onnxruntime", types.SimpleNamespace(InferenceSession=Session))
    wav = tmp_path / "input.wav"
    sf.write(wav, np.zeros((90, 1), dtype="float32"), 8000)
    outputs = dw.infer(wav, tmp_path / "mock.onnx", tmp_path / "out")
    assert len(calls) == 1
    assert {p.stem for p in outputs} == set(dw.STEMS)
    for output in outputs:
        samples, rate = sf.read(output, always_2d=True)
        assert samples.shape == (90, 2) and rate == 8000
        assert np.isfinite(samples).all()
        assert np.mean(samples) == pytest.approx(0.1, abs=0.005)


def test_drumsep_worker_resample_and_validation(monkeypatch, tmp_path):
    _small_window(monkeypatch)
    class Named:
        def __init__(self, name): self.name = name
    class InvalidSession:
        def __init__(self, *args, **kwargs): pass
        def get_inputs(self): return [Named("wrong")]
        def get_outputs(self): return [Named("time_out")]
    monkeypatch.setitem(sys.modules, "onnxruntime", types.SimpleNamespace(InferenceSession=InvalidSession))
    src = tmp_path / "input.wav"
    sf.write(src, np.zeros((32, 3), dtype="float32"), 16000)
    with pytest.raises(RuntimeError, match="signature"):
        dw.infer(src, tmp_path / "mock.onnx", tmp_path / "out")
    sf.write(src, np.zeros((0, 2), dtype="float32"), 8000)
    with pytest.raises(ValueError, match="Empty drums"):
        dw.infer(src, tmp_path / "mock.onnx", tmp_path / "out")


def test_sam_audio_adapter_validation_and_subprocess(monkeypatch, tmp_path):
    with pytest.raises(ValueError, match="Unsupported"):
        main._sam_audio_extract(tmp_path / "input.wav", tmp_path / "out", "bogus", "kick")
    monkeypatch.delenv("MTA_SAM_AUDIO_PYTHON", raising=False)
    with pytest.raises(RuntimeError, match="MTA_SAM_AUDIO_PYTHON"):
        main._sam_audio_extract(tmp_path / "input.wav", tmp_path / "out", "sam-audio-small", "kick")
    monkeypatch.setenv("MTA_SAM_AUDIO_PYTHON", sys.executable)
    def good_run(argv, **kwargs):
        assert "--prompt" in argv
        destination = Path(argv[argv.index("--output") + 1]); destination.write_bytes(b"RIFF" + b"0" * 90)
        return types.SimpleNamespace(returncode=0, stderr="", stdout="")
    monkeypatch.setattr(main.subprocess, "run", good_run)
    output = main._sam_audio_extract(tmp_path / "input.wav", tmp_path / "out", "sam-audio-small", "kick")
    assert output.name == "kick.wav"
    monkeypatch.setattr(main.subprocess, "run", lambda *a, **k: types.SimpleNamespace(returncode=2, stderr="inference error", stdout=""))
    with pytest.raises(RuntimeError, match="inference error"):
        main._sam_audio_extract(tmp_path / "input.wav", tmp_path / "out2", "sam-audio-small", "snare")


def test_sam_audio_worker_temporal_anchor_cli(monkeypatch, tmp_path):
    """Use mocked checkpoint APIs but execute the actual SAM command-line adapter."""
    from app import sam_audio_worker as sw
    from contextlib import nullcontext
    saved = []
    processed = []
    class FakeTensor:
        ndim = 3
        shape = (1, 2, 8)
        def detach(self): return self
        def cpu(self): return self
        def __getitem__(self, item): return self
    class FakeModel:
        @classmethod
        def from_pretrained(cls, model):
            assert model == "facebook/sam-audio-small"
            return cls()
        def eval(self): return self
        def to(self, device): return self
        def separate(self, batch, **kwargs):
            assert kwargs["predict_spans"] is False
            return types.SimpleNamespace(target=FakeTensor())
    class FakeProcessor:
        audio_sampling_rate = 48000
        @classmethod
        def from_pretrained(cls, model): return cls()
        def __call__(self, **kwargs):
            processed.append(kwargs)
            return self
        def to(self, device): return self
    monkeypatch.setitem(sys.modules, "torch", types.SimpleNamespace(cuda=types.SimpleNamespace(is_available=lambda:False), inference_mode=nullcontext))
    monkeypatch.setitem(sys.modules, "torchaudio", types.SimpleNamespace(save=lambda *args:saved.append(args)))
    monkeypatch.setitem(sys.modules, "sam_audio", types.SimpleNamespace(SAMAudio=FakeModel,SAMAudioProcessor=FakeProcessor))
    path = tmp_path / "singer.wav"
    monkeypatch.setattr(sys, "argv", ["worker", "--source", "in.wav", "--output", str(path),
             "--model", "facebook/sam-audio-small", "--prompt", "singing voice",
             "--anchors-json", '[["+",1.0,3.0],["-",4.0,6.0]]'])
    sw.main()
    assert processed[0]["anchors"] == [[['+',1.0,3.0],['-',4.0,6.0]]]
    assert saved[0][0] == str(path) and saved[0][2] == 48000
    monkeypatch.setattr(sys, "argv", ["worker", "--source", "in.wav", "--output", str(path),
             "--model", "facebook/sam-audio-small", "--prompt", "singing voice",
             "--anchors-json", '[["*",1.0,3.0]]'])
    with pytest.raises(ValueError, match="temporal anchors"):
        sw.main()
