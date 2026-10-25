"""Checkpoint contract fixtures; optional real Torch test never certifies inference."""
import importlib.util
import types

import pytest
from app.transkun_runner import load_state


class Tensor:pass


@pytest.mark.parametrize('field',['best_state_dict','state_dict'])
def test_transkun_accepts_only_weights_and_preserves_original_device(field):
    state={'model.weight':Tensor()};calls=[]
    def load(path,**kw):calls.append((path,kw));return {field:state}
    assert load_state(types.SimpleNamespace(load=load,Tensor=Tensor),'pinned.pt','cpu') is state
    assert calls==[('pinned.pt',{'map_location':'cpu','weights_only':True})]


@pytest.mark.parametrize('error',[TypeError('unsupported metadata'),RuntimeError('unsafe globals')])
def test_transkun_never_falls_back_to_unrestricted_unpickling(error):
    calls=[]
    def load(path,**kw):calls.append(kw);raise error
    with pytest.raises(type(error)):load_state(types.SimpleNamespace(load=load,Tensor=Tensor),'pinned.pt','cpu')
    assert calls==[{'map_location':'cpu','weights_only':True}]


@pytest.mark.parametrize('data',[None,{},[],{'state_dict':{}},{'state_dict':{'bad':object()}},{'state_dict':{1:Tensor()}}])
def test_executable_or_malformed_weight_objects_are_not_accepted(data):
    with pytest.raises(ValueError):load_state(types.SimpleNamespace(load=lambda *a,**kw:data,Tensor=Tensor),'pinned.pt','cpu')


@pytest.mark.skipif(importlib.util.find_spec('torch') is None,reason='Optional Torch runtime not installed; no model installation authorized')
def test_actual_torch_weights_only_rejects_pickle_execution(tmp_path):
    import builtins
    import torch
    marker=tmp_path/'must-not-execute'
    class Payload:
        def __reduce__(self):return builtins.eval,("__import__('pathlib').Path("+repr(str(marker))+").write_text('unsafe')",)
    source=tmp_path/'checkpoint.pt';torch.save({'state_dict':{'layer':Payload()}},source)
    with pytest.raises(Exception):load_state(torch,source,'cpu')
    assert not marker.exists()
    torch.save({'best_state_dict':{'layer':torch.tensor([1.0])}},source)
    assert load_state(torch,source,'cpu')['layer'].tolist()==[1.0]
