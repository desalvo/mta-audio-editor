"""Exercise the actual adapter path with synthetic bytes and dependency doubles.

No real ONNX inference or checkpoint rights certification is claimed.
"""
import hashlib
import sys
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from app import ai_studio_adapter as adapter


@pytest.fixture
def checkpoint(tmp_path,monkeypatch):
    path=tmp_path/'model.onnx';path.write_bytes(b'synthetic ONNX fixture')
    monkeypatch.setattr(adapter,'model_path',lambda:path)
    monkeypatch.setattr(adapter,'MODEL_SHA256',hashlib.sha256(path.read_bytes()).hexdigest())
    return path


def test_transcribe_passes_exact_verified_bytes_to_runtime_and_keeps_cpu_limits(checkpoint,monkeypatch):
    original=checkpoint.read_bytes();seen=[]
    class Model:
        MODEL_TYPES=SimpleNamespace(ONNX='onnx')
    def session(data,**kwargs):
        # Replacing the path at the runtime boundary cannot replace loaded bytes.
        checkpoint.write_bytes(b'replacement after verification')
        assert type(data) is bytes and data==original
        assert kwargs['providers']==['CPUExecutionProvider']
        assert 1<=kwargs['sess_options'].intra_op_num_threads<=4
        assert kwargs['sess_options'].inter_op_num_threads==1
        seen.append(data)
        return object()
    def predict(source,model_or_model_path,**kwargs):
        assert model_or_model_path.model_type=='onnx'
        return None,None,[(0.,.5,60,.8,None)]
    monkeypatch.setitem(sys.modules,'soundfile',SimpleNamespace(info=lambda _:SimpleNamespace(channels=1,duration=1.,samplerate=44100)))
    monkeypatch.setitem(sys.modules,'onnxruntime',SimpleNamespace(SessionOptions=SimpleNamespace,InferenceSession=session,disable_telemetry_events=lambda:None))
    inference=SimpleNamespace(Model=Model,predict=predict,get_audio_input=lambda *a:None)
    monkeypatch.setitem(sys.modules,'basic_pitch',SimpleNamespace(inference=inference))
    monkeypatch.setitem(sys.modules,'basic_pitch.inference',inference)
    result=adapter.transcribe('synthetic.wav',{})
    assert seen==[original]
    assert len(result.parts)==1 and result.parts[0].notes[0].pitch==60


@pytest.mark.parametrize('change',['replace','same-size','empty','symlink','hardlink','directory','oversized'])
def test_changed_or_unsafe_model_never_reaches_runtime(checkpoint,monkeypatch,change):
    import os
    if change=='replace':checkpoint.write_bytes(b'other checkpoint')
    elif change=='same-size':checkpoint.write_bytes(b'X'*checkpoint.stat().st_size)
    elif change=='empty':checkpoint.write_bytes(b'')
    elif change=='symlink':
        other=checkpoint.with_suffix('.other');checkpoint.rename(other);checkpoint.symlink_to(other)
    elif change=='hardlink':os.link(checkpoint,checkpoint.with_suffix('.alias'))
    elif change=='directory':checkpoint.unlink();checkpoint.mkdir()
    else:
        with checkpoint.open('wb') as stream:stream.truncate(64*1024*1024+1)
    runtime=Mock()
    monkeypatch.setitem(sys.modules,'onnxruntime',SimpleNamespace(InferenceSession=runtime))
    with pytest.raises((RuntimeError,ValueError,OSError)):adapter.model_bytes()
    runtime.assert_not_called()


@pytest.mark.parametrize('component',['acoustic','vocoder'])
def test_diffsinger_loader_passes_verified_bytes_and_refuses_replacement(checkpoint,monkeypatch,component):
    from model_rights_fixtures import authorize_singing_fixture
    authorize_singing_fixture(monkeypatch,checkpoint.parent)
    from app import diffsinger_onnx
    original=checkpoint.read_bytes();calls=[]
    def load(data,**kwargs):
        assert type(data) is bytes and data==original
        checkpoint.write_bytes(b'replaced '+component.encode())
        calls.append(data)
        return 'loaded'
    monkeypatch.setitem(sys.modules,'onnxruntime',SimpleNamespace(SessionOptions=SimpleNamespace,
        InferenceSession=load,disable_telemetry_events=lambda:None))
    assert diffsinger_onnx.session(checkpoint,adapter.MODEL_SHA256)=='loaded'
    with pytest.raises(ValueError,match='integrity'):diffsinger_onnx.session(checkpoint,adapter.MODEL_SHA256)
    assert calls==[original]
