"""Prevent release builders from using an unrelated Python ABI."""
from pathlib import Path

BASE = Path(__file__).resolve().parents[1] / 'scripts/server_packages'


def test_deb_release_binds_python_minor():
    script = (BASE / 'build_deb.sh').read_text()
    assert '3.12) py_deps=' in script
    assert '3.13) py_deps=' in script
    assert 'python3 (<< 3.14)' in script
    assert 'MTA_SERVER_PYTHON' in script


def test_rpm_release_uses_python312_verifier():
    script = (BASE / 'build_rpm.sh').read_text()
    assert 'MTA_SERVER_PYTHON:-python3.12' in script
    assert 'MTA_SERVER_RELEASE_READY' in script


def test_promoted_python_is_tested_before_backup_removed():
    script = (BASE / 'install_runtime.py').read_text()
    assert script.index('promoted_python =') < script.index('shutil.rmtree(backup)')
    assert "subprocess.run([promoted_python, '-m', 'pip', 'check']" in script
