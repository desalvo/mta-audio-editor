from pathlib import Path
import os
import subprocess

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "install_mta.sh"


def test_install_mta_standalone_and_executable():
    source = SCRIPT.read_text()
    assert source.startswith("#!/usr/bin/env bash")
    assert SCRIPT.stat().st_mode & 0o111
    assert "git clone" in source and "mta-audio-editor.git" in source
    assert "--uninstall" in source and "--purge-data" in source
    assert "/api/health" in source


def test_dry_run_preserves_selected_version_and_network_values():
    result = subprocess.run([str(SCRIPT), "--legacy-source", "--dry-run", "--version", "v0.3.0", "--port", "8877", "--bind", "local"], capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr
    assert "ref=v0.3.0" in result.stdout
    assert "port=8877 bind=local" in result.stdout


def test_unsupported_os_rejected_before_root_check(tmp_path):
    os_release = tmp_path / "os-release"
    os_release.write_text('ID=alpine\nVERSION_ID=3.22\nPRETTY_NAME=Alpine\n')
    env = dict(os.environ, MTA_OS_RELEASE=str(os_release))
    result = subprocess.run([str(SCRIPT), "--legacy-source", "--dry-run"], env=env, capture_output=True, text=True, timeout=10)
    assert result.returncode == 2
    assert "Unsupported OS" in result.stderr
