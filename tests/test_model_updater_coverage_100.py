import hashlib, json
import app.model_updater as mu


def test_https_and_atomic_write(tmp_path):
    assert mu._https('https://example.invalid/model')
    assert not mu._https('http://example.invalid/model')
    target=tmp_path/'nested'/'model.bin'
    mu._atomic_write(target,b'abc')
    assert target.read_bytes()==b'abc'
    mu._atomic_write(target,b'def')
    assert target.read_bytes()==b'def'


def test_update_once_installs_and_then_detects_unchanged(tmp_path, monkeypatch):
    ios=b'coreml-model'; android=b'onnx-model'
    manifest={
        'version':'v42',
        'models':{
            'ios':{'4':{'url':'https://models.invalid/demucs-4.mlmodel','sha256':hashlib.sha256(ios).hexdigest()}},
            'android':{'4':{'url':'https://models.invalid/demucs-4.onnx','sha256':hashlib.sha256(android).hexdigest()}},
        },
    }
    mapping={
        mu.MANIFEST_URL:json.dumps(manifest).encode(),
        'https://models.invalid/demucs-4.mlmodel':ios,
        'https://models.invalid/demucs-4.onnx':android,
    }
    monkeypatch.setattr(mu,'ROOT',tmp_path)
    monkeypatch.setattr(mu,'COREML_DIR',tmp_path/'coreml')
    monkeypatch.setattr(mu,'ONNX_DIR',tmp_path/'onnx')
    monkeypatch.setattr(mu,'SERVER_DIR',tmp_path/'server')
    monkeypatch.setattr(mu,'BLACKLIST_FILE',tmp_path/'blacklist.json')
    monkeypatch.setattr(mu,'CATALOG_FILE',tmp_path/'catalog.json')
    monkeypatch.setattr(mu,'ENABLED',True)
    monkeypatch.setattr(mu,'_read_url',lambda u:mapping[u])
    result=mu.update_once()
    assert sorted(result['updated'])==['android:4','ios:4']
    assert (tmp_path/'coreml/demucs-4.mlmodel').read_bytes()==ios
    assert (tmp_path/'onnx/demucs-4.onnx').read_bytes()==android
    assert json.loads((tmp_path/'coreml/demucs-4.mlmodel.json').read_text())['version']=='v42'
    result2=mu.update_once()
    assert sorted(result2['unchanged'])==['android:4','ios:4']


def test_update_once_rejects_bad_digest_and_invalid_entries(tmp_path, monkeypatch):
    manifest={'models':{'ios':{
        '4':{'url':'https://models.invalid/bad.mlmodel','sha256':'0'*64},
        '3':{'url':'https://models.invalid/three.mlmodel','sha256':'1'*64},
    }}}
    monkeypatch.setattr(mu,'ROOT',tmp_path)
    monkeypatch.setattr(mu,'COREML_DIR',tmp_path/'coreml')
    monkeypatch.setattr(mu,'ONNX_DIR',tmp_path/'onnx')
    monkeypatch.setattr(mu,'SERVER_DIR',tmp_path/'server')
    monkeypatch.setattr(mu,'BLACKLIST_FILE',tmp_path/'blacklist.json')
    monkeypatch.setattr(mu,'CATALOG_FILE',tmp_path/'catalog.json')
    monkeypatch.setattr(mu,'ENABLED',True)
    monkeypatch.setattr(mu,'_read_url',lambda u: json.dumps(manifest).encode() if u==mu.MANIFEST_URL else b'wrong')
    result=mu.update_once()
    assert len(result['errors'])==2
    assert not (tmp_path/'coreml/demucs-4.mlmodel').exists()


def test_update_once_manifest_failure_and_disabled(monkeypatch):
    monkeypatch.setattr(mu,'ENABLED',False)
    assert mu.update_once()=={'updated':[],'unchanged':[],'errors':[]}
    monkeypatch.setattr(mu,'ENABLED',True)
    monkeypatch.setattr(mu,'_read_url',lambda u: (_ for _ in ()).throw(RuntimeError('offline')))
    result=mu.update_once()
    assert result['errors'] and 'offline' in result['errors'][0]
