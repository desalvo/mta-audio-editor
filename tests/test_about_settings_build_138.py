from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
JS = (ROOT / 'app/static/app.js').read_text(encoding='utf-8')
CSS = (ROOT / 'app/static/app.css').read_text(encoding='utf-8')
WF = (ROOT / '.github/workflows/ci-cd.yml').read_text(encoding='utf-8')


def test_about_has_large_logo_and_documentation_photo():
    assert 'about-photo' in JS
    assert "cover-daw-studio.png" in CSS
    assert '.about-logo{width:170px' in CSS
    assert 'about-info-panel' in CSS


def test_settings_available_on_web_and_native_buttons_are_legible():
    assert 'async function showSettings()' in JS
    assert "if(currentUser?.native_single_user)return showNativeSettings();" in JS
    assert 'return showWebSettings();' in JS
    assert 'Settings non disponibile' not in JS
    assert 'native-settings' in JS
    assert '-webkit-text-fill-color:#f4f9fd!important' in CSS
    assert 'mtaWebAutosaveEnabled' in JS


def test_build_number_format_is_strict_14_digits():
    build = (ROOT / 'BUILD_INFO').read_text(encoding='utf-8').strip()
    assert re.fullmatch(r'\d{14}', build)
    assert "+%Y%m%d%H%M%S" in WF
    assert 'yyyyMMddHHmmss' in WF
    assert '%Y%m%d-%H:%M:%S' not in WF
    assert 'yyyyMMdd-HH:mm:ss' not in WF
