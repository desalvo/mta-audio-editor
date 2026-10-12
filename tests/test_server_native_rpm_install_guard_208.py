"""Safety checks for the RPM package-manager integration test."""
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'scripts/server_packages/test_rpm_upgrade.sh'


def test_rpm_install_requires_disposable_container():
    result = subprocess.run(['bash', str(SCRIPT)], capture_output=True, text=True, check=False)
    assert result.returncode != 0
    assert 'MTA_SERVER_RPM' in result.stderr


def test_rpm_install_rejects_untrusted_environment():
    result = subprocess.run(['bash', str(SCRIPT)], env={'PATH': '/usr/bin:/bin', 'MTA_SERVER_RPM': '/tmp/test.rpm'},
                            capture_output=True, text=True, check=False)
    assert result.returncode == 2
    assert 'disposable CI container' in result.stderr


def test_ci_push_scope_includes_native_packaging():
    workflow = (ROOT / '.github/workflows/server-native-runtime-validation.yml').read_text()
    assert 'push:' in workflow
    assert "- 'scripts/server_packages/**'" in workflow
    assert 'test_rpm_upgrade.sh' in workflow
