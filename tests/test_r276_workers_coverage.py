"""Exercise real audio worker framing/decoding and defensive branches in CI."""
from __future__ import annotations
import sys
import types
import numpy as np
import pytest
import soundfile as sf
from app import drumsep_onnx_worker as dw


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
    from model_rights_fixtures import authorize_fixture
    authorize_fixture(monkeypatch,tmp_path,'drumsep-weights')
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
    monkeypatch.setitem(sys.modules, "onnxruntime", types.SimpleNamespace(InferenceSession=Session,get_available_providers=lambda:["CPUExecutionProvider"]))
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
    from model_rights_fixtures import authorize_fixture
    authorize_fixture(monkeypatch,tmp_path,'drumsep-weights')
    _small_window(monkeypatch)
    class Named:
        def __init__(self, name): self.name = name
    class InvalidSession:
        def __init__(self, *args, **kwargs): pass
        def get_inputs(self): return [Named("wrong")]
        def get_outputs(self): return [Named("time_out")]
    monkeypatch.setitem(sys.modules, "onnxruntime", types.SimpleNamespace(InferenceSession=InvalidSession,get_available_providers=lambda:["CPUExecutionProvider"]))
    src = tmp_path / "input.wav"
    sf.write(src, np.zeros((32, 3), dtype="float32"), 16000)
    with pytest.raises(RuntimeError, match="signature"):
        dw.infer(src, tmp_path / "mock.onnx", tmp_path / "out")
    sf.write(src, np.zeros((0, 2), dtype="float32"), 8000)
    with pytest.raises(ValueError, match="Empty drums"):
        dw.infer(src, tmp_path / "mock.onnx", tmp_path / "out")


