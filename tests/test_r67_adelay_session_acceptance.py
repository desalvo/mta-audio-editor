"""Keep real-plugin session acceptance in CI and prevent premature realtime claims."""
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]


def test_real_sdk_ci_executes_multi_request_acceptance():
    workflow = (ROOT / '.github/workflows/ci-cd.yml').read_text()
    assert 'python scripts/test_vst3_adelay_session.py' in workflow
    script = (ROOT / 'scripts/test_vst3_adelay_session.py').read_text()
    for fragment in ('(17, 513, 4097, 115536)', '(44100, 48000, 96000)',
                     '(1, 2)', 'render_native_session_chain', 'error < 1e-5'):
        assert fragment in script


def test_readiness_gates_deny_interactive_host_claim():
    cpp = (ROOT / 'native/vst3_probe/main.cpp').read_text()
    assert 'native_host_ready' in cpp and 'false}' in cpp
    checklist = (ROOT / 'native/vst3_probe/READINESS_GATES.md').read_text()
    assert 'interactive worker' in checklist.lower()
    assert 'Audio callback isolation' in checklist
