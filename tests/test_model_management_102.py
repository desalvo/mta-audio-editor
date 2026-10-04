from pathlib import Path
import json

def test_model_updater_has_blacklist_and_catalog(monkeypatch,tmp_path):
    import app.model_updater as m
    monkeypatch.setattr(m,'BLACKLIST_FILE',tmp_path/'blacklist.json')
    monkeypatch.setattr(m,'COREML_DIR',tmp_path/'coreml');monkeypatch.setattr(m,'ONNX_DIR',tmp_path/'onnx');monkeypatch.setattr(m,'SERVER_DIR',tmp_path/'server')
    assert m.load_blacklist()==set()
    result=m.blacklist_model('htdemucs_6s');assert result['blacklisted'] is True;assert 'htdemucs_6s' in m.load_blacklist()
    assert m.unblacklist_model('htdemucs_6s')['blacklisted'] is False
    assert 'htdemucs' in m.OFFICIAL_DEMUCS_MODELS and 'mdx_extra' in m.OFFICIAL_DEMUCS_MODELS

def test_plugins_hide_blacklisted_model(monkeypatch,tmp_path):
    import app.model_updater as m
    from app.plugins import DemucsStemSplitter
    monkeypatch.setattr(m,'BLACKLIST_FILE',tmp_path/'blacklist.json');m.save_blacklist({'htdemucs_6s'})
    assert 'htdemucs_6s' not in [p['model'] for p in DemucsStemSplitter._model_profiles()]

def test_admin_and_client_model_management_surfaces_exist():
    root=Path(__file__).resolve().parents[1]
    main=(root/'app/main.py').read_text();admin=(root/'app/templates/admin.html').read_text();js=(root/'app/static/app.js').read_text()
    assert '/api/admin/demucs-models/{model_id}/blacklist' in main
    assert 'Modelli AI' in admin and 'modelsBody' in admin
    assert 'openNativeModelManager' in js and 'delete_local_model' in js
    ios=(root/'mobile/ios/MTAEditorMobile/MobileWebViewController.swift').read_text();android=(root/'mobile/android/app/src/main/java/com/desalvo/mtaaudioeditor/mobile/DemucsModelManager.java').read_text()
    assert 'showDemucsModelManager' in ios and 'Delete local model' in ios
    assert 'deleteLocal' in android and 'forceUpdate' in android

def test_model_updater_normalization_targets_and_catalog(monkeypatch,tmp_path):
    import app.model_updater as m
    monkeypatch.setattr(m,'ROOT',tmp_path)
    monkeypatch.setattr(m,'COREML_DIR',tmp_path/'coreml');monkeypatch.setattr(m,'ONNX_DIR',tmp_path/'onnx');monkeypatch.setattr(m,'SERVER_DIR',tmp_path/'server')
    monkeypatch.setattr(m,'BLACKLIST_FILE',tmp_path/'blacklist.json');monkeypatch.setattr(m,'CATALOG_FILE',tmp_path/'catalog.json')
    manifest={'version':'x','models':[
        {'id':'ios-a','platform':'ios','stem_count':4,'url':'https://x/a','sha256':'a'*64,'display_name':'A'},
        {'id':'and-a','platform':'android','stem_count':6,'url':'https://x/b','sha256':'b'*64},
        {'id':'desk','platform':'native','stem_count':4,'url':'https://x/c.zip','sha256':'c'*64},
        {'id':'bad','platform':'ios','stem_count':65,'url':'https://x/d','sha256':'d'*64},
    ]}
    entries=m._normalize_manifest(manifest)
    assert [x['id'] for x in entries]==['ios-a','and-a','desk']
    assert m._target_for(entries[0])==tmp_path/'coreml/ios-a.mlmodel'
    assert m._target_for(entries[1])==tmp_path/'onnx/and-a.onnx'
    assert m._target_for(entries[2])==tmp_path/'server/desk.zip'
    m._atomic_write(m.CATALOG_FILE,(json.dumps({'models':entries})+'\n').encode())
    cat=m.public_catalog('ios')
    assert cat['models'][0]['id']=='ios-a' and not cat['models'][0]['installed_on_server']
    m.save_blacklist({'ios-a'})
    assert m.public_catalog('ios')['models']==[]


def test_install_delete_and_force_update_paths(monkeypatch,tmp_path):
    import hashlib
    import app.model_updater as m
    monkeypatch.setattr(m,'COREML_DIR',tmp_path/'coreml');monkeypatch.setattr(m,'ONNX_DIR',tmp_path/'onnx');monkeypatch.setattr(m,'SERVER_DIR',tmp_path/'server')
    monkeypatch.setattr(m,'BLACKLIST_FILE',tmp_path/'blacklist.json');monkeypatch.setattr(m,'CATALOG_FILE',tmp_path/'catalog.json')
    payload=b'model-bytes';sha=hashlib.sha256(payload).hexdigest()
    item={'id':'ios-model','model':'ios-model','platform':'ios','stem_count':4,'stem_labels':['a','b','c','d'],'display_name':'IOS','engine':'demucs','version':'1','url':'https://models.invalid/a','sha256':sha,'_legacy_key':''}
    monkeypatch.setattr(m,'_read_url',lambda url: payload)
    result={'updated':[],'unchanged':[],'errors':[]}
    m._install_item(item,result)
    assert result['updated']==['ios:ios-model']
    assert (tmp_path/'coreml/ios-model.mlmodel').read_bytes()==payload
    result2={'updated':[],'unchanged':[],'errors':[]};m._install_item(item,result2)
    assert result2['unchanged']==['ios:ios-model']
    removed=m.delete_model_artifacts('ios-model')
    assert removed and not (tmp_path/'coreml/ios-model.mlmodel').exists()
    try:m._safe_id('!!!')
    except ValueError:pass
    else:assert False


def test_native_bundle_creation_and_blacklist_cleanup(monkeypatch,tmp_path):
    import zipfile
    import app.model_updater as m
    monkeypatch.setattr(m,'SERVER_DIR',tmp_path/'server');monkeypatch.setattr(m,'BLACKLIST_FILE',tmp_path/'blacklist.json')
    checkpoints=m.SERVER_DIR/'torch-hub/checkpoints';checkpoints.mkdir(parents=True)
    cp=checkpoints/'abcd1234-feedbeef.th';cp.write_bytes(b'weights')
    yaml=tmp_path/'testmodel.yaml';yaml.write_text("models: ['abcd1234']\n")
    monkeypatch.setattr(m,'_demucs_signatures',lambda name:(yaml,['abcd1234']))
    bundle=m._server_bundle('testmodel');assert bundle and bundle.is_file()
    with zipfile.ZipFile(bundle) as z:assert set(z.namelist())=={'testmodel.yaml','abcd1234-feedbeef.th'}
    assert m.native_bundle('testmodel')==bundle
    result=m.blacklist_model('testmodel')
    assert result['blacklisted'] and not bundle.exists() and not cp.exists()
    assert m.native_bundle('testmodel') is None


def test_update_once_v2_blacklist_and_model_filter(monkeypatch,tmp_path):
    import hashlib,json
    import app.model_updater as m
    monkeypatch.setattr(m,'COREML_DIR',tmp_path/'coreml');monkeypatch.setattr(m,'ONNX_DIR',tmp_path/'onnx');monkeypatch.setattr(m,'SERVER_DIR',tmp_path/'server')
    monkeypatch.setattr(m,'BLACKLIST_FILE',tmp_path/'blacklist.json');monkeypatch.setattr(m,'CATALOG_FILE',tmp_path/'catalog.json')
    monkeypatch.setattr(m,'ENABLED',True);monkeypatch.setattr(m,'MANIFEST_URL','https://models.invalid/manifest.json')
    p1=b'a';p2=b'b';manifest={'version':'v1','models':[
      {'id':'one','platform':'ios','stem_count':4,'url':'https://models.invalid/one','sha256':hashlib.sha256(p1).hexdigest()},
      {'id':'two','platform':'android','stem_count':6,'url':'https://models.invalid/two','sha256':hashlib.sha256(p2).hexdigest()}]}
    mapping={m.MANIFEST_URL:json.dumps(manifest).encode(),'https://models.invalid/one':p1,'https://models.invalid/two':p2}
    monkeypatch.setattr(m,'_read_url',lambda u:mapping[u])
    r=m.update_once({'one'});assert r['updated']==['ios:one'];assert not (tmp_path/'onnx/two.onnx').exists()
    m.save_blacklist({'two'});r=m.update_once();assert 'two' in r['skipped_blacklist']
    assert m.cached_catalog() and m.cached_catalog()[0]['id']=='one'


def test_server_inventory_and_prefetch(monkeypatch,tmp_path):
    import app.model_updater as m
    monkeypatch.setattr(m,'SERVER_DIR',tmp_path/'server');monkeypatch.setattr(m,'BLACKLIST_FILE',tmp_path/'blacklist.json');monkeypatch.setattr(m,'CATALOG_FILE',tmp_path/'catalog.json')
    monkeypatch.setattr(m,'_registry_server_profiles',lambda:[{'id':'fake','model':'fake','stem_count':4,'stem_labels':['a']*4,'display_name':'Fake'}])
    monkeypatch.setattr(m,'_load_server_model',lambda name: object())
    monkeypatch.setattr(m,'_server_bundle',lambda name: (m.SERVER_DIR/'bundles/fake.zip'))
    r={'updated':[],'unchanged':[],'server_ready':[],'skipped_blacklist':[],'errors':[]}
    m._prefetch_server_models(r)
    assert r['server_ready']==['fake']
    inv=m.server_inventory();assert any(x['id']=='fake' and x['installed'] for x in inv['models'])
    m.save_blacklist({'fake'});inv2=m.server_inventory();assert any(x['id']=='fake' and x['blacklisted'] for x in inv2['models'])


def test_background_start_and_https_rejection(monkeypatch):
    import app.model_updater as m
    assert m._https('https://example.test/x') and not m._https('ftp://example.test/x')
    try:m._read_url('http://example.test/x')
    except ValueError:pass
    else:assert False
    class T:
        def __init__(self,*a,**k):self.started=False
        def start(self):self.started=True
    created=[]
    monkeypatch.setattr(m.threading,'Thread',lambda *a,**k:(created.append(T()) or created[-1]))
    monkeypatch.setattr(m,'ENABLED',True);monkeypatch.setattr(m,'_started',False)
    m.start_background_updater();assert m._started and created and created[0].started
