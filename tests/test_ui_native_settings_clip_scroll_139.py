from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_JS = (ROOT / 'app/static/app.js').read_text(encoding='utf-8')
APP_CSS = (ROOT / 'app/static/app.css').read_text(encoding='utf-8')
INDEX = (ROOT / 'app/templates/index.html').read_text(encoding='utf-8')


def test_project_clip_browser_is_collapsed_by_default_and_reset_on_open():
    assert 'let clipBrowserExpanded=false;' in APP_JS
    assert "function resetProjectUiForOpen(){clipBrowserExpanded=false;" in APP_JS
    assert 'resetProjectUiForOpen();resetSessionHistory();render();schedulePlaybackPrewarm(40);refresh();' in APP_JS
    assert 'resetProjectUiForOpen();render();await refresh();toast(\'Progetto aperto dal filesystem\')' in APP_JS


def test_web_settings_are_available_to_admin_from_sidebar():
    assert 'id="nativeSettingsButton" onclick="showSettings()"' in INDEX
    assert 'async function showSettings()' in APP_JS
    assert "currentUser=await api('/api/session')" in APP_JS
    assert "if(currentUser?.native_single_user)return showNativeSettings();" in APP_JS
    assert 'return showWebSettings();' in APP_JS
    assert "currentUser?.role==='admin'?`<button type=\"button\" onclick=\"location.href='/settings'\">Server administration</button>`:''" in APP_JS
    assert 'Settings non disponibile' not in APP_JS


def test_native_webview_document_cannot_remain_scrolled_offscreen():
    assert 'function forceNativeViewportTop()' in APP_JS
    assert 'function installNativeViewportGuard()' in APP_JS
    assert "window.addEventListener('scroll',guard,{passive:true})" in APP_JS
    assert "document.addEventListener('focusin',()=>setTimeout(forceNativeViewportTop,0))" in APP_JS
    assert 'body.native-single-user .app-shell{position:fixed;inset:0' in APP_CSS
    assert 'body.native-single-user{height:100%;max-height:100%;overflow:hidden!important' in APP_CSS
