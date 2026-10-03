from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
JS=(ROOT/"app/static/app.js").read_text()
HTML=(ROOT/"app/templates/index.html").read_text()

def test_native_picker_waits_for_bridge():
    assert "async function waitForNativeApi" in JS
    assert "const apiBridge=await waitForNativeApi()" in JS
    assert "apiBridge.choose_project_save_path" in JS

def test_stem_new_project_requires_native_destination():
    assert "if(mode==='new'&&currentUser?.native_single_user)" in JS
    assert "impossibile scegliere dove salvare il nuovo progetto" in JS

def test_settings_name_and_native_availability():
    assert ">Settings</span>" in HTML
    assert "Native settings</span>" not in HTML
    assert "showUtilityModal('Settings'" in JS

def test_editing_tools_are_collapsed_group():
    assert 'id="editingToolsPanel"' in HTML
    assert 'id="editingToolsPanel"' in HTML and 'sidebar-tools collapsed' in HTML
    for label in ["Import MTA","Import Audio","Import &amp; Separate","Tracks","Plugins","Mixer"]:
        assert label in HTML

def test_tracks_plugins_mixer_have_actions():
    assert 'onclick="focusTracks()"' in HTML
    assert 'onclick="focusInspector()"' in HTML
    assert 'onclick="focusMixer()"' in HTML
    assert "function focusTracks()" in JS
