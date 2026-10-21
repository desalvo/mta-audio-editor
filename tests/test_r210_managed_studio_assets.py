"""Data-only test bundles; not real models and not inference certification."""
import hashlib,io,json,zipfile
import pytest
from app import studio_asset_registry as assets


def bundle(asset_id='test-vocoder',kind='vocoder',bindings=None,files=None,policy='test-checkpoint'):
    files=files or {'model.pt':b'fake test bytes','LICENSE.txt':b'Test notice'}
    value={'schema':'mta-studio-bundle-1','id':asset_id,'name':'Test fixture','kind':kind,'languages':['en'],
        'files':{name:{'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()} for name,data in files.items()},
        'bindings':bindings or {'checkpoint':'model.pt'},
        'components':{'checkpoint':policy},'component_files':{'checkpoint':['model.pt','LICENSE.txt']},
        'licenses':[{'policy_model':policy,'notice':'LICENSE.txt','evidence_url':'https://example.com/permission'}]}
    output=io.BytesIO()
    with zipfile.ZipFile(output,'w') as archive:
        archive.writestr('manifest.json',json.dumps(value))
        for name,data in files.items():archive.writestr(name,data)
    return output.getvalue(),value


@pytest.fixture
def managed(tmp_path,monkeypatch):
    from app import studio_catalog
    monkeypatch.setattr(studio_catalog,'root',lambda:tmp_path)
    return tmp_path


def test_install_is_hash_verified_disabled_and_preserves_notices(managed):
    data,value=bundle();result=assets.install(data)
    assert result['enabled'] is False and not result['real_inference_validated']
    info=assets.manifest(value['id'],verify=True)
    assert assets.binding(info,'checkpoint').read_bytes()==b'fake test bytes'
    assert not assets.catalog()[0]['admitted']
    with pytest.raises(ValueError,match='already installed'):assets.install(data)


def test_activation_requires_component_rights(managed,monkeypatch):
    from app import model_license_policy as policy
    assets.install(bundle()[0])
    with pytest.raises(policy.LicenseDenied):assets.configure('test-vocoder',True)
    monkeypatch.setattr(policy,'evaluate_model',lambda model:policy.Decision(model,'free_only','https://example.com','a'*64))
    assert assets.configure('test-vocoder',True)['enabled']
    assert not assets.policies('test-vocoder')[0].billable
    path=assets.binding(assets.manifest('test-vocoder'),'checkpoint');path.write_bytes(b'tampered')
    with pytest.raises(ValueError,match='checksum'):assets.manifest('test-vocoder',verify=True)


@pytest.mark.parametrize('path',['../outside','/absolute','a\\b','x/./file','x/../file','C:/file'])
def test_traversal_rejected(managed,path):
    with pytest.raises(ValueError):assets.relative(path)


def test_tampered_zip_no_activation(managed):
    data,value=bundle();output=io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(data)) as source,zipfile.ZipFile(output,'w') as target:
        for entry in source.infolist():target.writestr(entry.filename,b'bad' if entry.filename=='model.pt' else source.read(entry))
    with pytest.raises(ValueError):assets.install(output.getvalue())
    assert assets.catalog()==[]


def test_extra_files_and_links_rejected(managed):
    data,value=bundle();output=io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(data)) as source,zipfile.ZipFile(output,'w') as target:
        for entry in source.infolist():target.writestr(entry.filename,source.read(entry))
        link=zipfile.ZipInfo('link');link.external_attr=0o120777<<16;target.writestr(link,'model.pt')
    with pytest.raises(ValueError,match='Links'):assets.install(output.getvalue())


def test_cancelled_install_does_not_publish(managed):
    with pytest.raises(RuntimeError,match='cancelled'):assets.install(bundle()[0],cancelled=lambda:True)
    assert assets.catalog()==[]


@pytest.mark.parametrize('key,value',[('kind',{}),('licenses',[{'policy_model':'test-checkpoint','notice':[],
    'evidence_url':'https://example.com'}]),('components',{'checkpoint':[]}),('component_files',{'checkpoint':[[]]})])
def test_malformed_manifest_is_rejected_as_validation_error(key,value):
    _,manifest=bundle();manifest[key]=value
    with pytest.raises(ValueError):assets.validate_manifest(manifest)


def test_every_runtime_file_requires_component_permission():
    _,manifest=bundle();manifest['files']['unreviewed.pt']={'bytes':1,'sha256':'a'*64}
    with pytest.raises(ValueError,match='Every model/runtime'):assets.validate_manifest(manifest)
