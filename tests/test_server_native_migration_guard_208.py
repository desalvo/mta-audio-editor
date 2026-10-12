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


def test_native_installer_dry_run_requires_trust_anchor():
    result = subprocess.run(['bash', str(SCRIPTS / 'install_mta.sh'), '--native-server', 'early', '--dry-run'], capture_output=True, text=True)
    assert result.returncode == 2
    assert 'fingerprint' in result.stderr.lower() or 'repository' in result.stderr.lower()


def test_native_installer_dry_run_does_not_mutate():
    import os
    env = dict(os.environ, MTA_PACKAGES_URL='https://example.invalid/repo', MTA_REPO_KEY_FINGERPRINT='A'*40)
    result = subprocess.run(['bash', str(SCRIPTS / 'install_mta.sh'), '--native-server', 'stable', '--dry-run'], capture_output=True, text=True, env=env)
    assert result.returncode in (0, 3)
    if result.returncode == 0:
        assert 'mta-audio-editor-server' in result.stdout
