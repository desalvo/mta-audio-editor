"""Windows --windowed native launcher must report the actual HTTP startup failure."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import types

import pytest


def launcher():
    path = Path(__file__).resolve().parents[1] / "native" / "mta_audio_editor_native.py"
    spec = importlib.util.spec_from_file_location("mta_windows_startup", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_native_thread_exception_is_reported_without_waiting_timeout(monkeypatch, tmp_path):
    native = launcher()
    monkeypatch.setenv("MTA_NATIVE_DATA_DIR", str(tmp_path))
    class Config:
        def __init__(self, app, **kwargs):
            assert kwargs["log_config"] is None
    class Server:
        started = False
        should_exit = False
        def __init__(self, config):
            pass
        def run(self):
            raise ValueError("uvicorn startup probe failed")
    uvicorn = types.ModuleType("uvicorn")
    uvicorn.Config = Config
    uvicorn.Server = Server
    app = types.ModuleType("app.main")
    app.app = object()
    monkeypatch.setitem(sys.modules, "uvicorn", uvicorn)
    monkeypatch.setitem(sys.modules, "app.main", app)
    server, thread = native._start_server(49001)
    thread.join(timeout=3)
    assert not thread.is_alive()
    with pytest.raises(RuntimeError, match="uvicorn startup probe failed"):
        native._wait_ready("http://127.0.0.1:49001", timeout=1, server=server, thread=thread)
    report = (tmp_path / "logs" / "native-startup.log").read_text()
    assert "uvicorn startup probe failed" in report
    assert "Traceback" in report


def test_unhealthy_http_response_never_counts_as_ready(monkeypatch, tmp_path):
    native = launcher()
    monkeypatch.setenv("MTA_NATIVE_DATA_DIR", str(tmp_path))
    class FakeResponse:
        status = 503
        def read(self): return b"error"
    class FakeConnection:
        def __init__(self, *args, **kwargs): pass
        def request(self, *args): pass
        def getresponse(self): return FakeResponse()
        def close(self): pass
    monkeypatch.setattr(native.http.client, "HTTPConnection", FakeConnection)
    with pytest.raises(RuntimeError, match="HTTP 503"):
        native._wait_ready("http://127.0.0.1:49001", timeout=0.01)


def test_longer_native_startup_timeout_is_bounded(monkeypatch):
    native = launcher()
    for setting, expected in (("", 90), ("10", 20), ("250", 180), ("garbage", 90)):
        if setting: monkeypatch.setenv("MTA_NATIVE_STARTUP_TIMEOUT", setting)
        else: monkeypatch.delenv("MTA_NATIVE_STARTUP_TIMEOUT", raising=False)
        assert native._startup_timeout_seconds() == expected


def test_native_preserves_actual_lifespan_error_without_console(monkeypatch, tmp_path):
    """Run real Uvicorn: it swallows lifespan exceptions before SystemExit(3)."""
    from contextlib import asynccontextmanager
    from fastapi import FastAPI
    import logging

    native = launcher()
    monkeypatch.setenv('MTA_NATIVE_DATA_DIR', str(tmp_path))
    @asynccontextmanager
    async def broken_lifespan(app):
        raise PermissionError('startup storage probe denied')
        yield  # pragma: no cover -- a lifespan async generator must yield
    module = types.ModuleType('app.main')
    module.app = FastAPI(lifespan=broken_lifespan)
    monkeypatch.setitem(sys.modules, 'app.main', module)
    target = logging.getLogger('uvicorn.error')
    before = (list(target.handlers), target.level, target.disabled)
    monkeypatch.setattr(sys, 'stdout', None)
    monkeypatch.setattr(sys, 'stderr', None)
    server, thread = native._start_server(native._free_local_port())
    thread.join(timeout=10)
    assert not thread.is_alive()
    assert isinstance(server._mta_startup_exception, SystemExit)
    assert server._mta_startup_exception.code == 3
    report = (tmp_path / 'logs/native-startup.log').read_text()
    assert 'PermissionError: startup storage probe denied' in report
    assert 'Application startup failed' in report
    assert (target.handlers, target.level, target.disabled) == before


def test_native_diagnostics_uses_user_directory_and_honors_override(monkeypatch, tmp_path):
    native = launcher()
    import os
    monkeypatch.setattr(os, 'environ', dict(os.environ))
    monkeypatch.setattr(native, '_configure_native_tls', lambda: None)
    monkeypatch.setenv('MTA_NATIVE_DATA_DIR', str(tmp_path / 'user data'))
    monkeypatch.delenv('MTA_DIAGNOSTIC_DIR', raising=False)
    native._prepare_environment()
    import os
    assert Path(os.environ['MTA_DIAGNOSTIC_DIR']) == tmp_path / 'user data/diagnostics'
    monkeypatch.setenv('MTA_DIAGNOSTIC_DIR', str(tmp_path / 'custom'))
    native._prepare_environment()
    assert Path(os.environ['MTA_DIAGNOSTIC_DIR']) == tmp_path / 'custom'
