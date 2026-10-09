from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
JS=(ROOT/'app/static/app.js').read_text()
NATIVE=(ROOT/'native/mta_audio_editor_native.py').read_text()


def test_settings_save_does_not_block_with_full_page_translation():
    section=JS.split('async function saveNativeSettings(){',1)[1].split('async function checkNativeAppUpdate',1)[0]
    assert 'if(languageChanged)setTimeout(()=>applyInterfaceLanguage(),0)' in section
    assert 'if(languageChanged)applyInterfaceLanguage()' not in section
    assert 'nativeSettingsSaveInProgress' in section
    assert 'Promise.race' in section


def test_settings_native_handler_does_not_import_web_app_on_ui_bridge():
    section=NATIVE.split('    def set_native_settings(',1)[1].split('    def set_recent_projects(',1)[0]
    assert 'sys.modules.get("app.main")' in section
    assert 'import app.main as app_main' not in section
