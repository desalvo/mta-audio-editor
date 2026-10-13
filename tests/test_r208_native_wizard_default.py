from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def test_native_package_is_default():
    text = (ROOT / 'scripts/install_mta.sh').read_text()
    assert 'if (( ! legacy_source )); then' in text
    assert '--legacy-source' in text


def test_single_file_bootstrap_downloads_wizard():
    text = (ROOT / 'scripts/install_mta.sh').read_text()
    assert 'repositories/install_repository.sh install_mta_native_wizard.sh' in text
    assert '"$native_dir/install_mta_native_wizard.sh"' in text


def test_wizard_can_reconfigure_without_reinstalling():
    text = (ROOT / 'scripts/install_mta_native.sh').read_text()
    assert '--configure-only' in text
    assert '--no-wizard' in text
    assert 'exec bash "$wizard"' in text


def test_scripts_have_valid_syntax():
    for f in ('install_mta.sh', 'install_mta_native.sh', 'install_mta_native_wizard.sh'):
        subprocess.run(['bash', '-n', str(ROOT / 'scripts' / f)], check=True)


def test_native_wizard_does_not_source_env_or_use_unverified_downloads():
    text = (ROOT / 'scripts/install_mta_native_wizard.sh').read_text()
    assert 'source "$config"' not in text
    assert 'curl http' not in text
    assert 'dnf install -y' in text
