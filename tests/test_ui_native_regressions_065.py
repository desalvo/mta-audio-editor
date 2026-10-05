from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = (ROOT / 'app/static/app.js').read_text(encoding='utf-8')
CSS = (ROOT / 'app/static/app.css').read_text(encoding='utf-8')
HTML = (ROOT / 'app/templates/index.html').read_text(encoding='utf-8')
MAIN = (ROOT / 'app/main.py').read_text(encoding='utf-8')


def test_meter_token_is_declared_and_playback_save_is_silent():
    assert 'meterRunToken=0' in JS
    start = JS.index('async function previewMaster()')
    body = JS[start: start + 450]
    assert 'collect();stopPlayback()' in body
    assert 'await flushAutosave(false)' not in body
    assert 'await save()' not in body


def test_project_can_be_closed_without_deleting_it():
    assert 'function closeCurrentProject()' in JS
    assert 'Close project' in HTML
    body = JS[JS.index('function closeCurrentProject()'):JS.index('function closeCurrentProject()') + 650]
    assert "current=null" in body
    assert "method:'DELETE'" not in body


def test_account_navigation_redirects_expired_session_to_login():
    marker = 'def account_page(request: Request):'
    body = MAIN[MAIN.index(marker):MAIN.index(marker) + 420]
    assert 'if not session_user(request)' in body
    assert 'RedirectResponse' in body
    assert '/login?next=/account' in body


def test_responsive_toolbars_wrap_instead_of_overflowing():
    assert '.topbar{' in CSS and 'flex-wrap:wrap' in CSS
    assert '.editor-toolbar{flex-wrap:wrap;overflow-x:hidden' in CSS
    assert '.header-actions{flex-wrap:wrap' in CSS


def test_native_choose_button_has_explicit_readable_style():
    assert '.native-path-row .utility-btn{' in CSS
    block = CSS[CSS.rindex('.native-path-row .utility-btn{'):]
    assert 'color:#eaf6ff!important' in block
    assert 'Scegli…' in JS


def test_mobile_sidebar_is_expandable_and_reveals_labels():
    assert 'mobileSidebarToggle' in HTML
    assert 'function toggleMobileSidebar()' in JS
    assert 'mobile-nav-expanded' in JS
    assert '.sidebar.mobile-expanded .nav-item span{display:inline!important' in CSS
