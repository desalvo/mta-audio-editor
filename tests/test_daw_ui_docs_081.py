from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
MODELS=(ROOT/"app/models.py").read_text()
JS=(ROOT/"app/static/app.js").read_text()
CSS=(ROOT/"app/static/app.css").read_text()
USER=(ROOT/"app/docs/user.html").read_text()
USER_EN=(ROOT/"app/docs/user-en.html").read_text()

def test_multitrack_daw_project_format_is_supported():
    assert 'Literal["MTA8", "MTA16", "DAW"]' in MODELS
    assert '>Multitrack DAW</option>' in JS
    assert 'mta_target:' in MODELS

def test_track_selection_does_not_revalidate_existing_waveforms():
    assert 'if(waveformValidationProjectId!==current.id)' in JS
    assert 'if(t.waveform_peaks?.length){drawWave(t);if(!validateExisting)continue}' in JS

def test_plugin_number_commits_on_blur_or_enter():
    assert 'onblur="commitPluginEditorParams' in JS
    assert 'pluginNumberKey(event' in JS
    assert "event.key==='Enter'" in JS

def test_mixer_has_no_static_volume_bar():
    assert 'meter meter-static' not in JS
    assert '.meter-static{display:none!important}' in CSS
    assert '.v-fader{width:108px;height:13px}' in CSS

def test_docs_describe_real_daw_and_new_controls():
    assert 'Digital Audio Workstation (DAW) multitraccia' in USER
    assert 'Multitrack DAW' in USER and 'Multitrack DAW' in USER_EN
    assert 'facendo click fuori dal campo' in USER
    assert 'when focus leaves the field' in USER_EN
