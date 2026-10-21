"""Actual optional singing and atomic publication; no fabricated model results."""
import os
from pathlib import Path
import shutil
import pytest

from test_r210_studio_workflows import wait


@pytest.fixture
def vocal_studio(tmp_path,monkeypatch):
    from test_r210_studio_workflows import studio
    return studio.__wrapped__(tmp_path,monkeypatch)


def test_settings_refuse_unverified_language_and_parameters():
    from app.vocal_synthesis import Settings
    for options in ({'language':'it'},{'voicebank':'untrusted'},{'seed':123},{'formant':float('nan')},{'syllables':['a'*501]}):
        with pytest.raises(ValueError):Settings.model_validate(options)


@pytest.mark.skipif(not os.getenv('MTA_TEST_VOCAL_BANKS'),reason='Requires explicitly installed, hash-verified CC0 voicebank and compiled core')
def test_real_singing_queue_atomic_midi_audio_reopen(vocal_studio,monkeypatch):
    studio=vocal_studio
    from app import auth,storage
    monkeypatch.setenv('MTA_DATA_DIR',str(auth.data_root()))
    source=Path(os.environ['MTA_TEST_VOCAL_BANKS'])
    target=auth.data_root()/'.studio-models/oddvoices';target.mkdir(parents=True)
    for name in ('air.voice','air.json','cmudict-0.7b'):shutil.copyfile(source/name,target/name)
    project,client=studio
    project.tracks[0].midi_route='none';storage.save_project(project)
    response=client.post(f'/api/projects/{project.id}/ai-studio/jobs',headers={'X-MTA-Request':'1'},json={
        'operation':'vocal-synthesis','track_ids':['melody'],'start_ms':500,'end_ms':2500,
        'settings':{'voicebank':'air','language':'vocalise','vocalise':'A'}})
    assert response.status_code==200,response.text
    jid=response.json()['job_id'];state=wait(studio,jid)
    assert state['job']['state']=='completed',state['job']['message']
    assert state['imported']
    saved=storage.load_project(project.id)
    assert len(saved.tracks)==3
    vocal=next(t for t in saved.tracks if t.kind=='audio')
    assert vocal.clips[0].timeline_start_ms==500
    assert len(vocal.music_generation['bank_sha256'])==64
    guide=next(t for t in saved.tracks if t.kind=='midi' and t.id!='melody')
    assert guide.midi_route=='none'
    import soundfile as sf
    import numpy as np
    pcm,rate=sf.read(storage.audio_path(saved.id,vocal.filename))
    assert rate==48000 and np.max(np.abs(pcm))>.001
    from app.audio_engine import render_mix
    mix=auth.data_root()/'singing-project.wav'
    render_mix(saved,storage.audio_path,mix,fmt='wav')
    mixed,sample_rate=sf.read(mix)
    assert np.max(np.abs(mixed))>.001
    assert np.max(np.abs(mixed[:int(sample_rate*.45)]))<1e-5
    assert state['job']['cpu_seconds']>0
    import io,zipfile
    artifact=client.get(f'/api/projects/{project.id}/ai-studio/jobs/{jid}/artifacts.zip')
    assert artifact.status_code==200 and 'no-store' in artifact.headers['cache-control']
    with zipfile.ZipFile(io.BytesIO(artifact.content)) as archive:
        assert set(archive.namelist())=={'music.json','singing.json','voice-1.wav'}
    rev=client.get(f'/api/projects/{project.id}/midi/revision').json()['revision']
    for _ in range(2):
        value=client.post(f'/api/projects/{project.id}/ai-studio/jobs/{jid}/import',headers={'X-MTA-Request':'1'},json={'expected_revision':rev})
        assert value.status_code==200,value.text
    assert len(storage.load_project(project.id).tracks)==3
    removed=client.delete('/api/native/ai/studio/voicebanks/air',headers={'X-MTA-Request':'1'})
    assert removed.status_code==200,removed.text
    assert not (target/'air.voice').exists() and not (target/'cmudict-0.7b').exists()
    assert storage.audio_path(project.id,vocal.filename).is_file()
