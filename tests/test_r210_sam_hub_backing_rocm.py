"""SAM Hub 0.x/1.x contracts, worker output and ROCm backing-vocal dispatch."""
from contextlib import nullcontext
import importlib.util
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import numpy as np
import pytest
import soundfile as sf

from app import backing_vocals_runtime as backing, sam_audio_compat as compat, sam_audio_worker as worker
from app.ai_cgroup_metering import _worker_failure, safe_failure_metadata


def hub_base(version, modern=False):
    calls = []
    def snapshot(*, repo_id, token, revision, cache_dir, local_files_only, force_download):
        calls.append((repo_id, token, revision, cache_dir, local_files_only, force_download))
        return 'checkpoint'
    if version == 0:
        original = snapshot
        def snapshot(*, proxies, resume_download, **kwargs):
            assert proxies is None and resume_download is None
            return original(**kwargs)
    base = SimpleNamespace(snapshot_download=snapshot)
    class Base:
        @classmethod
        def from_pretrained(cls, model_id):
            kwargs = dict(model_id=model_id, token='credential', revision='fixed-revision',
                          cache_dir='/cache', local_files_only=True, force_download=False)
            if version == 0:kwargs.update(proxies=None, resume_download=None)
            return cls._from_pretrained(**kwargs)
        @classmethod
        def _from_pretrained(cls, *, model_id, proxies, resume_download, **kwargs):
            return base.snapshot_download(repo_id=model_id, proxies=proxies,
                                          resume_download=resume_download, **kwargs)
    if modern:
        @classmethod
        def hook(cls, *, model_id, proxies=None, resume_download=None, **kwargs):
            return base.snapshot_download(repo_id=model_id, **kwargs)
        Base._from_pretrained = hook
    base.BaseModel = Base
    return base, calls


@pytest.mark.parametrize('version,modern', [(0,False),(1,False),(1,True)])
def test_sam_load_contract_keeps_auth_revision_cache_and_restores_bindings(version, modern):
    base,calls=hub_base(version,modern)
    descriptor=base.BaseModel.__dict__['_from_pretrained'];snapshot=base.snapshot_download
    if version==1 and not modern:
        with pytest.raises(TypeError,match='proxies'):
            base.BaseModel.from_pretrained('facebook/sam-audio-small')
    with compat.sam_hub_compat(base):
        class Child(base.BaseModel):pass
        assert Child.from_pretrained('facebook/sam-audio-small')=='checkpoint'
    assert calls==[('facebook/sam-audio-small','credential','fixed-revision','/cache',True,False)]
    assert base.BaseModel.__dict__['_from_pretrained'] is descriptor and base.snapshot_download is snapshot


def test_sam_bridge_does_not_retry_or_swallow_model_failures():
    base,_=hub_base(1);original=base.BaseModel.__dict__['_from_pretrained']
    def failed(**kwargs):raise PermissionError('checkpoint access denied')
    base.snapshot_download=failed
    with pytest.raises(PermissionError):
        with compat.sam_hub_compat(base):base.BaseModel.from_pretrained('facebook/sam-audio-small')
    assert base.BaseModel.__dict__['_from_pretrained'] is original and base.snapshot_download is failed


class Tensor:
    def __init__(self,data):self.data=np.asarray(data);self.ndim=self.data.ndim;self.shape=self.data.shape;self.device=None
    def to(self,device):self.device=device;return self
    def cpu(self):return self
    def detach(self):return self
    def numpy(self):return self.data
    def __getitem__(self,item):return Tensor(self.data[item])


@pytest.mark.parametrize('gpu', [False,True])
def test_actual_sam_worker_reaches_inference_and_writes_wav(tmp_path,monkeypatch,gpu):
    base,_=hub_base(1);observed={}
    class Model(base.BaseModel):
        @classmethod
        def from_pretrained(cls,model_id):super().from_pretrained(model_id);return cls()
        def eval(self):return self
        def to(self,device):observed['device']=device;return self
        def separate(self,inputs,**kwargs):
            assert kwargs==dict(predict_spans=False,reranking_candidates=1)
            return SimpleNamespace(target=Tensor(np.zeros((1,1,4800),np.float32)))
    class Processor:
        audio_sampling_rate=48000
        @classmethod
        def from_pretrained(cls,model_id):return cls()
        def __call__(self,**kwargs):observed['prompts']=kwargs;return Tensor([1])
    monkeypatch.setitem(sys.modules,'sam_audio',SimpleNamespace(SAMAudio=Model,SAMAudioProcessor=Processor))
    monkeypatch.setitem(sys.modules,'sam_audio.model.base',base)
    monkeypatch.setitem(sys.modules,'torch',SimpleNamespace(cuda=SimpleNamespace(is_available=lambda:gpu),inference_mode=nullcontext))
    def save(path,audio,rate):sf.write(path,audio.numpy().T,rate)
    monkeypatch.setitem(sys.modules,'torchaudio',SimpleNamespace(save=save))
    output=tmp_path/'out.wav'
    monkeypatch.setattr(sys,'argv',['sam','--source','in.wav','--output',str(output),'--model','facebook/sam-audio-small','--prompt','singing voice','--anchors-json','[["+",0,1]]'])
    worker.main();audio,rate=sf.read(output)
    assert len(audio)==4800 and rate==48000
    assert observed['device']==('cuda' if gpu else 'cpu')
    assert observed['prompts']['anchors']==[[['+',0,1]]]


def test_sam_import_failure_emits_only_fixed_stage_marker(tmp_path,monkeypatch,capsys):
    monkeypatch.setattr(sys,'argv',['sam','--source','in','--output',str(tmp_path/'out'),'--model','facebook/sam-audio-small','--prompt','PRIVATE'])
    monkeypatch.setitem(sys.modules,'torch',None)
    with pytest.raises(ModuleNotFoundError):worker.main()
    assert capsys.readouterr().err.strip()=='MTA_SAM_FAILURE:imports'
    assert not (tmp_path/'out').exists()


def test_safe_sam_failure_and_backing_categories():
    for message,category in [
        ("TypeError: BaseModel._from_pretrained() missing 2 required keyword-only arguments: 'proxies' and 'resume_download'",'sam_hub_incompatible'),
        ('MTA_SAM_FAILURE:model_load','sam_model_load_failed'),
        ('MTA_SAM_FAILURE:inference','sam_inference_failed'),
        ('MTA_BACKING_FAILURE:rocm_conversion_failed','backing_rocm_conversion_failed')]:
        result=_worker_failure(message+'\nPRIVATE credential\nsubprocess.CalledProcessError: SECRET',1)
        assert result['category']==category and result['metering_valid'] is False
        assert safe_failure_metadata(result)['category']==category
        assert 'PRIVATE' not in json.dumps(result) and 'SECRET' not in json.dumps(result)


def separator():
    inst=SimpleNamespace(model_path='/cache/selected.onnx',model_run=lambda x:'cpu',torch_device='cpu')
    return SimpleNamespace(model_instance=inst,load_model=lambda **kwargs:None)


@pytest.fixture
def backing_rights(tmp_path,monkeypatch):
    from model_rights_fixtures import authorize_fixture
    for model in ('uvr-kara-2','audio-separator-weights'):
        authorize_fixture(monkeypatch,tmp_path,model)


def test_backing_same_onnx_checkpoint_runs_on_rocm_and_returns_expected_numpy(monkeypatch,backing_rights):
    observed={};s=separator()
    class Model:
        def to(self,device):observed['device']=device;return self
        def eval(self):return self
        def __call__(self,x):observed['input_device']=x.device;return x
    def convert(path):observed['path']=path;return Model()
    monkeypatch.setitem(sys.modules,'torch',SimpleNamespace(version=SimpleNamespace(hip='7.2'),cuda=SimpleNamespace(is_available=lambda:True),device=lambda x:x,inference_mode=nullcontext))
    monkeypatch.setitem(sys.modules,'onnx2torch',SimpleNamespace(convert=convert))
    backing.load_backing_model(s,'UVR_MDXNET_KARA_2.onnx')
    np.testing.assert_array_equal(s.model_instance.model_run(Tensor([1,2])),[1,2])
    assert observed==dict(device='cuda',input_device='cuda',path='/cache/selected.onnx')
    assert s.model_instance.uses_pytorch_inference and s.model_instance.mta_execution_backend=='pytorch-rocm'


@pytest.mark.parametrize('hip,gpu,filename',[(None,True,'UVR_MDXNET_KARA_2.onnx'),('7.2',False,'UVR_MDXNET_KARA_2.onnx'),('7.2',True,'mel_band_roformer_karaoke_gabox_v2.ckpt')])
def test_other_backing_devices_and_models_keep_existing_route(monkeypatch,hip,gpu,filename,backing_rights):
    s=separator();original=s.model_instance.model_run
    monkeypatch.setitem(sys.modules,'torch',SimpleNamespace(version=SimpleNamespace(hip=hip),cuda=SimpleNamespace(is_available=lambda:gpu)))
    backing.load_backing_model(s,filename)
    assert s.model_instance.model_run is original


def test_backing_conversion_failure_does_not_fall_back_to_cpu(monkeypatch,backing_rights):
    s=separator()
    monkeypatch.setitem(sys.modules,'torch',SimpleNamespace(version=SimpleNamespace(hip='7.2'),cuda=SimpleNamespace(is_available=lambda:True),device=lambda x:x))
    def failed(path):raise ValueError('unsupported operator')
    monkeypatch.setitem(sys.modules,'onnx2torch',SimpleNamespace(convert=failed))
    with pytest.raises(RuntimeError,match='rocm_conversion_failed'):backing.load_backing_model(s,'UVR_MDXNET_KARA_2.onnx')


def test_installer_exercises_model_loader_without_huggingface_download(monkeypatch):
    path=Path(__file__).parents[1]/'scripts/install_ai_engines.py'
    spec=importlib.util.spec_from_file_location('sam_installer',path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    calls=[];monkeypatch.setattr(m,'run',lambda args,**kwargs:calls.append(args))
    m.verify('/python','sam','rocm')
    assert any('verify_sam_hub_compatibility' in str(args) for args in calls)
    assert any('AudioDecoder' in str(args) for args in calls)


def test_native_bundle_contains_sam_bridge_source():
    root=Path(__file__).parents[1]
    assert '(str(project / "app" / "sam_audio_compat.py"), "app")' in (root/'native/mta_audio_editor_native.spec').read_text()
