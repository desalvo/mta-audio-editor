"""Actual track route, edited input and interval import with a synthetic separator."""
import shutil
import numpy as np
import soundfile as sf
from fastapi.testclient import TestClient


def test_track_route_preserves_profile_interval_and_original(tmp_path,monkeypatch,local_native_ai):
    from app import main,storage
    from app.models import Clip,Track
    from app.bass_roformer_runtime import profiles
    monkeypatch.setattr(storage,'ROOT',tmp_path.resolve())
    monkeypatch.setenv('MTA_ALLOW_INSECURE_NO_AUTH','true')
    project=storage.create_project('Bass interval')
    source=storage.audio_path(project.id,'source.wav')
    sf.write(source,np.ones((44100,2),dtype='float32')*.5,44100,subtype='FLOAT')
    project.tracks=[Track(id='source',name='Original',filename=source.name,duration_ms=1000,gain_db=-6,
        clips=[Clip(id='part',source_start_ms=0,source_end_ms=800,timeline_start_ms=200)])]
    storage.save_project(project)
    seen={}
    class Splitter:
        @staticmethod
        def available(): return True
        @staticmethod
        def status(): return {'models':['htdemucs','bs-roformer-bass','bs-roformer-4stem'],
            'supported_stem_counts':[2,4], 'model_profiles':profiles()}
        @staticmethod
        def split(source,output_dir,model,stem_count,**kwargs):
            seen.update(model=model,count=stem_count,audio=sf.read(source)[0])
            output_dir.mkdir(parents=True,exist_ok=True)
            paths=[output_dir/'bass.wav',output_dir/'accompaniment.wav']
            for p in paths:shutil.copyfile(source,p)
            return paths
    monkeypatch.setattr(main,'STEM_SPLITTER',Splitter)
    monkeypatch.setattr(main,'_enqueue_existing_ai_job',lambda job,work,**kwargs:work())
    main.STEM_JOBS.clear()
    client=TestClient(main.app,headers={'X-MTA-Request':'1'})
    response=client.post(f'/api/projects/{project.id}/tracks/source/stem-jobs?model=bs-roformer-bass&stem_count=2&stem_targets=bass&range_start_ms=200&range_end_ms=500')
    assert response.status_code==200,response.text
    assert response.json()['status']=='completed',response.text
    assert seen['model']=='bs-roformer-bass' and seen['count']==2
    assert len(seen['audio'])==13230 and .24<float(np.mean(seen['audio']))<.26
    saved=storage.load_project(project.id)
    assert len(saved.tracks)==2 and saved.tracks[0].id=='source'
    assert saved.tracks[1].type=='bass' and saved.tracks[1].clips[0].timeline_start_ms==200
    assert source.is_file()
    assert client.post(f'/api/projects/{project.id}/tracks/source/stem-jobs?model=bs-roformer-bass&stem_count=6').status_code==400
    assert client.post(f'/api/projects/{project.id}/tracks/source/stem-jobs?model=bs-roformer-bass&range_start_ms=500&range_end_ms=200').status_code==400
    assert client.post(f'/api/projects/{project.id}/tracks/source/stem-jobs?model=bs-roformer-bass&range_end_ms=2000').status_code==400
