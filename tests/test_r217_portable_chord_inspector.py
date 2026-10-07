from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = (ROOT / "app/static/app.js").read_text(encoding="utf-8")
CSS = (ROOT / "app/static/app.css").read_text(encoding="utf-8")
NATIVE = (ROOT / "native/mta_audio_editor_native.py").read_text(encoding="utf-8")


def test_portable_project_is_default_native_save_and_open_format():
    assert 'Portable MTA Audio Editor Project (*.maeprojz)' in NATIVE
    assert 'safe_name += PORTABLE_PROJECT_EXTENSION' in NATIVE
    portable_pos = NATIVE.index('"Portable MTA Audio Editor Project (*.maeprojz)"')
    legacy_pos = NATIVE.index('"MTA Audio Editor Project (*.maeproj)"')
    assert portable_pos < legacy_pos


def test_opened_portable_project_remains_bound_for_save_and_autosave():
    assert 'if is_portable_project_archive(resolved):' in NATIVE
    assert 'self.project_paths[project.id] = resolved' in NATIVE
    assert 'self._persist_project_paths()' in NATIVE
    assert 'await syncNativeProjectFile(current?.id);' in JS
    assert 'await syncNativeProjectFile(current.id);' in JS


def test_chord_extraction_renders_new_state_before_persisting_it():
    needle = "current=await api(`/api/projects/${current.id}`);"
    start = JS.index(needle)
    block = JS[start:start + 1000]
    assert block.index('render();') < block.index('await persistCurrentProject(false);')
    assert 'await syncNativeProjectFile(current.id);' in block


def test_inspector_reserves_horizontal_timeline_viewport_without_changing_track_geometry():
    assert '.editor-grid:not(.inspector-hidden) .timeline-pane{margin-right:min(360px,42vw)}' in CSS
    assert '@media(max-width:900px){.editor-grid:not(.inspector-hidden) .timeline-pane{margin-right:min(360px,78vw)}}' in CSS
    assert '.inspector{position:absolute!important' in CSS


def test_inspector_insert_configuration_is_routed_to_track_modal():
    assert '${insertPanelHtml(t,false,t.id)}' in JS
    assert "function insertPanelHtml(owner,isMaster,trackId='')" in JS
    assert 'insertHtml(x,n,isMaster,trackId)' in JS
    assert 'insertAddHtml(isMaster,trackId)' in JS


def test_utility_modals_stay_above_inspector():
    assert '.utility-backdrop{position:fixed;inset:0;z-index:5000' in CSS
    assert 'z-index:180!important' in CSS
