"""Application lifecycle with explicitly synthetic model outputs, never neural QA."""
import hashlib
import json
from pathlib import Path
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app import studio_admin,studio_asset_registry as assets,studio_catalog
from tests.test_r210_managed_studio_assets import bundle
from tests.test_r210_studio_workflows import studio,wait  # noqa: F401, F811


def test_managed_upload_requires_role_and_explicit_rights(tmp_path,monkeypatch):
    monkeypatch.setattr(studio_catalog,'root',lambda:tmp_path)
    user={'id':1,'role':'user'}
    app=FastAPI();studio_admin.register_routes(app,lambda request:user)
    client=TestClient(app)
    url='/api/admin/ai/studio/assets/install'
    assert client.post(url+'?accept_licenses=true',content=bundle()[0]).status_code==403
    user['role']='admin'
    assert client.post(url,content=bundle()[0]).status_code==422
    captured={}
    def queue_start(pid,operation,fn,**kwargs):
        captured['fn']=fn;return True,{'state':'queued'}
    monkeypatch.setattr(studio_admin.queue,'start',queue_start)
    response=client.post(url+'?accept_licenses=true',content=bundle()[0]);assert response.status_code==200
    assert list((tmp_path/'managed').glob('.incoming-*'))
    from threading import Event
    captured['fn'](tmp_path/'progress.json',Event())
    assert not list((tmp_path/'managed').glob('.incoming-*'))
    assert not assets.manifest('test-vocoder',verify=True)['enabled']
    assert client.put('/api/admin/ai/studio/assets/test-vocoder',json={'enabled':True}).status_code==422
    assert client.put('/api/admin/ai/studio/assets/test-vocoder',json={'enabled':'true'}).status_code==422
    monkeypatch.setenv('MTA_NATIVE_SINGLE_USER','false')
    assert client.get('/api/native/ai/studio/models').status_code==404


def test_empty_audio_result_completes_without_creating_placeholder_tracks(studio,monkeypatch):  # noqa: F811
    import numpy as np
    import soundfile as sf
    from app import storage,studio_compute,ai_worker_registry
    from app.music_interchange import no_notes
    from app.models import Track,Clip
    p,c=studio
    p.tracks=[Track(id='audio',name='Silent source',filename='silent.wav',kind='audio',duration_ms=1000,
                    clips=[Clip(id='clip',source_end_ms=1000)],clips_initialized=True)]
    sf.write(storage.audio_path(p.id,'silent.wav'),np.zeros(44100),44100);storage.save_project(p)
    monkeypatch.setattr(ai_worker_registry,'resolve_worker',lambda kind:Path(__file__))
    executions=[]
    def infer(*args,**kwargs):
        executions.append(args);return no_notes(),{'usage':{}}
    monkeypatch.setattr(studio_compute,'compute',infer)
    response=c.post(f'/api/projects/{p.id}/ai-studio/jobs',headers={'X-MTA-Request':'1'},json={
        'operation':'audio-to-midi','track_ids':['audio'],'start_ms':0,'end_ms':1000,'auto_import':True})
    assert response.status_code==200,response.text
    jid=response.json()['job_id'];data=wait(studio,jid)
    assert data['job']['state']=='completed',data
    assert len(storage.load_project(p.id).tracks)==1 and not data['imported']
    result=c.get(f'/api/projects/{p.id}/ai-studio/jobs/{jid}/result').json()
    assert result['empty_reason']=='no-notes' and not result['parts']
    revision=c.get(f'/api/projects/{p.id}/midi/revision').json()['revision']
    assert c.post(f'/api/projects/{p.id}/ai-studio/jobs/{jid}/import',headers={'X-MTA-Request':'1'},json={'expected_revision':revision}).status_code==422
    def retry(previous):
        response=c.post(f'/api/projects/{p.id}/ai-studio/jobs',headers={'X-MTA-Request':'1'},json={
            'operation':'audio-to-midi','track_ids':['audio'],'start_ms':0,'end_ms':1000,'auto_import':True,'retry_of':previous})
        assert response.status_code==200,response.text
        result=wait(studio,response.json()['job_id']);assert result['job']['state']=='completed',result
        return response.json()['job_id']
    second=retry(jid);assert len(executions)==1
    monkeypatch.setenv('MTA_STUDIO_TEST_EPOCH','different-runtime')
    retry(second);assert len(executions)==2



def test_bundle_builder_streams_pinned_bytes_and_notices(tmp_path):
    from scripts.build_studio_bundle import build
    source=tmp_path/'source';source.mkdir()
    data,value=bundle()
    import zipfile,io
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        for name in value['files']:(source/name).write_bytes(archive.read(name))
    template=tmp_path/'template.json';value['files']=list(value['files']);template.write_text(json.dumps(value))
    output=tmp_path/'reviewed.zip';build(template,source,output)
    with zipfile.ZipFile(output) as archive:
        manifest=json.loads(archive.read('manifest.json'))
        for name,receipt in manifest['files'].items():assert hashlib.sha256(archive.read(name)).hexdigest()==receipt['sha256']


def test_explicit_syllable_phones_require_actual_reviewed_inventory(tmp_path,monkeypatch):
    from app.diffsinger_bridge import select_score_phonemes
    from app.vocal_synthesis import Settings
    import pytest
    profile={'schema':'mta-bank-phonemes-1','language':'fr','bank_sha256':'a'*64,
             'inventory':['SP','a','l'],'vowels':['a'],'ipa_map':{'a':['a'],'l':['l']}}
    # Use the contract loader here; actual profile-file validation is separately tested.
    monkeypatch.setattr('app.vocal_phonemizer.load_profile',lambda *a,**k:profile)
    cfg=Settings(backend='diffsinger',language='fr',explicit_phones=[['l','a']],syllables=['A'])
    assert cfg.explicit_phones==[['l','a']]
    request={'language':'fr','explicit_bank_phones':True,'notes':[{'phonemes':['l','a']}]}
    assert select_score_phonemes(request)==request
    with pytest.raises(ValueError):select_score_phonemes({**request,'notes':[{'phonemes':['unsupported']}]})
    with pytest.raises(ValueError):Settings(backend='oddvoices',explicit_phones=[['a']])
