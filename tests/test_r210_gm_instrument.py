"""GM parameter/schema safety and optional actual FluidSynth PCM generation."""
import os

import numpy as np
import pytest

from app.gm_instruments import validate, Synth
from app.models import Track, InsertPlugin


@pytest.mark.parametrize('params', [{'program': 128}, {'gain': float('nan')}, {'polyphony': 2}, {'bank_id': '../../secret'}, {'path': '/etc/passwd'}, {'gain': True}, {'program': .5}])
def test_gm_rejects_unknown_banks_paths_and_invalid_values(params):
    with pytest.raises(ValueError):
        validate(params)


def test_missing_gm_runtime_does_not_prevent_loading_editable_midi(monkeypatch):
    monkeypatch.setenv('MTA_FLUIDSYNTH_LIBRARY', '/nonexistent/gm.so')
    track = Track(id='gm', name='GM', filename='gm.wav', kind='midi', instrument=InsertPlugin(id='instrument', plugin='gm_soundfont', params={'program': 24}))
    restored = Track.model_validate_json(track.model_dump_json())
    assert restored.instrument.params['program'] == 24
    with pytest.raises(ValueError, match='library'):
        Synth(restored.instrument.params, 48000)


@pytest.mark.skipif(not os.getenv('MTA_TEST_GM_RUNTIME'), reason='Set MTA_TEST_GM_RUNTIME with reviewed FluidSynth and FluidR3 assets')
def test_real_gm_soundfont_is_sample_scheduled_and_live_parameters_apply():
    synth = Synth({'program': 0, 'gain': .4, 'reverb_level': 0}, 48000)
    try:
        data = synth.process([(bytes([144, 60, 100]), .05)], duration=.1, sample_rate=48000)
        assert data.shape == (2, 4800)
        assert np.max(abs(data[:, :2300])) < 1e-6
        assert np.max(abs(data[:, 2600:])) > .001
        synth.configure({'gain': 0})
        # FluidSynth may smooth gain, so permit one short transition block.
        synth.process([], duration=.1, sample_rate=48000)
        silence = synth.process([], duration=.1, sample_rate=48000)
        assert np.max(abs(silence)) < 1e-5
        synth.reset()
    finally:
        synth.close()


@pytest.mark.skipif(not os.getenv('MTA_TEST_GM_RUNTIME'), reason='Requires reviewed GM assets and the compiled audio core')
def test_real_gm_offline_and_isolated_server_render(tmp_path):
    import soundfile as sf
    from app.models import Project, Clip, MidiNote
    from app.midi_render import render_source
    from app.vst3_live import Session
    from app.server_vst3 import read_pcm
    track = Track(id='piano', name='GM piano', filename='midi-piano.wav', kind='midi', duration_ms=1000,
                  sample_rate=48000, midi_notes=[MidiNote(id='note', pitch=60, duration_ms=800)],
                  instrument=InsertPlugin(id='instrument', plugin='gm_soundfont', params={'program':0}),
                  clips=[Clip(id='clip', source_end_ms=1000)], clips_initialized=True)
    target = tmp_path/'render.wav'
    render_source(track,target,48000)
    pcm,rate = sf.read(target)
    assert rate == 48000 and len(pcm) >= 48000 and np.max(np.abs(pcm)) > .001
    project = Project(id='gm-test',title='GM test',sample_rate=48000,tracks=[track])
    session = Session(project,[target],0,output='browser',paused=True,original_editor=False)
    try:
        result,data = read_pcm(session,0,16384)
        samples = np.frombuffer(data,dtype='<f4')
        assert result['frames'] == 16384 and np.isfinite(samples).all()
        assert np.max(np.abs(samples)) > .001
    finally:
        session.close()
