"""Keep media decoding independent from the selected inference accelerator."""
import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).parents[1]


def setup_module_object():
    spec = importlib.util.spec_from_file_location('sam_setup', ROOT / 'scripts/install_ai_engines.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize('device,version', [('rocm', '0.11.1+cpu'), ('cpu', '0.17.0+cpu')])
def test_sam_codec_variant_is_constrained_before_upstream_install(tmp_path, monkeypatch, device, version):
    module = setup_module_object()
    calls = []
    def run(args, **kwargs):
        calls.append(list(map(str, args)))
        if 'ls-remote' in args:
            return SimpleNamespace(stdout='a'*40 + '\tHEAD\n')
        return SimpleNamespace(stdout='torch==2.11.0+rocm7.2\ntorchaudio==2.11.0+rocm7.2\ntorchvision==0.26.0+rocm7.2\n')
    monkeypatch.setattr(module, 'run', run)
    monkeypatch.setattr(module, 'verify', lambda *a: None)
    module.install_group('/python', tmp_path, device, 'sam')
    codec_index = next(i for i,c in enumerate(calls) if 'torchcodec==' + version in c)
    upstream_index = next(i for i,c in enumerate(calls) if any(x.startswith('sam_audio @') for x in c))
    assert codec_index < upstream_index
    assert '--no-deps' in calls[codec_index]
    assert 'https://download.pytorch.org/whl/cpu' in calls[codec_index]
    assert 'torchcodec==' + version in (tmp_path/'torch-constraints.txt').read_text()
    assert '-c' in calls[upstream_index]


def test_sam_decode_failure_blocks_publication(monkeypatch):
    module = setup_module_object()
    def run(args, **kwargs):
        if 'AudioDecoder' in str(args):
            raise RuntimeError('decoder cannot load shared library')
    monkeypatch.setattr(module, 'run', run)
    with pytest.raises(RuntimeError, match='decoder cannot load'):
        module.verify('/python', 'sam', 'rocm')


def test_root_markdown_policy():
    assert all(p.name.upper().startswith('README') for p in ROOT.glob('*.md'))
