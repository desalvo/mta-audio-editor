from pathlib import Path

JS = (Path(__file__).resolve().parents[1] / "app/static/app.js").read_text()


def test_localization_mutations_do_not_trigger_whole_page_scan():
    section = JS.split("function ensureLiveLocalization(){", 1)[1].split("const _nativeConfirm=", 1)[0]
    assert "applyInterfaceLanguage()" not in section
    assert "applyInterfaceLanguage(node)" in section
    assert "localizationPending" in section


def test_settings_save_skips_global_language_refresh_when_unchanged():
    section = JS.split("async function saveNativeSettings(){", 1)[1].split("async function checkNativeAppUpdate", 1)[0]
    assert "if(languageChanged)setTimeout(()=>applyInterfaceLanguage(),0)" in section
    assert "setTimeout(()=>updateTimedPlaybackOverlay(playCursorMs),0)" in section


def test_native_settings_displays_loading_before_config_fetch():
    section = JS.split("async function showNativeSettings(){", 1)[1].split("async function saveNativeSettings(){", 1)[0]
    assert section.index("showUtilityModal('Settings','<p") < section.index("get_native_settings()")
