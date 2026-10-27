"""Optional real ORT loader proof using an in-memory synthetic ONNX graph.

Install onnx==1.17.0 onnxruntime==1.20.1 in an isolated test environment.
This is not Basic Pitch inference, accuracy or checkpoint rights acceptance.
"""
import hashlib

import pytest


def test_real_onnx_runtime_loads_verified_bytes_despite_path_replacement(tmp_path,monkeypatch):
    onnx=pytest.importorskip('onnx')
    ort=pytest.importorskip('onnxruntime')
    import numpy as np
    from app import ai_studio_adapter as adapter
    graph=onnx.helper.make_graph([onnx.helper.make_node('Identity',['x'],['y'])],'synthetic-identity',
        [onnx.helper.make_tensor_value_info('x',onnx.TensorProto.FLOAT,[1])],
        [onnx.helper.make_tensor_value_info('y',onnx.TensorProto.FLOAT,[1])])
    model=onnx.helper.make_model(graph,opset_imports=[onnx.helper.make_opsetid('',13)],ir_version=9)
    raw=model.SerializeToString();path=tmp_path/'synthetic.onnx';path.write_bytes(raw)
    monkeypatch.setattr(adapter,'model_path',lambda:path)
    monkeypatch.setattr(adapter,'MODEL_SHA256',hashlib.sha256(raw).hexdigest())
    verified=adapter.model_bytes()
    path.write_bytes(b'invalid replacement that ORT cannot load')
    options=ort.SessionOptions();options.intra_op_num_threads=1;options.inter_op_num_threads=1
    session=ort.InferenceSession(verified,sess_options=options,providers=['CPUExecutionProvider'])
    assert session.run(None,{'x':np.array([42.],dtype=np.float32)})[0].tolist()==[42.]
    with pytest.raises(ValueError,match='integrity'):adapter.model_bytes()
