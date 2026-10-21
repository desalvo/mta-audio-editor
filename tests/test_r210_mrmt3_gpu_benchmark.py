"""GPU benchmark guardrails: tests do not require a GPU or fake inference."""
from pathlib import Path
import pytest
from scripts.run_mrmt3_gpu_benchmark import plan_cycles, main
from scripts.run_mrmt3_resumable import resolve_device, gpu_memory_ok, gpu_backend


class FakeCuda:
    def __init__(self, available, free=0):
        self.available = available
        self.free = free
    def is_available(self):
        return self.available
    def mem_get_info(self):
        return self.free, self.free


class FakeTorch:
    def __init__(self, available, free=0, backend='cuda'):
        self.cuda = FakeCuda(available, free)
        self.version = type('Version', (), {'hip': '7.0' if backend=='rocm' else None,
                                             'cuda': '12.8' if backend=='cuda' else None})()


def test_explicit_gpu_does_not_fall_back():
    with pytest.raises(RuntimeError, match='unavailable'):
        resolve_device('cuda', FakeTorch(False))
    assert resolve_device('auto', FakeTorch(False)) == 'cpu'
    assert resolve_device('cuda', FakeTorch(True)) == 'cuda'
    assert resolve_device('cpu', FakeTorch(True)) == 'cpu'
    assert resolve_device('gpu', FakeTorch(True, backend='rocm')) == 'cuda'
    assert resolve_device('rocm', FakeTorch(True, backend='rocm')) == 'cuda'
    assert resolve_device('auto', FakeTorch(True, backend='rocm')) == 'cuda'
    assert gpu_backend(FakeTorch(True, backend='rocm')) == 'rocm'
    with pytest.raises(RuntimeError, match='rocm requested'):
        resolve_device('rocm', FakeTorch(True, backend='cuda'))
    with pytest.raises(RuntimeError, match='cuda requested'):
        resolve_device('cuda', FakeTorch(True, backend='rocm'))


def test_gpu_respects_free_memory():
    assert not gpu_memory_ok(FakeTorch(False), 3)
    assert not gpu_memory_ok(FakeTorch(True, 1024), 3)
    assert gpu_memory_ok(FakeTorch(True, 4*1024**3), 3)


def test_plan_rejects_incorrect_inputs(tmp_path):
    wav = tmp_path/'mix.wav'; wav.touch()
    model=tmp_path/'model.safetensors'; model.touch()
    assert plan_cycles(wav,model,tmp_path/'out',4,1000,3)
    with pytest.raises(ValueError,match='cycle'):
        plan_cycles(wav,model,tmp_path/'out',0,1000,3)
    with pytest.raises(ValueError,match='Safetensors'):
        plan_cycles(wav,Path('missing'),tmp_path/'out',4,1000,3)
    (tmp_path/'shortcut').symlink_to(tmp_path)
    with pytest.raises(ValueError,match='symlink'):
        plan_cycles(wav,model,tmp_path/'shortcut',4,1000,3)


def test_cli_requires_production_opt_in(tmp_path):
    wav = tmp_path/'mix.wav'; wav.touch()
    model=tmp_path/'model.safetensors'; model.touch()
    with pytest.raises(SystemExit):
        main(['--audio',str(wav),'--model',str(model),'--output',str(tmp_path/'output')])
    assert not (tmp_path/'output').exists()
