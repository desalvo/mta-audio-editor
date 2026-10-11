"""Optional HTTPS on the MTA server must be opt-in and safely configured."""
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'scripts' / 'install_mta.sh'
MAIN = ROOT / 'app' / 'main.py'


def dry_run(*args, env=None):
    return subprocess.run(['bash', str(SCRIPT), '--dry-run', *args], text=True,
                          capture_output=True, timeout=10, env=env, check=False)


def test_default_is_http_and_no_certificate_required():
    proc = dry_run()
    assert proc.returncode == 0, proc.stderr
    assert 'HTTPS=no' in proc.stdout


def test_self_signed_option_and_cert_subject_validation():
    proc = dry_run('--https', 'yes', '--tls-mode', 'self-signed', '--tls-name', 'mta.example.org')
    assert proc.returncode == 0, proc.stderr
    assert 'HTTPS=yes mode=self-signed' in proc.stdout
    assert dry_run('--https', 'yes', '--tls-name', 'bad/name').returncode != 0


def test_existing_certs_require_both_absolute_paths():
    assert dry_run('--https', 'yes', '--tls-mode', 'existing').returncode != 0
    assert dry_run('--https', 'yes', '--tls-mode', 'existing', '--tls-cert', '/etc/ssl/mta.crt',
                   '--tls-key', '/etc/ssl/private/mta.key').returncode == 0
    assert dry_run('--https', 'yes', '--tls-mode', 'existing', '--tls-cert', 'relative.crt',
                   '--tls-key', '/etc/ssl/private/server.key').returncode != 0


def test_https_settings_restored_from_wizard_config(tmp_path):
    config = tmp_path / 'wizard.conf'
    config.write_text('HTTPS=yes\nTLS_MODE=existing\nTLS_CERT=/etc/ssl/mta.crt\n'
                      'TLS_KEY=/etc/ssl/mta.key\nTLS_NAME=mta.example.org\n')
    env = dict(os.environ, MTA_WIZARD_CONFIG=str(config))
    proc = dry_run(env=env)
    assert proc.returncode == 0, proc.stderr
    assert 'HTTPS=yes mode=existing' in proc.stdout
    assert 'HTTPS=no' in dry_run('--https', 'no', env=env).stdout


def test_service_uses_tls_only_when_opted_in():
    code = SCRIPT.read_text()
    assert 'MTA_TLS_CERTFILE=' in code and 'MTA_TLS_KEYFILE=' in code
    assert 'openssl x509' in code and 'openssl pkey' in code
    assert 'subjectAltName=' in code
    assert "sed -i -E '/^MTA_TLS_CERTFILE=/d; /^MTA_TLS_KEYFILE=/d'" in code
    main = MAIN.read_text()
    assert 'if bool(tls_cert) != bool(tls_key)' in main
    assert '"ssl_certfile": tls_cert' in main
    assert '"ssl_keyfile": tls_key' in main
