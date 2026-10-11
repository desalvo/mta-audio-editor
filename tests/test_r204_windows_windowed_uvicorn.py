"""Regression: PyInstaller --windowed may have no standard IO streams."""
from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path


def test_windowed_native_server_disables_uvicorn_stream_formatter(monkeypatch):
    root = Path(__file__).resolve().parents[1]
    spec = importlib.util.spec_from_file_location("mta_r204_native", root / "native" / "mta_audio_editor_native.py")
    launcher = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(launcher)
    seen = {}

    class FakeConfig:
        def __init__(self, application, **kwargs):
            seen.update(kwargs)
            assert kwargs["log_config"] is None

    class FakeServer:
        def __init__(self, config):
            self.should_exit = False

        def run(self):
            pass

    fake_uvicorn = types.ModuleType("uvicorn")
    fake_uvicorn.Config = FakeConfig
    fake_uvicorn.Server = FakeServer
    fake_app = types.ModuleType("app.main")
    fake_app.app = object()
    monkeypatch.setitem(sys.modules, "uvicorn", fake_uvicorn)
    monkeypatch.setitem(sys.modules, "app.main", fake_app)
    # Replacement is limited to the function call, and cannot alter pytest IO.
    with monkeypatch.context() as context:
        context.setattr(sys, "stdout", None)
        context.setattr(sys, "stderr", None)
        server, worker = launcher._start_server(12345)
        worker.join(timeout=2)
    assert not worker.is_alive()
    assert server.should_exit is False
    assert seen["host"] == "127.0.0.1"
    assert seen["port"] == 12345
