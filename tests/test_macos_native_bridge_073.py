from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = (ROOT / "app/static/app.js").read_text(encoding="utf-8")
HTML = (ROOT / "app/templates/index.html").read_text(encoding="utf-8")


def test_native_bridge_waits_for_pywebview_event_and_slow_macos_injection():
    assert "async function waitForNativeApi(timeoutMs=15000)" in JS
    assert "window.addEventListener('pywebviewready',finish,{once:true})" in JS
    assert "return nativeApi();" in JS


def test_new_project_buttons_are_not_implicit_submit_buttons():
    assert 'type="button" onclick="chooseNewProjectPath()"' in JS
    assert 'type="button" onclick="createProjectFromDialog()"' in JS


def test_stem_workflow_buttons_are_not_implicit_submit_buttons():
    assert 'type="button" onclick="startStemWorkflow()"' in JS
    assert 'type="button" onclick="closeUtilityModal()"><span>Annulla</span>' in JS


def test_modal_content_stops_backdrop_click_propagation():
    assert 'class="utility-modal" onclick="event.stopPropagation()"' in HTML
