"""The server installer and the worker trust checks must agree."""
import json
import os
from pathlib import Path
import shutil
import subprocess

import pytest

from app import ai_adapter_identity as identity, ai_worker_registry as registry


@pytest.fixture
def installed(tmp_path, monkeypatch):
    if os.name != 'posix':
        pytest.skip('managed runtime is supported on POSIX')
    root = tmp_path / 'mta'
    monkeypatch.setattr(identity, 'MANAGED_RUNTIME_ROOT', root)
    monkeypatch.setattr(identity, 'MANAGED_RUNTIME_OWNER', os.getuid())
    result = {}
    for group in ('audio', 'sam'):
        folder = root / 'ai-0123456789abcdef' / group
        (folder / 'bin').mkdir(parents=True)
        python = folder / 'bin' / 'python'
        shutil.copyfile('/usr/bin/python3', python)
        python.chmod(0o755)
        (folder / 'pyvenv.cfg').write_text('home = /usr/bin\ninclude-system-site-packages = false\n')
        (folder / '.mta-ai-ready.json').write_text(json.dumps({
            'group': group, 'fingerprint': '0123456789abcdef', 'device': 'cpu'}))
        result[group] = python
    monkeypatch.setenv('MTA_AI_WORKER_ENABLED', 'true')
    monkeypatch.setenv('MTA_AI_UNIFIED_WORKERS_ENABLED', 'true')
    return result


@pytest.mark.parametrize(('kind', 'group'), [
    ('whisper', 'audio'), ('chords-ml', 'audio'), ('demucs', 'audio'),
    ('drumsep', 'audio'), ('markers', 'audio'), ('backing-vocals', 'audio'),
    ('sam-audio', 'sam'), ('singer-separation', 'sam'),
])
def test_installer_runtime_resolves_real_adapter(installed, monkeypatch, kind, group):
    monkeypatch.setenv('MTA_AI_WORKER_' + kind.upper().replace('-', '_') + '_PYTHON', str(installed[group]))
    assert registry.worker_python(kind) == str(installed[group])
    assert registry.resolve_worker(kind) == Path(identity.__file__).parent / 'ai_unified_adapter.py'


def test_wrong_group_or_tampered_marker_is_rejected(installed, monkeypatch):
    monkeypatch.setenv('MTA_AI_WORKER_WHISPER_PYTHON', str(installed['sam']))
    assert registry.resolve_worker('whisper') is None
    monkeypatch.setenv('MTA_AI_WORKER_WHISPER_PYTHON', str(installed['audio']))
    marker = installed['audio'].parents[1] / '.mta-ai-ready.json'
    marker.write_text('{}')
    assert registry.resolve_worker('whisper') is None


def test_writable_managed_folder_is_rejected(installed, monkeypatch):
    monkeypatch.setenv('MTA_AI_WORKER_WHISPER_PYTHON', str(installed['audio']))
    installed['audio'].parents[1].chmod(0o777)
    assert registry.resolve_worker('whisper') is None


def test_selected_managed_python_starts_in_its_own_venv(installed, monkeypatch):
    monkeypatch.setenv('MTA_AI_WORKER_WHISPER_PYTHON', str(installed['audio']))
    binary = registry.worker_python('whisper')
    result = subprocess.run([binary, '-I', '-c', 'import sys; print(sys.prefix)'],
                            check=True, capture_output=True, text=True)
    assert Path(result.stdout.strip()) == installed['audio'].parents[1]
