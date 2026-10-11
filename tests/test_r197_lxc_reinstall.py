from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'scripts' / 'install_ace_step.sh'


def test_lxc_script_valid_shell():
    subprocess.run(['bash', '-n', str(SCRIPT)], check=True)


def test_lxc_script_help_without_side_effects():
    completed = subprocess.run(['bash', str(SCRIPT), '--help'], check=True, capture_output=True, text=True)
    assert '--reinstall' in completed.stdout


def test_script_preserves_models_and_pins_reviewed_commit():
    data = SCRIPT.read_text()
    assert 'dce621408bee8c31b4fcf4811682eb9359e1bc94' in data
    assert 'systemctl enable --now mta-ace-step.service' in data
    assert '/models/checkpoints' in data
    assert 'rm -rf "$DATA"' not in data


def test_mta_lxc_service_script_syntax_and_security():
    script = ROOT / 'scripts' / 'install_mta_lxc_service.sh'
    subprocess.run(['bash', '-n', str(script)], check=True)
    data = script.read_text()
    assert 'MTA_AI_WORKER_ENABLED=true' in data
    assert 'MTA_ACE_STEP_URL=http://127.0.0.1:8001' in data
    assert 'After=network-online.target mta-ace-step.service' in data
    assert 'rm -rf' not in data
