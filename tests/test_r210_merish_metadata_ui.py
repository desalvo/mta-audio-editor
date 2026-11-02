"""M-Live identity settings live in the account profile."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_profile_exposes_mlive_settings_and_import_button():
    account = (ROOT / 'app/templates/account.html').read_text()
    editor = (ROOT / 'app/static/app.js').read_text()
    assert 'id="mliveProfile"' in account
    assert 'name="merish_user_id"' in account and 'name="merish_syl_key"' in account
    assert '<button type="button" id="mliveImportButton">' in account
    assert 'projectMetaMerishUserId' not in editor and 'projectMetaMerishSylKey' not in editor
    assert '/api/projects/${encodeURIComponent(projectId)}/merish-metadata' not in editor
