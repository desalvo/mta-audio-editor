"""Persistent model-download admission/recovery regression coverage."""
import threading
from types import SimpleNamespace
import pytest
from app import main, ai_arranger_runtime as queue

@pytest.mark.parametrize('kind', ['lyrics','chords'])
def test_model_download_restore_uses_stable_identity(monkeypatch, kind):
    monkeypatch.setattr(main, 'lyrics_catalog', lambda **kw: {'models':[{'id':'safe-model'}]})
    monkeypatch.setattr(main, 'chords_catalog', lambda **kw: {'models':[{'id':'safe-model'}]})
    called=[]
    monkeypatch.setattr(main, '_ai_model_download_worker', lambda *args: called.append(args))
    job_id = 'recover-download-' + kind
    main.MEDIA_JOBS.pop(job_id, None)
    execute = main._restore_model_download_job('server-models', {'schema_version':1,'kind':kind,'model_id':'safe-model'}, job_id)
    execute(None, threading.Event())
    assert called == [(job_id,kind,'safe-model')]
    main.MEDIA_JOBS.pop(job_id, None)

@pytest.mark.parametrize('change', [
    {'schema_version': 2}, {'kind':'bad'}, {'model_id':'../../bad'},
    {'model_id':''}, {'model_id':123}, {'model_id':'missing'}
])
def test_model_download_rejects_untrusted_payload(monkeypatch, change):
    monkeypatch.setattr(main, 'lyrics_catalog', lambda **kw: {'models':[{'id':'safe-model'}]})
    payload={'schema_version':1,'kind':'lyrics','model_id':'safe-model'}
    payload.update(change)
    with pytest.raises(ValueError):
        main._restore_model_download_job('server-models',payload,'unsafe')

def test_model_download_admission_is_durable(tmp_path, monkeypatch):
    monkeypatch.setattr(queue,'_ROOT',tmp_path)
    monkeypatch.setattr(queue,'_spawn',lambda *args,**kwargs: True)
    monkeypatch.setattr(main,'_actor',lambda request: {'id':'test'})
    job=main._start_ai_model_download_job('lyrics','safe-model',SimpleNamespace())
    assert queue.read_payload(job['id']) == {'schema_version':1,'kind':'lyrics','model_id':'safe-model'}
    assert queue.get(job['id'])['operation']=='download-lyrics-model'
    assert job['cancel_supported'] is True
    main.MEDIA_JOBS.pop(job['id'],None)

def test_model_download_persisted_status(tmp_path,monkeypatch):
    monkeypatch.setattr(queue,'_ROOT',tmp_path)
    monkeypatch.setattr(queue,'_spawn',lambda *args,**kwargs: True)
    monkeypatch.setattr(main,'_actor',lambda request: {'id':'test'})
    job=main._start_ai_model_download_job('chords','safe-model',SimpleNamespace())
    main.MEDIA_JOBS.pop(job['id'],None)
    result=main.media_job_status(job['id'],SimpleNamespace())
    assert result['id']==job['id']
    assert result['kind']=='download-chords-model'

def test_model_download_cancel_after_restart(tmp_path, monkeypatch):
    monkeypatch.setattr(queue, '_ROOT', tmp_path)
    monkeypatch.setattr(queue, '_spawn', lambda *args,**kwargs: True)
    monkeypatch.setattr(main, '_actor', lambda request: {'id':'test'})
    job = main._start_ai_model_download_job('lyrics','safe-model',SimpleNamespace())
    main.MEDIA_JOBS.pop(job['id'],None)
    cancelled=main.cancel_media_job(job['id'],SimpleNamespace())
    assert cancelled['status']=='cancelled'
    assert queue.get(job['id'])['state']=='cancelled'
