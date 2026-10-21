"""Backend detection is independently testable without a GPU or model files."""
from types import SimpleNamespace
import pytest
from app.yourmt3_adapter import select_inference_device

def fake(*, available=True, hip=None, cuda=None):
    return SimpleNamespace(cuda=SimpleNamespace(is_available=lambda: available), version=SimpleNamespace(hip=hip,cuda=cuda))

def test_cpu_default_and_bad_choice():
    assert select_inference_device(fake(available=False),'cpu')=='cpu'
    with pytest.raises(ValueError):select_inference_device(fake(),'bogus')

@pytest.mark.parametrize('backend', ['cuda','rocm','gpu'])
def test_unavailable_backend_fails_closed(backend):
    with pytest.raises(RuntimeError,match='no usable accelerator'):
        select_inference_device(fake(available=False),backend)

def test_rocm_detection():
    amd=fake(hip='7.2.53211')
    assert select_inference_device(amd,'rocm')=='cuda'
    assert select_inference_device(amd,'gpu')=='cuda'
    with pytest.raises(RuntimeError,match='NVIDIA'):select_inference_device(amd,'cuda')

def test_nvidia_detection():
    nvidia=fake(cuda='12.8')
    assert select_inference_device(nvidia,'cuda')=='cuda'
    assert select_inference_device(nvidia,'gpu')=='cuda'
    with pytest.raises(RuntimeError,match='ROCm'):select_inference_device(nvidia,'rocm')

def test_unknown_backend_rejected():
    with pytest.raises(RuntimeError,match='identity'):select_inference_device(fake(),'gpu')
