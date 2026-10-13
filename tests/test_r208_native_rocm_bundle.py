"""ROCm bootstrap must be packaged and optional, never silently install host drivers."""
from pathlib import Path
import subprocess
ROOT = Path(__file__).resolve().parents[1]


def test_both_packages_ship_rocm_bootstrap():
    for name in ('build_rpm.sh', 'build_deb.sh'):
        src = (ROOT / 'scripts/server_packages' / name).read_text()
        assert 'install_rocm_userspace.sh' in src
        assert 'native-installers/install_rocm_userspace.sh' in src


def test_local_ace_checks_rocm_before_installing_ace():
    src = (ROOT / 'scripts/install_mta_native_wizard.sh').read_text()
    assert src.index('bash "$rocm_installer" yes') < src.index('bash "$ace_installer" --yes')
    assert 'alternative' not in src or 'choose remote ACE-Step' in src


def test_rocm_no_disables_without_changes():
    res = subprocess.run(['bash', str(ROOT / 'scripts/install_rocm_userspace.sh'), 'no'], capture_output=True, text=True)
    assert res.returncode == 0
    assert 'disabled' in res.stdout


def test_rocm_never_installs_kernel_drivers():
    src = (ROOT / 'scripts/install_rocm_userspace.sh').read_text()
    assert 'dnf install -y rocm-hip-runtime rocminfo' in src
    assert 'dnf install -y amdgpu-dkms' not in src
    assert 'Do not use EL9 packages on EL10' in src


def test_rocm_shell_valid():
    for name in ('install_rocm_userspace.sh', 'install_mta_native_wizard.sh'):
        subprocess.run(['bash', '-n', str(ROOT / 'scripts' / name)], check=True)
