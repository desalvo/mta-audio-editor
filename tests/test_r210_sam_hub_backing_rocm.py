"""ROCm backing-vocal coverage retained after retiring the unrelated SAM backend."""
from contextlib import nullcontext
import sys
from types import SimpleNamespace
import numpy as np
import pytest
from app import backing_vocals_runtime as backing


class Tensor:
    def __init__(self,data):self.data=np.asarray(data);self.ndim=self.data.ndim;self.shape=self.data.shape;self.device=None
    def to(self,device):self.device=device;return self
    def cpu(self):return self
    def detach(self):return self
    def numpy(self):return self.data
    def __getitem__(self,item):return Tensor(self.data[item])


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


