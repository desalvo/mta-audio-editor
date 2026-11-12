"""Execute the installed probe with synthetic backends, never claim GPU evidence."""
import runpy
import sys
from types import ModuleType, SimpleNamespace

import numpy as np
import pytest

from app import bass_roformer_install, mega53_install


@pytest.fixture(params=['bass', 'mega53'])
def probe(monkeypatch, tmp_path, request):
    events = []
    torch = ModuleType('torch')
    torch.version = SimpleNamespace(hip=None, cuda=None)
    torch.cuda = SimpleNamespace(is_available=lambda: True,
                                 synchronize=lambda: events.append('synchronize'))
    def ones(shape, *, device):
        events.append(('kernel', device))
        return np.ones(shape, dtype=np.float32)
    def load(path, *, map_location, weights_only):
        assert map_location == 'cpu' and weights_only is True
        events.append('checkpoint')
        return {'state_dict': {'weights': 'synthetic'}}
    def load_state_dict(state, *, strict):
        assert state == {'weights': 'synthetic'} and strict is True
        events.append('strict-load')
    torch.ones, torch.isfinite = ones, np.isfinite
    torch.allclose, torch.full_like, torch.load = np.allclose, np.full_like, load
    model = SimpleNamespace(load_state_dict=load_state_dict,
                            to=lambda device: events.append(('model', device)))
    settings = ModuleType('utils.settings')
    def get_model(kind, path):
        assert kind == 'bs_roformer'
        instruments = ['drums', 'bass', 'other', 'vocals'] if request.param == 'bass' else list(range(53))
        return model, SimpleNamespace(training=SimpleNamespace(instruments=instruments))
    settings.get_model_from_config = get_model
    monkeypatch.setitem(sys.modules, 'torch', torch)
    monkeypatch.setitem(sys.modules, 'utils', ModuleType('utils'))
    monkeypatch.setitem(sys.modules, 'utils.settings', settings)
    monkeypatch.setattr(sys, 'path', list(sys.path))
    program = tmp_path / 'device_probe.py'
    program.write_text(bass_roformer_install.TEST if request.param == 'bass' else mega53_install.TEST)
    def run(expected):
        monkeypatch.setattr(sys, 'argv', ['-c', '/synthetic-source', 'model.yaml', 'weights.ckpt', expected])
        runpy.run_path(str(program))
    return run, torch, model, events


@pytest.mark.parametrize('backend', ['cpu', 'cuda', 'rocm'])
def test_probe_exercises_requested_device_and_loads_exact_model(probe, backend):
    run, torch, _, events = probe
    torch.version.hip = '7.2' if backend == 'rocm' else None
    torch.version.cuda = '12.8' if backend == 'cuda' else None
    run(backend)
    device = 'cpu' if backend == 'cpu' else 'cuda:0'
    assert events == ([('kernel', device)] + ([] if backend == 'cpu' else ['synchronize']) +
                      ['checkpoint', 'strict-load', ('model', device)] +
                      ([] if backend == 'cpu' else ['synchronize']))


@pytest.mark.parametrize('backend,expected', [('cpu', 'cuda'), ('cpu', 'rocm'), ('cuda', 'rocm'),
                                             ('rocm', 'cuda'), ('cuda', 'cpu'), ('cpu', 'auto')])
def test_probe_rejects_wrong_backend_before_model_load(probe, backend, expected):
    run, torch, _, events = probe
    torch.version.hip = '7.2' if backend == 'rocm' else None
    torch.version.cuda = '12.8' if backend == 'cuda' else None
    with pytest.raises(RuntimeError, match='backend mismatch'):
        run(expected)
    assert events == []


@pytest.mark.parametrize('backend', ['cuda', 'rocm'])
def test_probe_rejects_gpu_unavailable_in_worker(probe, backend):
    run, torch, _, events = probe
    torch.version.hip = '7.2' if backend == 'rocm' else None
    torch.version.cuda = '12.8' if backend == 'cuda' else None
    torch.cuda.is_available = lambda: False
    with pytest.raises(RuntimeError, match='accelerator is unavailable'):
        run(backend)
    assert events == []


@pytest.mark.parametrize('bad', [float('nan'), 0])
def test_probe_rejects_corrupt_device_computation(probe, bad):
    run, torch, _, events = probe
    torch.ones = lambda shape, **kw: np.full(shape, bad)
    with pytest.raises(RuntimeError, match='computation validation failed'):
        run('cpu')
    assert 'checkpoint' not in events


@pytest.mark.parametrize('failure', ['kernel', 'synchronize', 'model-transfer'])
def test_probe_propagates_device_errors(probe, failure):
    run, torch, model, _ = probe
    torch.version.hip = '7.2'
    def fail(*args, **kwargs):
        raise RuntimeError('device error')
    if failure == 'kernel': torch.ones = fail
    elif failure == 'synchronize': torch.cuda.synchronize = fail
    else: model.to = fail
    with pytest.raises(RuntimeError, match='device error'):
        run('rocm')
