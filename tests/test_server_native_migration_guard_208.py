from pathlib import Path
import subprocess

BASE = Path(__file__).resolve().parents[1]
SCRIPTS = BASE / 'scripts'


def test_deb_has_preinst_migration_guard():
    builder = (SCRIPTS / 'server_packages/build_deb.sh').read_text()
    assert 'DEBIAN/preinst' in builder
    preinst = (SCRIPTS / 'server_packages/preinst').read_text()
    assert '.mta-wizard-managed' in preinst and '/opt/mta/application/.git' in preinst


def test_rpm_pre_script_guard():
    spec = (SCRIPTS / 'server_packages/build_rpm.sh').read_text()
    assert '%pre\n' in spec
    assert '.mta-wizard-managed' in spec


def test_native_installer_dry_run_uses_pinned_official_trust_anchor():
    # The official HTTPS endpoint and GPG fingerprint are built in; manual
    # environment variables are no longer mandatory for native installation.
    import os
    env = dict(os.environ)
    env.pop('MTA_PACKAGES_URL', None)
    env.pop('MTA_REPO_KEY_FINGERPRINT', None)
    result = subprocess.run(
        ['bash', str(SCRIPTS / 'install_mta.sh'), '--native-server', 'early', '--dry-run'],
        capture_output=True, text=True, env=env,
    )
    assert result.returncode == 0, result.stderr
    assert 'channel=early' in result.stdout
    assert 'https://desalvo.github.io/mta-audio-editor-packages' in result.stdout
    assert 'mta-audio-editor-server' in result.stdout
    native = (SCRIPTS / 'install_mta_native.sh').read_text()
    assert '0833A4FCB008ECAC9F98840B4C1D2DD95F5AEDB7' in native
    assert 'MTA_REPO_KEY_FINGERPRINT' in (SCRIPTS / 'repositories/install_repository.sh').read_text()


def test_native_installer_rejects_invalid_fingerprint_override():
    import os
    env = dict(os.environ, MTA_REPO_KEY_FINGERPRINT='not-a-valid-fingerprint')
    result = subprocess.run(
        ['bash', str(SCRIPTS / 'install_mta.sh'), '--native-server', 'early', '--dry-run'],
        capture_output=True, text=True, env=env,
    )
    assert result.returncode == 2
    assert 'fingerprint' in result.stderr.lower()


def test_native_installer_dry_run_does_not_mutate():
    import os
    env = dict(os.environ, MTA_PACKAGES_URL='https://example.invalid/repo', MTA_REPO_KEY_FINGERPRINT='A'*40)
    result = subprocess.run(['bash', str(SCRIPTS / 'install_mta.sh'), '--native-server', 'stable', '--dry-run'], capture_output=True, text=True, env=env)
    assert result.returncode in (0, 3)
    if result.returncode == 0:
        assert 'mta-audio-editor-server' in result.stdout
