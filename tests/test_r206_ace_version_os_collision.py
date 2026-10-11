from pathlib import Path
import os
import subprocess

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "install_ace_step.sh"


def run_wizard(tmp_path, *, saved=None, cli=(), env_version=None, os_id="debian"):
    osfile = tmp_path / "os-release"
    if os_id == "debian":
        osfile.write_text('ID=debian\nVERSION_ID="12"\nVERSION="12 (bookworm)"\nPRETTY_NAME="Debian GNU/Linux 12"\n')
    else:
        osfile.write_text('ID=rocky\nID_LIKE="rhel centos fedora"\nVERSION_ID="9.8"\nVERSION="9.8 (Blue Onyx)"\nPRETTY_NAME="Rocky Linux 9.8"\n')
    config = tmp_path / "wizard.conf"
    if saved:
        config.write_text(f"PORT=8001\nBIND=local\nFIREWALL=no\nVERSION={saved}\n")
    env = dict(os.environ, MTA_OS_RELEASE=str(osfile), MTA_ACE_WIZARD_CONFIG=str(config))
    if env_version:
        env["MTA_ACE_VERSION"] = env_version
    else:
        env.pop("MTA_ACE_VERSION", None)
    # A simulated RHEL environment does not have dnf on CI runners.
    if os_id == "rocky":
        bin_dir = tmp_path / "bin"
        bin_dir.mkdir(exist_ok=True)
        tool = bin_dir / "dnf"
        tool.write_text("#!/bin/sh\nexit 0\n")
        tool.chmod(0o755)
        env["PATH"] = str(bin_dir) + os.pathsep + env["PATH"]
    return subprocess.run(["bash", str(SCRIPT), "--dry-run", *cli], text=True, capture_output=True, env=env)


def test_default_never_uses_os_version(tmp_path):
    for distro in ("debian", "rocky"):
        result = run_wizard(tmp_path, os_id=distro)
        # On hosts without AMD devices --dry-run can report missing GPU; the source contract
        # must still isolate ACE_VERSION from /etc/os-release and emit no OS VERSION as ACE ref.
        assert 'version=12 (bookworm)' not in result.stdout
        assert 'version=9.8 (Blue Onyx)' not in result.stdout
    source = SCRIPT.read_text()
    assert 'ACE_VERSION=${MTA_ACE_VERSION:-}' in source
    assert 'ACE_VERSION=${ACE_VERSION:-$SAVED_VERSION}' in source
    assert 'VERSION=%s' in source  # persisted config retains compatibility


def test_saved_and_command_line_versions_survive_os_release(tmp_path):
    result = run_wizard(tmp_path, saved="v0.1.8", cli=("--version", "v0.1.9"))
    assert "12 (bookworm)" not in result.stdout.split('version=')[-1]
    assert 'ACE_VERSION=$1' in SCRIPT.read_text()
