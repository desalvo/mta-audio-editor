from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_torchvision_version_matches_native_torch_stack():
    intel = (ROOT / "requirements-stems-macos-x64.txt").read_text()
    win = (ROOT / "requirements-stems-windows.txt").read_text()
    standard = (ROOT / "requirements-stems.txt").read_text()
    assert "torch==2.2.2" in intel and "torchvision==0.17.2" in intel
    assert "torch==2.14.1+cpu" in win and "torchvision==0.29.1+cpu" in win
    assert "torchvision==0.29.1+cpu" in standard


def test_native_packaging_collects_torchvision_and_ci_checks_compiled_ops():
    spec = (ROOT / "native/mta_audio_editor_native.spec").read_text()
    ci = (ROOT / ".github/workflows/ci-cd.yml").read_text()
    assert '"torchvision"' in spec
    assert ci.count("from torchvision.ops import nms") >= 2


def test_runtime_reports_actionable_nms_dependency_issue():
    app = (ROOT / "app/main.py").read_text()
    assert "Incompatible PyTorch/torchvision native operators" in app
    assert "nms(torch.empty((0, 4)), torch.empty((0,)), 0.5)" in app
