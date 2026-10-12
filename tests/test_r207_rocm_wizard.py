"""Regression checks for the standalone ROCm userspace wizard."""
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
WIZARD = ROOT / 'scripts' / 'install_mta.sh'


def test_rocm_wizard_is_standalone():
    text = WIZARD.read_text()
    assert 'install_rocm_userspace()' in text
    assert 'install_rocm_userspace\n' in text
    assert 'MTA_ROCM_RELEASE' in text
    assert 'amdgpu-dkms' in text
    assert 'GPU=$GPU' in text
    assert '--gpu auto|yes|no' in text


def test_rocm_wizard_shell_syntax():
    subprocess.run(['bash', '-n', str(WIZARD)], check=True)


def test_rocm_wizard_rejects_invalid_gpu_value():
    result = subprocess.run(
        ['bash', str(WIZARD), '--dry-run', '--gpu', 'broken'],
        text=True, capture_output=True, check=False,
    )
    assert result.returncode != 0
    assert 'Invalid GPU setting' in result.stderr


def test_rocm_wizard_dry_run_has_no_install():
    result = subprocess.run(
        ['bash', str(WIZARD), '--dry-run', '--gpu', 'auto'],
        text=True, capture_output=True, check=False,
    )
    assert result.returncode == 0, result.stderr
    assert 'source=' in result.stdout
