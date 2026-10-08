from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_sidebar_preferences_saved_globally():
    js = (ROOT / 'app/static/app.js').read_text(encoding='utf-8')
    assert "mta.sidebar.collapsed.v1" in js
    assert 'restoreSidebarPanels();' in js
    assert "localStorage.setItem(SIDEBAR_PREF_KEY,JSON.stringify(state))" in js
    assert "toggleSidebarPanel('view'" in js


def test_model_manager_lists_backing_models_and_paths():
    js = (ROOT / 'app/static/app.js').read_text(encoding='utf-8')
    native = (ROOT / 'native/mta_audio_editor_native.py').read_text(encoding='utf-8')
    main = (ROOT / 'app/main.py').read_text(encoding='utf-8')
    assert 'api(\'/api/vocal-separation/models\')' in js
    assert 'm.path||v.model_directory' in js
    assert '"storage_path": str(local_repo())' in native
    assert '"model_directory": str(LEAD_BACKING_MODEL_DIR)' in main
    assert '@app.delete("/api/vocal-separation/models/{model_id}")' in main


def test_bilingual_backing_vocals_and_worker_hiding():
    js = (ROOT / 'app/static/app.js').read_text(encoding='utf-8')
    native = (ROOT / 'native/mta_audio_editor_native.py').read_text(encoding='utf-8')
    assert "['Scarica modello','Download model']" in js
    assert "['Avvia separazione','Start separation']" in js
    assert 'NSApplicationActivationPolicyProhibited' in native
    assert '_hide_background_worker_dock_icon()' in native
