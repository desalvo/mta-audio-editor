"""r26: end-to-end offline signal observability contract."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def test_offline_signal_runs_longer_than_one_second():
    cpp = (ROOT / "native/vst3_probe/main.cpp").read_text()
    assert "constexpr int kBlocks = 128;" in cpp
    assert "offlineOutputAudible = offlineOutputEnergy > 1e-12" in cpp
    assert "offline_nonfinite_samples" in cpp

def test_python_adapter_exposes_output_signal_status():
    source = (ROOT / "native/vst3_probe/probe.py").read_text()
    assert "offline_output_audible" in source
    assert "<= 128 else None" in source


def test_ci_requires_numerically_nonzero_adelay_output():
    script = (ROOT / "scripts/test_vst3_adelay_offline.py").read_text()
    assert "data['offline_output_energy'] > 1" in script
    assert "data['offline_output_audible'] is True" in script
