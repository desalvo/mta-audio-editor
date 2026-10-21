"""Model administration contracts; data-only test bytes, no model inference."""
import hashlib
import io
import json
from pathlib import Path
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app import model_asset_admin as models,studio_asset_registry as assets,auth
from app import ai_arranger_runtime as queue
from app.model_asset_admin_routes import register_routes

LEGACY_ROOTS=models._roots


@pytest.fixture
def workspace(tmp_path,monkeypatch):
    data=tmp_path/'data';data.mkdir()
    monkeypatch.setattr(auth,'DATA_ROOT',data)
    monkeypatch.setattr(queue,'_ROOT',tmp_path/'queue')
    monkeypatch.setenv('HF_HOME',str(tmp_path/'hf'))
    monkeypatch.delenv('HF_HUB_CACHE',raising=False)
    monkeypatch.delenv('MTA_STUDIO_YOURMT3_RUNTIME',raising=False)
    monkeypatch.delenv('MTA_STUDIO_MRMT3_RUNTIME',raising=False)
    for key in ('MTA_NEURAL_SINGER_CHECKPOINT','MTA_DIFFSINGER_VOCODER','MTA_DIFFSINGER_PHONEMES','MTA_DIFFSINGER_LEXICON'):monkeypatch.delenv(key,raising=False)
    monkeypatch.setattr(models,'_roots',lambda:[])
    monkeypatch.setattr(models,'sources',lambda:[])
    return data


def managed_bundle():
    files={'model.pt':b'test checkpoint','LICENSE.txt':b'Test license'}
    value={'schema':'mta-studio-bundle-1','id':'test-vocoder','name':'Test','kind':'vocoder','languages':['en'],
           'files':{name:{'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()} for name,raw in files.items()},
           'bindings':{'checkpoint':'model.pt'},'components':{'checkpoint':'test-checkpoint'},
           'component_files':{'checkpoint':list(files)},'licenses':[{'policy_model':'test-checkpoint','notice':'LICENSE.txt','evidence_url':'https://example.com/permission'}]}
    import zipfile
    output=io.BytesIO()
    with zipfile.ZipFile(output,'w') as z:
        z.writestr('manifest.json',json.dumps(value))
        for name,raw in files.items():z.writestr(name,raw)
    assets.install(output.getvalue())
    return assets.root()/'test-vocoder',files


def pin(raw=b'checkpoint'):
    return {'id':'test-source','engine':'rvc','consumers':['rvc','seed-vc'],'repo_id':'author/model',
            'revision':'a'*40,'filename':'model.bin','bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest(),
            'source_kind':'huggingface-model','url':'https://huggingface.co/author/model/resolve/'+'a'*40+'/model.bin',
            'source_url':'https://huggingface.co/author/model/tree/'+'a'*40}


def test_missing_manifest_files_remain_visible_and_restore_keeps_disabled(workspace,tmp_path):
    folder,files=managed_bundle();(folder/'model.pt').unlink()
    row=next(row for row in models.records()[0] if row['name']=='model.pt')
    assert not row['installed'] and models.public(row)['can_restore']
    source=tmp_path/'restore';source.write_bytes(files['model.pt'])
    restored=models.publish(row,source,row['_expected'])
    assert restored['sha256']==hashlib.sha256(files['model.pt']).hexdigest()
    assert (folder/'model.pt').read_bytes()==files['model.pt']
    assert json.loads((folder/'receipt.json').read_text())['enabled'] is False


def test_wrong_restore_never_replaces_installed_model(workspace,tmp_path):
    folder,files=managed_bundle();row=next(row for row in models.records()[0] if row['name']=='model.pt')
    source=tmp_path/'bad';source.write_bytes(b'x'*len(files['model.pt']))
    with pytest.raises(ValueError,match='SHA-256'):models.publish(row,source,row['_expected'])
    assert (folder/'model.pt').read_bytes()==files['model.pt']


def test_selective_delete_does_not_remove_sibling_or_manifest(workspace):
    folder,files=managed_bundle()
    row=next(row for row in models.records()[0] if row['name']=='model.pt')
    models.remove(row['id'])
    assert not (folder/'model.pt').exists() and (folder/'LICENSE.txt').read_bytes()==files['LICENSE.txt']
    assert (folder/'manifest.json').is_file() and not assets.manifest('test-vocoder')['enabled']
    assert any(not r['installed'] and r['name']=='model.pt' for r in models.records()[0])


def test_pinned_source_is_missing_visible_and_shared_between_engines(workspace,monkeypatch):
    monkeypatch.setattr(models,'sources',lambda:[pin()])
    data=models.inventory(engine='seed-vc')
    assert data['total']==1 and not data['files'][0]['installed']
    assert data['files'][0]['can_download'] and data['files'][0]['engines']==['rvc','seed-vc']
    assert not any(k.startswith('_') for k in data['files'][0])


def test_pagination_returns_all_files_without_silent_truncation(workspace,tmp_path,monkeypatch):
    root=tmp_path/'cache';root.mkdir()
    for i in range(251):(root/f'model-{i:03}.pt').write_bytes(b'x')
    monkeypatch.setattr(models,'_roots',lambda:[('rvc',root)])
    pages=[models.inventory(offset=i,limit=100) for i in (0,100,200)]
    assert all(p['total']==251 and p['complete'] for p in pages)
    assert len({r['id'] for p in pages for r in p['files']})==251
    assert pages[-1]['next_offset'] is None


def test_duplicate_overlapping_roots_have_one_file_identity(workspace,tmp_path,monkeypatch):
    root=tmp_path/'cache';nested=root/'models';nested.mkdir(parents=True);(nested/'file.pt').write_bytes(b'x')
    monkeypatch.setattr(models,'_roots',lambda:[('rvc',root),('rvc',nested)])
    assert models.inventory()['total']==1


def test_credentials_and_directory_links_are_not_model_files(workspace,tmp_path,monkeypatch):
    root=tmp_path/'cache';root.mkdir();(root/'token').write_text('secret')
    outside=tmp_path/'outside';outside.mkdir();(outside/'key').write_text('secret')
    (root/'linked').symlink_to(outside,target_is_directory=True)
    (root/'real.pt').write_bytes(b'model')
    monkeypatch.setattr(models,'_roots',lambda:[('rvc',root)])
    assert [r['name'] for r in models.inventory()['files']]==['real.pt']


def test_file_link_escape_is_reported_not_exposed(workspace,tmp_path,monkeypatch):
    root=tmp_path/'cache';root.mkdir();outside=tmp_path/'secret';outside.write_text('secret')
    (root/'model.pt').symlink_to(outside)
    monkeypatch.setattr(models,'_roots',lambda:[('rvc',root)])
    data=models.inventory();assert not data['complete'] and data['files']==[]


def test_hf_alias_delete_preserves_shared_weight_blob(workspace,tmp_path,monkeypatch):
    root=tmp_path/'hub';snap=root/('models--author--model/snapshots/'+'a'*40);snap.mkdir(parents=True)
    blob=root/'models--author--model/blobs'/'weight';blob.parent.mkdir();blob.write_bytes(b'model')
    path=snap/'model.bin';path.symlink_to(blob)
    monkeypatch.setattr(models,'_roots',lambda:[('rvc',root)])
    row=next(r for r in models.records()[0] if r['_path']==path)
    assert row['source']['revision']=='a'*40
    models.remove(row['id']);assert not path.exists() and blob.read_bytes()==b'model'


def test_hf_snapshot_restore_rejects_directory_link(workspace,tmp_path,monkeypatch):
    source=pin();monkeypatch.setattr(models,'sources',lambda:[source]);row=models.records()[0][0]
    outside=tmp_path/'outside';outside.mkdir()
    root=row['_root'];root.mkdir(parents=True);(root/'models--author--model').symlink_to(outside,target_is_directory=True)
    with pytest.raises(ValueError):models.find(row['id'])
    assert list(outside.iterdir())==[]


def test_active_job_protects_model_bytes(workspace):
    folder,files=managed_bundle();row=next(r for r in models.records()[0] if r['name']=='model.pt')
    with queue._db() as con:
        con.execute("INSERT INTO jobs(job_id,project_id,operation,state,rank,created_at,phase,message) VALUES('active','project','worker:studio-music','running',1,0,'running','')")
    with pytest.raises(ValueError,match='running AI jobs'):models.remove(row['id'])
    assert (folder/'model.pt').read_bytes()==files['model.pt']


def test_verified_download_is_bounded_and_never_activates_model(workspace,tmp_path,monkeypatch):
    raw=b'checkpoint';source=pin(raw);monkeypatch.setattr(models,'sources',lambda:[source])
    from app import secure_https
    monkeypatch.setattr(secure_https,'https_urlopen',lambda *a,**k:io.BytesIO(raw))
    row=models.records()[0][0];result=models.download(row['id'])
    assert result['enabled'] is False and models.find(row['id'])['_path'].read_bytes()==raw


def test_oversized_download_does_not_publish_partial_bytes(workspace,monkeypatch):
    source=pin();monkeypatch.setattr(models,'sources',lambda:[source])
    from app import secure_https
    monkeypatch.setattr(secure_https,'https_urlopen',lambda *a,**k:io.BytesIO(b'bad'*100))
    row=models.records()[0][0]
    with pytest.raises(ValueError,match='exceeds pinned'):models.download(row['id'])
    assert not models.find(row['id'])['_path'].exists()


def test_mr_receipt_files_are_visible_when_missing_and_unverified_after_change(workspace,tmp_path,monkeypatch):
    root=tmp_path/'mr';root.mkdir();raw=b'checkpoint';(root/'mta-runtime.json').write_text(json.dumps({
        'model':'mr-mt3','tested':True,'files':{'checkpoint.pt':hashlib.sha256(raw).hexdigest()}}))
    monkeypatch.setenv('MTA_STUDIO_MRMT3_RUNTIME',str(root));row=models.records()[0][0]
    assert row['engine']=='mr-mt3' and not row['installed']
    restore=tmp_path/'restore';restore.write_bytes(raw);models.publish(row,restore,row['_expected'])
    assert json.loads((root/'mta-runtime.json').read_text())['tested'] is False


def client(role):
    app=FastAPI();register_routes(app,lambda request:{'id':1,'role':role});return TestClient(app)


def test_administration_requires_admin_even_for_inventory(workspace):
    response=client('user').get('/api/admin/ai/model-assets')
    assert response.status_code==403


def test_paths_and_urls_cannot_be_supplied_as_file_ids(workspace):
    for identifier in ('etc-passwd','https:example','unknown'):
        assert client('admin').delete('/api/admin/ai/model-assets/'+identifier).status_code==409


def test_download_requires_exact_explicit_consent(workspace,monkeypatch):
    monkeypatch.setattr(models,'sources',lambda:[pin()]);identifier=models.records()[0][0]['id']
    response=client('admin').post('/api/admin/ai/model-assets/'+identifier+'/download',json={'accept_licenses':False})
    assert response.status_code==422
    response=client('admin').post('/api/admin/ai/model-assets/'+identifier+'/download',json={'accept_licenses':True,'url':'https://example.com'})
    assert response.status_code==422


def test_export_serves_only_selected_regular_model(workspace):
    folder,files=managed_bundle();row=next(r for r in models.records()[0] if r['name']=='model.pt')
    response=client('admin').get('/api/admin/ai/model-assets/'+row['id']+'/file')
    assert response.content==files['model.pt'] and response.headers['cache-control']=='no-store'


def test_source_catalog_pins_are_complete_and_do_not_grant_licenses():
    source=Path(models.__file__).with_name('studio_assets')/'admin_external_sources.json'
    document=json.loads(source.read_text());rows=document['sources']
    assert len(rows)>=128 and not document['license_approval_granted']
    assert len({r['id'] for r in rows})==len(rows)
    for row in rows:
        assert row['url'].startswith('https://') and len(row['sha256'])==64 and row['bytes']>=0
        assert row['license_review_required'] is True
    assert any('hubert' in r['filename'].lower() or r.get('role')=='hubert-encoder' for r in rows)
    assert any('rmvpe' in r['filename'].lower() for r in rows)
    assert any('campplus' in r['repo_id'].lower() for r in rows)


def test_shared_hf_blob_cannot_be_deleted_through_its_storage_row(workspace,tmp_path,monkeypatch):
    root=tmp_path/'hub';snap=root/('models--author--model/snapshots/'+'a'*40);snap.mkdir(parents=True)
    blob=root/'models--author--model/blobs'/'weight';blob.parent.mkdir();blob.write_bytes(b'model')
    path=snap/'model.bin';path.symlink_to(blob)
    monkeypatch.setattr(models,'_roots',lambda:[('rvc',root)])
    row=next(r for r in models.records()[0] if r['_path']==blob)
    with pytest.raises(ValueError,match='still referenced'):models.remove(row['id'])
    assert blob.read_bytes()==path.read_bytes()==b'model'


def test_mr_interpreter_exact_restore_preserves_executable_mode(workspace,tmp_path,monkeypatch):
    root=tmp_path/'mr';root.mkdir();raw=b'test interpreter bytes'
    (root/'mta-runtime.json').write_text(json.dumps({'model':'mr-mt3','tested':True,'files':{},'python_sha256':hashlib.sha256(raw).hexdigest()}))
    monkeypatch.setenv('MTA_STUDIO_MRMT3_RUNTIME',str(root))
    row=next(r for r in models.records()[0] if r['origin']=='runtime-interpreter')
    source=tmp_path/'restore';source.write_bytes(raw);models.publish(row,source,row['_expected'])
    import os
    assert os.access(root/'bin/python',os.X_OK)
    assert not json.loads((root/'mta-runtime.json').read_text())['tested']



def test_mr_original_download_does_not_require_or_create_runtime_receipt(workspace,monkeypatch):
    raw=b'mr original checkpoint';source=pin(raw);source['engine']='mr-mt3';source['consumers']=['mr-mt3']
    monkeypatch.setattr(models,'sources',lambda:[source])
    from app import secure_https
    monkeypatch.setattr(secure_https,'https_urlopen',lambda *a,**k:io.BytesIO(raw))
    row=models.records()[0][0];result=models.download(row['id'])
    assert result['enabled'] is False and models.find(row['id'])['_path'].read_bytes()==raw
    assert not (row['_root']/'mta-runtime.json').exists()


def test_corrupt_bundle_can_be_removed_without_deleting_neighbor(workspace):
    folder,_=managed_bundle();neighbor=assets.root()/'neighbor';neighbor.mkdir();(neighbor/'keep').write_text('keep')
    (folder/'manifest.json').write_text('corrupt manifest')
    result=models.remove_bundle('test-vocoder')
    assert result['removed'] and not folder.exists() and (neighbor/'keep').read_text()=='keep'


def test_bundle_removal_rejects_links_to_other_directories(workspace,tmp_path):
    outside=tmp_path/'outside';outside.mkdir();(outside/'keep').write_text('keep')
    (assets.root()/'unsafe').symlink_to(outside,target_is_directory=True)
    with pytest.raises(ValueError,match='unsafe'):models.remove_bundle('unsafe')
    assert (outside/'keep').exists()



@pytest.mark.parametrize('state',['queued','blocked'])
def test_queued_inference_protects_model_files(workspace,state):
    folder,files=managed_bundle();row=next(r for r in models.records()[0] if r['name']=='model.pt')
    with queue._db() as con:
        con.execute("INSERT INTO jobs(job_id,project_id,operation,state,rank,created_at,phase,message) VALUES('pending','project','worker:studio-music',?,1,0,'queued','')",(state,))
    with pytest.raises(ValueError,match='queued inference jobs'):models.remove(row['id'])
    assert (folder/'model.pt').read_bytes()==files['model.pt']


def test_queued_model_maintenance_does_not_deadlock_file_restoration(workspace,tmp_path):
    folder,files=managed_bundle();row=next(r for r in models.records()[0] if r['name']=='model.pt')
    with queue._db() as con:
        con.execute("INSERT INTO jobs(job_id,project_id,operation,state,rank,created_at,phase,message) VALUES('pending','studio-models','worker:studio-install','queued',1,0,'queued','')")
    source=tmp_path/'restore';source.write_bytes(files['model.pt'])
    assert models.publish(row,source,row['_expected'])['downloaded']



def test_overlapping_hf_root_cannot_erase_managed_owner_and_restore_hash(workspace,monkeypatch):
    folder,_=managed_bundle()
    # A broad cache scan reaching the same physical files must not erase the
    # manifest association used to invalidate readiness on deletion/restore.
    monkeypatch.setattr(models,'_roots',lambda:[('shared',folder)])
    row=next(r for r in models.records()[0] if r['name']=='model.pt')
    assert row['_asset']=='test-vocoder' and row['_expected']['sha256']
    receipt=folder/'receipt.json';value=json.loads(receipt.read_text());value['enabled']=True;receipt.write_text(json.dumps(value))
    models.remove(row['id'])
    assert not json.loads(receipt.read_text())['enabled']



def test_legacy_diffsinger_root_exposes_all_experiment_weights_and_configs(tmp_path,monkeypatch,workspace):
    from app import model_asset_admin as models
    folder=tmp_path/'legacy';folder.mkdir()
    (folder/'exp').mkdir();(folder/'exp/variance.ckpt').write_bytes(b'contract')
    (folder/'exp/config.yaml').write_text('test: true')
    monkeypatch.setenv('MTA_DIFFSINGER_ROOT',str(folder))
    roots=LEGACY_ROOTS()
    assert ('diffsinger',folder) in roots
    monkeypatch.setattr(models,'_roots',lambda:[('diffsinger',folder)])
    # Known manifest/catalog directories still use the test's isolated data root.
    rows,_=models.records()
    assert any(r['engine']=='diffsinger' and r['name']=='exp/variance.ckpt' for r in rows)
    assert any(r['engine']=='diffsinger' and r['name']=='exp/config.yaml' for r in rows)
