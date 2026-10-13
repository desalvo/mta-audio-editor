from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
ACE = ROOT / 'scripts/install_ace_step.sh'
WIZ = ROOT / 'scripts/install_mta_native_wizard.sh'

def run(*args):
    return subprocess.run(['bash', str(ACE), *args], text=True, capture_output=True, timeout=15)

def test_cpu_dry_run_without_gpu():
    p = run('--device', 'cpu', '--yes', '--dry-run')
    assert p.returncode == 0, p.stderr
    assert 'device=cpu' in p.stdout
    assert 'CPU-only' in p.stdout

def test_auto_dry_run():
    p = run('--device', 'auto', '--yes', '--dry-run')
    assert p.returncode == 0, p.stderr
    assert 'device=' in p.stdout

def test_device_validation():
    p = run('--device', 'invalid', '--yes', '--dry-run')
    assert p.returncode != 0

def test_main_wizard_cpu_support():
    text = WIZ.read_text()
    assert "ACE-Step execution device (auto/rocm/cpu)" in text
    assert '--device "$ace_device"' in text
    assert 'Falling back automatically to CPU-only ACE-Step' in text

def test_cpu_wheels_selected():
    text = ACE.read_text()
    assert 'https://download.pytorch.org/whl/cpu' in text
    assert 'MTA_EXPECT_ACE_DEVICE' in text
    assert '.mta-installed-device' in text
