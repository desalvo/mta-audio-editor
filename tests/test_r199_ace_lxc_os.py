"""r199: OS guard refuses unsupported distributions before any installation."""
from pathlib import Path
import os
import subprocess

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/install_ace_step.sh"


def run_case(tmp_path, distro, version, like=""):
    os_release = tmp_path / "os-release"
    os_release.write_text(f'ID={distro}\nVERSION_ID="{version}"\nID_LIKE="{like}"\nPRETTY_NAME="Fixture {distro} {version}"\n')
    bins = tmp_path / "bin"
    bins.mkdir(exist_ok=True)
    for cmd in ("dnf", "apt-get"):
        executable = bins / cmd
        executable.write_text("#!/bin/sh\nexit 0\n")
        executable.chmod(0o755)
    env = dict(os.environ, MTA_OS_RELEASE=str(os_release), PATH=str(bins) + os.pathsep + os.environ["PATH"])
    return subprocess.run(["bash", str(SCRIPT), "--dry-run"], env=env, capture_output=True, text=True)


def test_bash_syntax():
    subprocess.run(["bash", "-n", str(SCRIPT)], check=True)


def test_os_gate(tmp_path):
    for name, ver, like in [("alpine", "3.21", ""), ("rocky", "8.10", "rhel"), ("centos", "7", "rhel"), ("debian", "8", ""), ("ubuntu", "20.04", "debian")]:
        result = run_case(tmp_path, name, ver, like)
        assert result.returncode == 2, (name, result.stdout, result.stderr)
        assert "Unsupported" in result.stderr
    for name, ver, like in [("debian", "12", ""), ("rocky", "9.8", "rhel"), ("almalinux", "9.5", "rhel"), ("ubuntu", "24.04", "debian")]:
        result = run_case(tmp_path, name, ver, like)
        assert "Supported OS:" in result.stdout, (name, result.stdout, result.stderr)
        # Next check must be the required Proxmox GPU device gate in CI.
        assert "Unsupported" not in result.stderr


def test_package_managers_and_early_gate():
    text = SCRIPT.read_text()
    assert text.index('OS_RELEASE=') < text.index('render_nodes=')
    assert text.index('render_nodes=') < text.index('apt-get update')
    assert 'DEBIAN_FRONTEND=noninteractive apt-get install' in text
    assert 'dnf install -y' in text
