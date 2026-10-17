"""Diagnostics must preserve application errors in the service journal."""
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]


def test_nested_backend_traceback_keeps_original_restricted_error():
    from app.ai_cgroup_metering import _safe_worker_error
    original = 'RuntimeError: model load failed token=PRIVATE https://private.example/SECRET\n'
    frames = '  File "/private/project/source.py", line 1, in worker\n' * 20
    detail = _safe_worker_error(original + frames + 'subprocess.CalledProcessError: backend exited 1\n')
    assert 'RuntimeError: model load failed' in detail
    assert 'CalledProcessError' in detail
    assert 'PRIVATE' not in detail and 'private.example' not in detail and '/private/project' not in detail


@pytest.mark.parametrize('enabled', [False, True])
def test_uvicorn_root_fallback_survives_diagnostic_capture(tmp_path, enabled):
    # Isolate from pytest's own root handlers: production Uvicorn configures
    # uvicorn.error/access but leaves the application's root without handlers.
    script = '''
import json, logging, logging.config, sys
from pathlib import Path
from uvicorn.config import LOGGING_CONFIG
from app import diagnostic_bundle as diag
from app.ai_cgroup_metering import _safe_worker_error, _worker_failure
logging.config.dictConfig(LOGGING_CONFIG)
assert not logging.getLogger().handlers
diag.BASE = Path(sys.argv[1])
diag.configure(sys.argv[2] == 'True')
diag.install_event_capture()
diag.install_event_capture()
assert len(logging.getLogger().handlers) == 2
raw = 'RuntimeError: model load failed token=PRIVATE https://private.example/SECRET'
logging.getLogger('app.ai_cgroup_metering').error(
    'AI metered worker exited nonzero: %s', _safe_worker_error(raw),
    extra={'mta_worker_failure': _worker_failure(raw, 1)})
logging.getLogger('app.main').warning('ordinary warning visible')
logging.getLogger('app.main').info('info hidden by fallback')
'''
    result = subprocess.run([sys.executable, '-c', script, str(tmp_path), str(enabled)],
                            cwd=ROOT, capture_output=True, text=True, check=True)
    assert result.stderr.count('AI metered worker exited nonzero') == 1
    assert 'RuntimeError: model load failed' in result.stderr
    assert 'ordinary warning visible' in result.stderr
    assert 'info hidden' not in result.stderr
    assert 'PRIVATE' not in result.stderr and 'private.example' not in result.stderr
    path = tmp_path / 'events.jsonl'
    assert path.exists() is enabled
    if enabled:
        content = path.read_text()
        events = [json.loads(line) for line in content.splitlines()]
        assert len(events) == 2
        assert events[0]['worker_failure']['exception_types'] == ['RuntimeError']
        assert events[0]['worker_failure']['metering_valid'] is False
        assert 'model load failed' not in content and 'PRIVATE' not in content


def test_existing_root_logging_is_preserved_without_duplicate_output(tmp_path):
    script = '''
import logging, sys
from pathlib import Path
from app import diagnostic_bundle as diag
root = logging.getLogger()
console = logging.StreamHandler()
root.addHandler(console)
diag.BASE = Path(sys.argv[1])
diag.configure(False)
diag.install_event_capture()
diag.install_event_capture()
assert root.handlers[0] is console
assert len(root.handlers) == 2
logging.getLogger('app.main').error('existing-handler-error')
'''
    result = subprocess.run([sys.executable, '-c', script, str(tmp_path)],
                            cwd=ROOT, capture_output=True, text=True, check=True)
    assert result.stderr.count('existing-handler-error') == 1
