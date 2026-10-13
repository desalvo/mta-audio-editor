from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
WIZARD = (ROOT / 'scripts/install_mta_native_wizard.sh').read_text()


def test_wizard_syntax():
    subprocess.run(['bash', '-n', str(ROOT / 'scripts/install_mta_native_wizard.sh')], check=True)


def test_self_signed_tls_san_and_private_key_permissions():
    assert 'openssl req -x509' in WIZARD
    assert 'subjectAltName=$san' in WIZARD
    assert 'chmod 600 "$tls_tmp/server.key"' in WIZARD
    assert 'MTA_TLS_CERTFILE' in WIZARD and 'MTA_TLS_KEYFILE' in WIZARD


def test_external_http_forbidden_except_loopback():
    assert 'Remote ACE-Step requires HTTPS' in WIZARD
    assert '127\\.0\\.0\\.1|localhost' in WIZARD
    assert 'MTA_ACE_STEP_TRUSTED_HOST' in WIZARD
    assert 'MTA_ACE_STEP_TOKEN' in WIZARD


def test_firewall_opt_in_not_default_and_no_auto_enable():
    assert "ask 'Open server TCP port in host firewall (yes/no)' no" in WIZARD
    assert 'systemctl enable --now firewalld' not in WIZARD
    assert 'firewall-cmd --permanent --add-port=' in WIZARD
    assert 'ufw allow ' in WIZARD


def test_rollback_restart_and_no_rpm_scriptlets_prompt():
    assert "cp -p \"$backup\" \"$config\"" in WIZARD
    assert 'if ! systemctl restart mta-server.service' in WIZARD
    rpm = (ROOT / 'scripts/server_packages/build_rpm.sh').read_text()
    assert '%post' in rpm
    assert 'read -r -p' not in rpm
