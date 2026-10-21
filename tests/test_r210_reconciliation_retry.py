"""Workflow checkpoint regression, independent of model-quality tests."""
from pathlib import Path
from app.music_interchange import MusicResult,MusicPart
from app.models import MidiNote


def test_retry_resumes_completed_model_without_reexecuting_it(tmp_path,monkeypatch):
    from test_r210_studio_workflows import studio,wait
    from app import storage,studio_compute,ai_worker_registry
    import numpy as np
    import soundfile as sf
    context=studio.__wrapped__(tmp_path,monkeypatch);project,client=context
    track=project.tracks[0];track.kind='audio';track.midi_notes=[]
    sf.write(storage.audio_path(project.id,track.filename),np.sin(np.arange(132300)*2*np.pi*440/44100)*.1,44100)
    storage.save_project(project)
    monkeypatch.setattr(ai_worker_registry,'resolve_worker',lambda kind:Path(__file__))
    monkeypatch.delenv('MTA_STUDIO_TRANSCRIBER',raising=False)
    calls=[]
    def compute(owner,kind,plan,**kwargs):
        calls.append(kind)
        if kind.endswith('basic-pitch') and calls.count(kind)==1:raise RuntimeError('Second model interrupted')
        part=MusicPart(id='melody',name='Melody',program=0,source_model=kind,
            notes=[MidiNote(id='note',pitch=60,duration_ms=500)])
        return MusicResult(parts=[part]),{'usage':{'cpu_seconds':1.}}
    monkeypatch.setattr(studio_compute,'compute',compute)
    body={'operation':'audio-to-midi','mode':'accurate','track_ids':['melody'],'end_ms':3000,'auto_import':False}
    def start(request):
        response=client.post(f'/api/projects/{project.id}/ai-studio/jobs',headers={'X-MTA-Request':'1'},json=request)
        assert response.status_code==200,response.text
        return response.json()['job_id']
    failed=start(body);state=wait(context,failed)
    assert state['job']['state']=='failed' and 'Second model' in state['job']['message']
    recovered=start({**body,'retry_of':failed});state=wait(context,recovered)
    assert state['job']['state']=='completed',state
    assert calls.count('audio-to-midi-yourmt3')==1
    assert calls.count('audio-to-midi-basic-pitch')==2
    result=client.get(f'/api/projects/{project.id}/ai-studio/jobs/{recovered}/result').json()
    assert len(result['parts'])==1 and len(result['alternatives'])==2
    # A changed request must not reuse another parameter set's checkpoint.
    changed=start({**body,'retry_of':failed,'settings':{'onset_threshold':.6}})
    assert wait(context,changed)['job']['state']=='completed'
    assert calls.count('audio-to-midi-yourmt3')==2
