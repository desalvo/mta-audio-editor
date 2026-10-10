"""r20: bounded native VST3 tail diagnostics and Linux matrix compiler checks."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_native_probe_has_bounded_tail_query():
    code = (ROOT / 'native/vst3_probe/main.cpp').read_text(encoding='utf-8')
    assert 'processor->getTailSamples()' in code
    assert 'reportedTail <= 10000000U' in code
    assert 'tail_samples' in code
    assert 'native_host_ready' in code


def test_python_rejects_invalid_tail_metadata():
    code = (ROOT / 'native/vst3_probe/probe.py').read_text(encoding='utf-8')
    assert "type(payload.get('tail_samples')) is int" in code
    assert "0 <= payload['tail_samples'] <= 10000000" in code


def test_linux_matrix_compiles_vst_probe():
    ci = (ROOT / '.github/workflows/ci-cd.yml').read_text(encoding='utf-8')
    section = ci.split('  native-linux:', 1)[1].split('  native-release:', 1)[0]
    assert 'ubuntu-24.04-arm' in section
    assert 'cmake -S native/vst3_probe' in section
    assert 'cmake --build build/vst3_probe' in section
