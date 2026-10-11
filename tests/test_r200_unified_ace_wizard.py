"""Regression contracts for the unified, persistent ACE-Step LXC installer."""
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
WIZARD = ROOT / 'scripts' / 'install_ace_step.sh'


def test_only_one_install_entrypoint():
    assert WIZARD.is_file()
    assert not (ROOT / 'scripts' / 'reinstall_ace_step.sh').exists()


def test_wizard_parses_and_documents_reinstall_and_network_options():
    subprocess.run(['bash', '-n', str(WIZARD)], check=True)
    out = subprocess.run(['bash', str(WIZARD), '--help'], capture_output=True, text=True, check=True).stdout
    for flag in ('--port', '--bind', '--firewall', '--reinstall', '--dry-run'):
        assert flag in out


def test_wizard_persists_settings_privately_and_does_not_source_config():
    data = WIZARD.read_text()
    assert '/etc/mta/ace-step-wizard.conf' in data
    assert 'while IFS=\'=\' read -r key val' in data
    assert '. "$CONFIG"' not in data
    assert 'chmod 600 "$TMP_CONF"' in data
    assert 'mv -f "$TMP_CONF" "$CONFIG"' in data
    assert 'SKIP_INSTALL=1' in data
    assert 'REINSTALL=0' in data


def test_localhost_by_default_and_no_firewall_opening():
    data = WIZARD.read_text()
    assert 'PORT=8001; BIND=local; FIREWALL=no' in data
    assert 'HOST=127.0.0.1' in data
    assert '[[ $BIND == network ]] && HOST=0.0.0.0' in data
    assert 'if [[ $BIND == local ]]; then FIREWALL=no; fi' in data


def test_docs_no_longer_mention_deleted_script():
    for name in ('ACE_STEP_ROCKY_LXC.md', 'ACE_STEP_LXC_WIZARD.md'):
        assert 'reinstall_ace_step.sh' not in (ROOT / name).read_text()
