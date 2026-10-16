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
