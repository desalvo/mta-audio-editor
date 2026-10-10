from pathlib import Path

APP_JS = Path(__file__).resolve().parents[1] / 'app/static/app.js'


def test_mixer_edit_registers_real_input_handlers():
    text = APP_JS.read_text()
    assert "input.addEventListener('keydown',event=>mixerTrackNameEditorKey(event,id))" in text
    assert "input.addEventListener('blur',()=>" in text
    assert "input.addEventListener('click',event=>event.stopPropagation())" in text


def test_both_rename_paths_use_fast_shared_update():
    text = APP_JS.read_text()
    assert 'function applyTrackName(id,value)' in text
    block = text.split('function applyTrackName(id,value)', 1)[1].split('function renameTrackInline',1)[0]
    assert 'markDirty(100)' in block
    assert 'render()' not in block
    assert 'host.textContent=name' in block
    assert 'function renameTrack(id)' in text
    assert 'if(value!==null)applyTrackName(id,value)' in text
    assert 'applyTrackName(id,name)' in text


def test_track_name_excluded_from_generic_model_input_writes():
    text = APP_JS.read_text()
    assert "if(el.dataset.k==='name')return" in text
    assert "el.dataset.k!=='name'" in text


def test_autosave_does_not_revert_a_rename_made_during_network_request():
    text = APP_JS.read_text()
    assert 'const projectId=current.id,mutationAtStart=projectMutationSerial' in text
    assert 'if(projectMutationSerial!==mutationAtStart)' in text
    assert 'autosaveQueued=true' in text
    assert 'projectMutationSerial++' in text
