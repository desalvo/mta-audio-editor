"""Scoped bridge for SAM's legacy ModelHubMixin hook and Hub 1.x.

No third-party installation is edited. Only SAM's two removed Hub options are
adapted; checkpoint authentication, revisions and weights_only loading remain
owned by upstream. The context lives in the isolated inference process.
"""
from contextlib import contextmanager
from functools import wraps
import importlib
import inspect
import json
from pathlib import Path
import tempfile


@contextmanager
def sam_hub_compat(base_module=None):
    base = base_module if base_module is not None else importlib.import_module('sam_audio.model.base')
    cls = base.BaseModel
    descriptor = inspect.getattr_static(cls, '_from_pretrained')
    original = descriptor.__func__
    parameters = inspect.signature(original).parameters
    defaults = {name: None for name in ('proxies', 'resume_download')
                if name in parameters and parameters[name].default is inspect.Parameter.empty}
    download = base.snapshot_download
    download_parameters = inspect.signature(download).parameters
    accepts_kwargs = any(p.kind == inspect.Parameter.VAR_KEYWORD for p in download_parameters.values())
    removed = {name for name in ('proxies', 'resume_download')
               if name not in download_parameters and not accepts_kwargs}

    @wraps(original)
    def load(model_cls, *args, **kwargs):
        for key, value in defaults.items():
            kwargs.setdefault(key, value)
        return original(model_cls, *args, **kwargs)

    @wraps(download)
    def snapshot(*args, **kwargs):
        for key in removed:
            kwargs.pop(key, None)
        return download(*args, **kwargs)

    try:
        if defaults:
            cls._from_pretrained = classmethod(load)
        if removed:
            base.snapshot_download = snapshot
        yield
    finally:
        cls._from_pretrained = descriptor
        base.snapshot_download = download


def verify_sam_hub_compatibility():
    """Exercise the actual installed Hub/SAM load contract without checkpoints/network."""
    import torch
    from sam_audio.model.base import BaseModel

    class Probe(BaseModel):
        config_cls = staticmethod(lambda **kwargs: kwargs)

        def __init__(self, config):
            super().__init__()

    with tempfile.TemporaryDirectory() as folder:
        Path(folder, 'config.json').write_text(json.dumps({}))
        torch.save({}, Path(folder, 'checkpoint.pt'))
        with sam_hub_compat():
            Probe.from_pretrained(folder)
