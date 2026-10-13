"""Native installer external dependency consent regression gates."""
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def test_interactive_default_and_unattended_dry_runs():
    installer = ROOT / 'scripts/install_mta.sh'
    for mode in ([], ['--unattended'], ['--yes']):
        cmd = ['bash', str(installer), '--native-server', 'early', '--dry-run', *mode]
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        assert result.returncode == 0, result.stderr
        assert 'NATIVE_SERVER channel=early' in result.stdout


def test_external_repo_consent_and_security_guards():
    s = (ROOT / 'scripts/repositories/install_repository.sh').read_text()
    assert 'confirm_external' in s
    assert 'read -r -p' in s
    assert '[[ $MODE == --unattended ]]' in s
    assert 'dnf install -y epel-release' in s
    assert 'dnf -q list --available epel-release' in s
    assert 'dnf -q provides /usr/bin/ffmpeg' in s
    assert 'gpgcheck=1' in s and 'repo_gpgcheck=1' in s
    assert 'nogpgcheck' not in s and 'skip-broken' not in s
    assert 'curl' in s and 'fingerprint mismatch' in s.lower()


def test_single_file_bootstrap_forwards_unattended():
    s = (ROOT / 'scripts/install_mta.sh').read_text()
    assert '"$@"' in s and 'tmp_native' in s
    n = (ROOT / 'scripts/install_mta_native.sh').read_text()
    assert '--unattended|--yes)' in n
    assert '--unattended || echo --interactive' in n
