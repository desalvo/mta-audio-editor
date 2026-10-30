"""An installed adapter must not make an arbitrary Python override executable."""
import base64
import json
import os
from pathlib import Path
import sys

import pytest

from app import ai_worker_registry as registry, ai_adapter_identity as identity, auth
from test_r210_execution_entry_acceptance import KINDS, api, audio
from test_r210_queue_identity_stem_metering import env as env  # noqa: F401


@pytest.fixture
def executable(tmp_path):
    marker = tmp_path / 'executed'
    path = tmp_path / 'python'
    path.write_text('#!/bin/sh\ntouch "' + str(marker) + '"\n')
    path.chmod(0o700)
    return path, marker


@pytest.mark.parametrize('kind', KINDS)
@pytest.mark.parametrize('scope', ['kind', 'default'])
def test_interpreter_override_is_refused_before_availability(executable, monkeypatch, kind, scope):
    path, marker = executable
    monkeypatch.setenv('MTA_AI_WORKER_ENABLED', 'true')
    monkeypatch.setenv('MTA_AI_UNIFIED_WORKERS_ENABLED', 'true')
    variable = 'MTA_AI_DEFAULT_PYTHON' if scope == 'default' else 'MTA_AI_WORKER_' + kind.upper().replace('-', '_') + '_PYTHON'
    monkeypatch.setenv(variable, str(path))
    assert registry.resolve_worker(kind) is None
    with pytest.raises(ValueError, match='interpreter/import contract'):
        registry.worker_python(kind)
    assert not marker.exists()


@pytest.mark.parametrize('alias', ['copy', 'symlink', 'hardlink', 'venv', 'relative'])
def test_matching_binary_bytes_do_not_attest_another_import_context(tmp_path, alias):
    target = tmp_path / 'python'
    if alias == 'copy': target.write_bytes(Path(sys.executable).read_bytes())
    elif alias in ('symlink', 'venv'):
        if alias == 'venv':
            (tmp_path / 'pyvenv.cfg').write_text('include-system-site-packages = true\n')
        target.symlink_to(sys.executable)
    elif alias == 'hardlink': os.link(Path(sys.executable).resolve(), target)
    else: target = Path('python')
    with pytest.raises(ValueError, match='interpreter/import contract'):
        identity.require_current_interpreter(str(target))


def test_current_installation_interpreter_is_preserved():
    assert identity.require_current_interpreter(sys.executable) == sys.executable


@pytest.mark.parametrize('transport', ['json', 'upload'])
def test_actual_token_api_cannot_launch_substituted_python_or_create_ledger(env, executable, monkeypatch, transport):
    from app import ai_access
    monkeypatch.setenv('MTA_AI_WORKER_ENABLED', 'true')
    monkeypatch.setenv('MTA_AI_UNIFIED_WORKERS_ENABLED', 'true')
    monkeypatch.setenv('MTA_AI_WORKER_WHISPER_PYTHON', str(executable[0]))
    token = ai_access.issue(env, 'Interpreter rejection')
    headers = {'Authorization': 'Bearer ' + token['token']}
    with api() as client:
        if transport == 'json':
            response = client.post('/api/ai-jobs/execute', json={'kind': 'whisper', 'plan': {}}, headers=headers)
        else:
            headers.update({'Content-Type': 'audio/wav', 'X-MTA-AI-Options': base64.urlsafe_b64encode(json.dumps({}).encode()).decode()})
            response = client.post('/api/ai-jobs/execute-audio/whisper', content=audio(), headers=headers)
    assert response.status_code == 503, response.text
    assert not executable[1].exists()
    with auth.db() as con:
        assert con.execute('SELECT count(*) FROM ai_compute_jobs').fetchone()[0] == 0
