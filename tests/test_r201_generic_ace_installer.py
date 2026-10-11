from pathlib import Path
import os
import subprocess
ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "install_ace_step.sh"

def test_executable_shebang_and_help():
    assert SCRIPT.exists()
    assert os.access(SCRIPT, os.X_OK)
    assert SCRIPT.read_text().startswith("#!/usr/bin/env bash\n")
    subprocess.run(["bash", "-n", str(SCRIPT)], check=True)
    help_result = subprocess.run([str(SCRIPT), "--help"], capture_output=True, text=True, check=True)
    assert "--reinstall" in help_result.stdout
    assert "--port" in help_result.stdout
    assert "Linux" in help_result.stdout or "wizard" in help_result.stdout

def test_legacy_name_removed():
    assert not (ROOT / "scripts" / "install_ace_step_lxc.sh").exists()
    text = SCRIPT.read_text()
    assert "Run as root on the target Linux system." in text
