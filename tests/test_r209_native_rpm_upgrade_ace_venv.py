"""Regressions for repeated RPM installs and already-installed ACE-Step."""
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / 'scripts'


def test_ace_existing_install_has_venv_before_skip_branch():
    script = (SCRIPTS / 'install_ace_step.sh').read_text()
    declaration = 'VENV="$BASE/venv-ace-step"'
    assert script.count(declaration) == 1
    assert script.index(declaration) < script.index('if (( ! SKIP_INSTALL )); then')
    assert script.index(declaration) < script.index('if ! "$VENV/bin/python" -c')
    assert 'ACE-Step $ACE_VERSION already installed; retaining existing Python environment and checkpoints.' in script
    assert subprocess.run(['bash', '-n', str(SCRIPTS / 'install_ace_step.sh')], check=False).returncode == 0


def test_signed_native_repo_upgrades_existing_server():
    script = (SCRIPTS / 'repositories/install_repository.sh').read_text()
    assert 'if rpm -q mta-audio-editor-server >/dev/null 2>&1; then' in script
    assert 'dnf upgrade -y --refresh mta-audio-editor-server' in script
    assert 'dnf install -y --refresh mta-audio-editor-server' in script
    assert 'repo_gpgcheck=1' in script
    assert 'gpgcheck=1' in script
    assert subprocess.run(['bash', '-n', str(SCRIPTS / 'repositories/install_repository.sh')], check=False).returncode == 0
