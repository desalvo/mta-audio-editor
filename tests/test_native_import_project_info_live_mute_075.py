from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = (ROOT / "app/static/app.js").read_text(encoding="utf-8")
HTML = (ROOT / "app/templates/index.html").read_text(encoding="utf-8")
NATIVE = (ROOT / "native/mta_audio_editor_native.py").read_text(encoding="utf-8")

def test_native_mta_import_asks_destination_before_upload_and_binds_project():
    import_pos = JS.index("$('#mtafile').addEventListener")
    block = JS[import_pos:import_pos + 5000]
    choose = block.index("choose_project_save_path")
    upload = block.index("uploadWithProgress('/api/import-jobs'")
    bind = block.index("bind_project_path(projectId,nativeProjectPath)")
    assert choose < upload < bind
    assert "if(!chosen?.ok)return" in block

def test_project_info_is_exposed_in_project_menu():
    assert 'onclick="showProjectInfo()">ⓘ <span>Info progetto</span>' in HTML
    assert "async function showProjectInfo()" in JS
    for label in ["Nome", "ID progetto", "Home / workspace", "Locazione", "Tipo", "Durata", "Tracce", "Auto-save"]:
        assert label in JS

def test_native_project_binding_is_persistent_and_reports_home():
    assert 'native-project-paths.json' in NATIVE
    assert "self._persist_project_paths()" in NATIVE
    assert '"home": str(_data_root())' in NATIVE

def test_dynamic_playback_instantiates_all_tracks_and_controls_gain_live():
    assert "tracks.map(t=>makeTrackPlayback" in JS
    assert "function trackAudibleNow(track)" in JS
    assert "function playbackGainForTrack(track,item=null)" in JS
    assert "function applyLiveMuteSolo()" in JS
    assert "updateMuteSoloVisuals();applyLiveMuteSolo()" in JS
    assert "if(item?.respectMuteSolo!==false&&!trackAudibleNow(track))return 0" in JS

def test_rendered_master_is_refreshed_automatically_for_mute_solo():
    assert "function refreshRenderedMasterForMixState()" in JS
    assert "if(renderedMasterPlayback&&renderedMasterDirty)return previewMaster()" in JS
