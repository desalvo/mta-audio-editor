"""r198: guard first-install wizard against regressions on LXC."""
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "install_ace_step.sh"


def test_wizard_bash_syntax():
    subprocess.run(["bash", "-n", str(SCRIPT)], check=True)


def test_wizard_help_is_non_destructive():
    result = subprocess.run(["bash", str(SCRIPT), "--help"], check=True,
                            text=True, capture_output=True)
    assert "--version" in result.stdout
    assert "--dry-run" in result.stdout
    assert "kernel" in result.stdout


def test_wizard_guards_gpu_and_persistent_storage():
    source = SCRIPT.read_text()
    assert "-c /dev/kfd" in source
    assert "/dev/dri/renderD*" in source
    assert "torch==$TORCH_VERSION" in source
    assert "torchaudio==$TORCH_VERSION" in source
    assert "models/checkpoints" in source
    assert "backup.$stamp" in source
    assert "mta-ace-step.service" in source
