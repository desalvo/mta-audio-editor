"""Regression gates for crash-safe configuration collection in the signed native wizard."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WIZARD = (ROOT / 'scripts/install_mta_native_wizard.sh').read_text()


def test_root_only_checkpoint_is_separate_from_live_config():
    assert 'checkpoint=/etc/mta/.mta-wizard.pending' in WIZARD
    assert 'umask 077' in WIZARD
    assert 'chmod 600 "$temp"' in WIZARD
    assert 'mv -f "$temp" "$checkpoint"' in WIZARD
    assert 'cp "$checkpoint" "$work"' in WIZARD
    assert 'Resuming previously saved wizard answers' in WIZARD


def test_every_primary_prompt_is_saved_before_next_prompt():
    for key in ['MTA_PORT', 'MTA_HOST', 'MTA_ADMIN_USERNAME',
                'MTA_DATA_DIR', 'MTA_ADMIN_PASSWORD', 'MTA_AI_DEVICE',
                'MTA_PUBLIC_URL', 'MTA_TLS_CERTFILE', 'MTA_TLS_KEYFILE',
                'MTA_ACE_STEP_URL']:
        assert f'set_setting {key} ' in WIZARD
    for key in ['ACE_MODE', 'ACE_DEVICE', 'ACE_PORT', 'HTTPS',
                'TLS_MODE', 'TLS_NAME', 'FIREWALL', 'BILLING']:
        assert f'checkpoint_answer {key} ' in WIZARD


def test_never_apply_wizard_metadata_to_running_service():
    assert "sed -i '/^MTA_WIZARD_[A-Z_]*=/d' \"$work\"" in WIZARD
    assert 'rm -f "$checkpoint"' in WIZARD
    assert 'cp -p "$backup" "$config"' in WIZARD
