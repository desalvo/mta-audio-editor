"""Deployment-owned upstream import contracts, independent of runtime receipts.

These pin source already reviewed with the shipped installers. They do not
attest another Python/venv, native dependencies or checkpoint permissions.
The optional adapters own one process; no other request may share its imports.
"""
from contextlib import contextmanager
import importlib.abc
import importlib.util
import json
import os
from pathlib import Path, PurePosixPath
import sys

from .ai_model_bytes import verified_model_bytes

CONTRACT_FILE = Path(__file__).with_name('studio_assets') / 'transcription_source_contracts.json'
CONTRACT_SHA256 = '2610e877a8f9e963050f1601b5a832e23f0ae83a7e04edfa87f42aa4cff06492'


def read_json(path, max_bytes=128 * 1024, *, expected_sha256=None):
    path = Path(path)
    if path.is_symlink() or not path.is_file() or path.stat().st_size > max_bytes:
        raise ValueError('Unsafe transcription source/receipt JSON')
    def unique(pairs):
        value = {}
        for key, item in pairs:
            if key in value:
                raise ValueError('Duplicate transcription source/receipt field')
            value[key] = item
        return value
    data = (verified_model_bytes(path, expected_sha256, max_bytes=max_bytes)
            if expected_sha256 else path.read_bytes())
    if len(data) > max_bytes:
        raise ValueError('Oversized transcription source/receipt JSON')
    value = json.loads(data, object_pairs_hook=unique)
    if not isinstance(value, dict):
        raise ValueError('Invalid transcription source/receipt JSON')
    return value


def profile(family):
    value = read_json(CONTRACT_FILE, expected_sha256=CONTRACT_SHA256)
    if value.get('schema') != 'mta-transcription-sources-1':
        raise ValueError('Unsupported transcription source contract')
    return value['profiles'][family]


def verify_sources(root, files, family, *, model=None):
    """The runtime cannot rewrite the expected hashes or omit import files."""
    contract = profile(family)
    root = Path(root)
    if not root.is_absolute() or root != root.resolve(strict=True) or not root.is_dir():
        raise ValueError('Unsafe transcription runtime root')
    expected = contract['files']
    if not isinstance(files, dict) or any(files.get(name) != digest for name, digest in expected.items()):
        raise ValueError('Transcription source inventory differs from the installed loader contract')
    if model is not None:
        checkpoints = contract['checkpoints'].get(model)
        if checkpoints is None:
            raise ValueError('Transcription checkpoint variant has no independent tensor identity contract')
        if {n:h for n,h in files.items() if n.endswith('.safetensors')} != checkpoints:
            raise ValueError('Transcription checkpoint integrity differs from the installed loader contract')
    for name, digest in expected.items():
        relative = PurePosixPath(name)
        if relative.is_absolute() or any(p in ('', '.', '..') for p in name.split('/')):
            raise ValueError('Unsafe transcription contract member')
        path = root / name
        if path.resolve(strict=True) != path:
            raise ValueError('Aliased transcription source path')
        verified_model_bytes(path, digest, max_bytes=8 * 1024 * 1024)
    for directory in contract['import_roots']:
        base = root if directory == '.' else root / directory
        # The YourMT3 runtime is also a venv. Its distribution directories are
        # not upstream import roots; those dependencies remain a separate gate.
        exclusions = {'bin', 'Scripts', 'lib', 'lib64', 'include', 'share', 'amt'} if directory == '.' else set()
        def inaccessible(error):
            raise error
        for current, directories, names in os.walk(base, followlinks=False, onerror=inaccessible):
            parent = Path(current)
            directories[:] = [d for d in directories if d != '__pycache__' and not (parent == base and d in exclusions)]
            if any((parent / d).is_symlink() for d in directories):
                raise ValueError('Linked upstream import directory')
            for name in names:
                path = parent / name
                if path.is_symlink():
                    raise ValueError('Linked upstream import member')
                if path.suffix in {'.py', '.pyc', '.pyo', '.pyd', '.so'} or '.so.' in path.name:
                    relative = path.relative_to(root).as_posix()
                    if relative not in expected:
                        raise ValueError('Uninventoried upstream import member: ' + relative)
    return contract


def checkpoint_bytes(root, files, family, model):
    """Supply the exact independently pinned bytes to a safetensors loader."""
    contract = profile(family)
    selected = contract['checkpoints'].get(model)
    if not selected or len(selected) != 1:
        raise ValueError('One independently pinned transcription checkpoint is required')
    name, digest = next(iter(selected.items()))
    if files.get(name) != digest:
        raise ValueError('Transcription checkpoint identity changed')
    return root / name, verified_model_bytes(root / name, digest, max_bytes=2 * 1024**3)


@contextmanager
def tensor_loader(root, files, family, model):
    """Bind an upstream load_file call to immutable bytes, never reopen paths."""
    import safetensors.torch as tensors
    original = tensors.load_file
    def load(filename, device='cpu'):
        from .model_license_policy import evaluate_model
        evaluate_model('yourmt3' if family == 'yourmt3' else 'mr-mt3-assets')
        expected, data = checkpoint_bytes(root, files, family, model)
        if Path(filename).absolute() != expected:
            raise ValueError('Upstream loader requested an unapproved transcription checkpoint')
        state = tensors.load(data)
        # safetensors.load owns immutable in-memory bytes on CPU. Explicit
        # placement retains the supported GPU path without a second file read.
        if str(device) != 'cpu':
            state = {name:value.to(device) for name,value in state.items()}
        evaluate_model('yourmt3' if family == 'yourmt3' else 'mr-mt3-assets')
        return state
    tensors.load_file = load
    try:
        yield
    finally:
        tensors.load_file = original


class _SourceLoader(importlib.abc.SourceLoader):
    def __init__(self, path, digest, model):
        self.path, self.digest, self.model = path, digest, model

    def get_filename(self, fullname):
        return str(self.path)

    def get_data(self, path):
        if path != str(self.path):
            raise ImportError('Only the pinned transcription source is readable by this loader')
        return verified_model_bytes(self.path, self.digest, max_bytes=8 * 1024 * 1024)

    def get_code(self, fullname):
        # SourceLoader owns module initialization/execution. Its ordinary
        # bytecode-cache resolution is deliberately replaced with pinned source.
        return self.source_to_code(self.get_data(str(self.path)), str(self.path))

    def exec_module(self, module):
        from .model_license_policy import evaluate_model
        evaluate_model(self.model)
        # Compile these exact checked bytes. Never consult .pyc caches, even
        # when their mtime and size match the original approved source.
        super().exec_module(module)
        evaluate_model(self.model)


class _Finder(importlib.abc.MetaPathFinder):
    def __init__(self, root, contract, model):
        self.modules, self.packages, self.model = {}, {}, model
        for directory in contract['import_roots']:
            base = root if directory == '.' else root / directory
            for name, digest in contract['files'].items():
                path = root / name
                if path.suffix != '.py' or not path.is_relative_to(base):
                    continue
                rel = path.relative_to(base)
                if directory == '.' and len(rel.parts) != 1:
                    continue
                parts = list(rel.with_suffix('').parts)
                package = parts[-1] == '__init__'
                if package: parts.pop()
                fullname = '.'.join(parts)
                self.modules[fullname] = (path, digest, package)
                for i in range(1, len(parts) + int(package)):
                    self.packages['.'.join(parts[:i])] = base.joinpath(*parts[:i])
        self.prefixes = {n.split('.')[0] for n in self.modules | self.packages}

    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] not in self.prefixes:
            return None
        if fullname in self.modules:
            path, digest, package = self.modules[fullname]
            return importlib.util.spec_from_file_location(fullname, path,
                loader=_SourceLoader(path, digest, self.model),
                submodule_search_locations=[str(path.parent)] if package else None)
        if fullname in self.packages:
            spec = importlib.machinery.ModuleSpec(fullname, loader=None, is_package=True)
            spec.submodule_search_locations = [str(self.packages[fullname])]
            return spec
        raise ImportError('Module is outside the approved transcription source contract: ' + fullname)


@contextmanager
def imports(root, files, family, model):
    root = Path(root)
    finder = _Finder(root, verify_sources(root, files, family), model)
    # Python checks sys.modules before finders. Never inherit a module loaded
    # by an unrelated source, even one claiming the same __file__ pathname.
    if any(name.split('.')[0] in finder.prefixes for name in sys.modules):
        raise ValueError('Upstream transcription namespace is already loaded; use an isolated worker')
    sys.meta_path.insert(0, finder)
    try:
        yield
    finally:
        sys.meta_path.remove(finder)
        # Do not leave model/helper modules available for a later request.
        for name in list(sys.modules):
            if name.split('.')[0] in finder.prefixes:
                del sys.modules[name]
